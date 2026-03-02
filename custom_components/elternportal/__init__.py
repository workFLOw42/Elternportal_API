"""The ElternPortal API integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall

from .api import ElternPortalApi
from .const import (
    DOMAIN,
    CONF_SCHOOL_SLUG,
    CONF_USERNAME,
    CONF_PASSWORD,
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

    # ---- Service: elternportal.fetch_data ----
    async def handle_fetch_data(call: ServiceCall) -> None:
        """Handle the fetch_data service call."""
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


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        coordinator: ElternPortalCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.close()

    # Remove service when no entries left
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_FETCH_DATA)

    return unload_ok