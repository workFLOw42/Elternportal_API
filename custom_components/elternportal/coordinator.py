"""DataUpdateCoordinator for ElternPortal API (manual fetch only)."""
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
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ElternPortalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches data only when explicitly requested."""

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
            update_interval=None,  # No automatic polling
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from ElternPortal."""
        try:
            return await self.api.get_all_data()
        except ElternPortalAuthError as err:
            raise UpdateFailed(f"Authentication error: {err}") from err
        except ElternPortalApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err