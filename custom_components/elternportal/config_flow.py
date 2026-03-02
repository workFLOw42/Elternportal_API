"""Config flow for ElternPortal API."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .api import ElternPortalApi, ElternPortalAuthError, ElternPortalApiError
from .const import DOMAIN, CONF_SCHOOL_SLUG, CONF_USERNAME, CONF_PASSWORD

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCHOOL_SLUG): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ElternPortalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ElternPortal API."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_SCHOOL_SLUG]}_{user_input[CONF_USERNAME]}"
            )
            self._abort_if_unique_id_configured()

            api = ElternPortalApi(
                school_slug=user_input[CONF_SCHOOL_SLUG],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )

            try:
                if not await api.test_connection():
                    errors["base"] = "invalid_auth"
            except ElternPortalAuthError:
                errors["base"] = "invalid_auth"
            except ElternPortalApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            finally:
                await api.close()

            if not errors:
                return self.async_create_entry(
                    title=f"ElternPortal API ({user_input[CONF_SCHOOL_SLUG]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )