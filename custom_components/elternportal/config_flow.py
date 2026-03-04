"""Config flow for ElternPortal API."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .api import ElternPortalApi, ElternPortalAuthError, ElternPortalApiError
from .const import (
    CONF_CHILD_NAME,
    CONF_PASSWORD,
    CONF_SCHOOL_SLUG,
    CONF_USERNAME,
    DOMAIN,
)

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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ElternPortalOptionsFlow:
        """Get the options flow."""
        return ElternPortalOptionsFlow(config_entry)

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
                    title=f"ElternPortal ({user_input[CONF_SCHOOL_SLUG]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )


class ElternPortalOptionsFlow(OptionsFlow):
    """Handle options for ElternPortal API."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_child = self.config_entry.options.get(CONF_CHILD_NAME, "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CHILD_NAME,
                        default=current_child,
                    ): str,
                }
            ),
        )