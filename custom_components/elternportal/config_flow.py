"""Config flow for ElternPortal API."""
from __future__ import annotations

import logging
from collections.abc import Mapping
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
    ENDPOINT_TOGGLES,
)

_LOGGER = logging.getLogger(__name__)

CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCHOOL_SLUG): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ElternPortalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ElternPortal API."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._user_input: dict[str, Any] = {}
        self._reauth_entry: ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> ElternPortalOptionsFlow:
        """Get the options flow."""
        return ElternPortalOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Credentials."""
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
                await api.test_connection()
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
                self._user_input = user_input
                return await self.async_step_child()

        return self.async_show_form(
            step_id="user",
            data_schema=CREDENTIALS_SCHEMA,
            errors=errors,
        )

    async def async_step_child(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: Child name for sensor naming."""
        if user_input is not None:
            child_name = user_input.get(CONF_CHILD_NAME, "").strip()
            self._user_input[CONF_CHILD_NAME] = child_name

            slug = self._user_input[CONF_SCHOOL_SLUG]
            if child_name:
                title = f"ElternPortal ({slug} – {child_name})"
            else:
                title = f"ElternPortal ({slug})"

            return self.async_create_entry(title=title, data=self._user_input)

        return self.async_show_form(
            step_id="child",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_CHILD_NAME, default=""): str,
                }
            ),
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication trigger."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}
        assert self._reauth_entry is not None

        if user_input is not None:
            api = ElternPortalApi(
                school_slug=self._reauth_entry.data[CONF_SCHOOL_SLUG],
                username=self._reauth_entry.data[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
            )
            try:
                await api.test_connection()
            except ElternPortalAuthError:
                errors["base"] = "invalid_auth"
            except ElternPortalApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            finally:
                await api.close()

            if not errors:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry,
                    data={
                        **self._reauth_entry.data,
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={
                "school_slug": self._reauth_entry.data[CONF_SCHOOL_SLUG],
                "username": self._reauth_entry.data[CONF_USERNAME],
            },
        )


class ElternPortalOptionsFlow(OptionsFlow):
    """Handle options for ElternPortal API."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_child = self.config_entry.options.get(
            CONF_CHILD_NAME,
            self.config_entry.data.get(CONF_CHILD_NAME, ""),
        )

        schema_dict: dict[Any, Any] = {
            vol.Optional(CONF_CHILD_NAME, default=current_child): str,
        }
        for conf_key in ENDPOINT_TOGGLES.values():
            current_val = self.config_entry.options.get(conf_key, True)
            schema_dict[vol.Optional(conf_key, default=current_val)] = bool

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )