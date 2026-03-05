"""The ElternPortal API integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .api import ElternPortalApi
from .const import (
    CONF_PASSWORD,
    CONF_SCHOOL_SLUG,
    CONF_USERNAME,
    DOMAIN,
    SERVICE_FETCH_DATA,
)
from .coordinator import ElternPortalCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ElternPortal API from a config entry."""
    api = ElternPortalApi(
        school_slug=entry.data[CONF_SCHOOL_SLUG],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
    )

    coordinator = ElternPortalCoordinator(hass, api)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def handle_fetch_data(call: ServiceCall) -> None:
        for coord in hass.data[DOMAIN].values():
            if isinstance(coord, ElternPortalCoordinator):
                await coord.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_FETCH_DATA):
        hass.services.async_register(
            DOMAIN,
            SERVICE_FETCH_DATA,
            handle_fetch_data,
            schema=vol.Schema({}),
        )

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        coordinator: ElternPortalCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        await coordinator.api.close()

    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_FETCH_DATA)

    return unload_ok