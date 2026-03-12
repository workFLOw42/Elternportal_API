"""DataUpdateCoordinator for ElternPortal API."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import ElternPortalApi, ElternPortalApiError, ElternPortalAuthError
from .const import DOMAIN, ENDPOINT_TOGGLES

_LOGGER = logging.getLogger(__name__)

# Keys that should have entries when the portal has data
_CRITICAL_KEYS = ("exams", "appointments")

# Max consecutive empty fetches before accepting empty data
_MAX_EMPTY_RETRIES = 3


class ElternPortalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches data only when explicitly requested.

    Includes stale-data protection: if the portal returns empty data
    but we previously had good data, we keep the old data and retry
    with a fresh session before accepting the empty result.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: ElternPortalApi,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
        )
        self.api = api
        self._consecutive_empty: int = 0
        self._last_good_data: dict[str, Any] | None = None

    @property
    def child_name(self) -> str | None:
        """Return detected child name."""
        if self.data:
            return self.data.get("child_name")
        return self.api.child_name

    @property
    def class_name(self) -> str | None:
        """Return detected class name."""
        if self.data:
            return self.data.get("class_name")
        return self.api.class_name

    def _count_critical_entries(self, data: dict[str, Any]) -> int:
        """Count entries in critical keys."""
        return sum(
            len(data.get(k, []))
            for k in _CRITICAL_KEYS
            if isinstance(data.get(k), list)
        )

    async def _fetch_with_fresh_session(
        self, enabled_endpoints: set[str] | None = None
    ) -> dict[str, Any] | None:
        """Close session and try a completely fresh fetch."""
        _LOGGER.info("Attempting fresh session recovery...")
        await self.api.close()
        try:
            retry_data = await self.api.get_all_data(
                enabled_endpoints=enabled_endpoints
            )
            retry_count = self._count_critical_entries(retry_data)
            if retry_count > 0:
                _LOGGER.info(
                    "Fresh session recovered %d critical entries!",
                    retry_count,
                )
                return retry_data
            _LOGGER.warning("Fresh session also returned empty data.")
        except (ElternPortalApiError, ElternPortalAuthError) as err:
            _LOGGER.warning("Fresh session retry failed: %s", err)
        return None

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from ElternPortal with stale-data protection."""
        # ── Build enabled endpoints set from options ──
        enabled = {
            key
            for key, conf_key in ENDPOINT_TOGGLES.items()
            if self.config_entry.options.get(conf_key, True)
        }

        # ── Attempt fetch ──
        try:
            new_data = await self.api.get_all_data(enabled_endpoints=enabled)
        except ElternPortalAuthError as err:
            _LOGGER.warning("Auth error, attempting fresh session: %s", err)
            recovery = await self._fetch_with_fresh_session(enabled)
            if recovery:
                self._consecutive_empty = 0
                self._last_good_data = recovery
                return recovery
            if self._last_good_data:
                _LOGGER.warning(
                    "Auth recovery failed. Keeping last good data."
                )
                return self._last_good_data
            raise UpdateFailed(f"Authentication error: {err}") from err
        except ElternPortalApiError as err:
            if self._last_good_data:
                _LOGGER.warning(
                    "Fetch error, keeping last good data: %s", err
                )
                return self._last_good_data
            raise UpdateFailed(f"Error fetching data: {err}") from err

        # ── Stale-data protection ──
        critical_count = self._count_critical_entries(new_data)

        if critical_count == 0 and self._last_good_data:
            self._consecutive_empty += 1
            _LOGGER.warning(
                "ElternPortal returned empty critical data "
                "(attempt %d/%d). Previous data had %d entries.",
                self._consecutive_empty,
                _MAX_EMPTY_RETRIES,
                self._count_critical_entries(self._last_good_data),
            )

            if self._consecutive_empty >= _MAX_EMPTY_RETRIES:
                # After N attempts, accept the empty data
                # (portal might genuinely be empty, e.g. new school year)
                _LOGGER.warning(
                    "Max empty retries (%d) reached. Accepting empty data. "
                    "If this is unexpected, reload the integration.",
                    _MAX_EMPTY_RETRIES,
                )
                self._consecutive_empty = 0
                self._last_good_data = new_data
                return new_data

            # Try once with a fresh session
            recovery = await self._fetch_with_fresh_session(enabled)
            if recovery:
                self._consecutive_empty = 0
                self._last_good_data = recovery
                return recovery

            # Fresh session didn't help – keep old data
            return self._last_good_data

        # ── Good fetch – save and reset ──
        if critical_count > 0:
            self._consecutive_empty = 0
            self._last_good_data = new_data

        return new_data