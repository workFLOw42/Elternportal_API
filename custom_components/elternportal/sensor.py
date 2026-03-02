"""Sensor platform for ElternPortal API."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    SENSOR_LETTERS,
    SENSOR_BLACKBOARD,
    SENSOR_MESSAGES,
    SENSOR_SUBSTITUTION,
    SENSOR_APPOINTMENTS,
    SENSOR_TIMETABLE,
    SENSOR_CHILDREN,
    ATTR_ENTRIES,
    ATTR_LAST_FETCH,
)
from .coordinator import ElternPortalCoordinator

_LOGGER = logging.getLogger(__name__)

SENSORS: dict[str, dict[str, str]] = {
    SENSOR_LETTERS: {
        "name": "Elternbriefe",
        "icon": "mdi:email-outline",
        "data_key": "letters",
    },
    SENSOR_BLACKBOARD: {
        "name": "Schwarzes Brett",
        "icon": "mdi:bulletin-board",
        "data_key": "blackboard",
    },
    SENSOR_APPOINTMENTS: {
        "name": "Termine",
        "icon": "mdi:calendar-school",
        "data_key": "appointments",
    },
    SENSOR_MESSAGES: {
        "name": "Nachrichten",
        "icon": "mdi:message-text-outline",
        "data_key": "messages",
    },
    SENSOR_SUBSTITUTION: {
        "name": "Vertretungsplan",
        "icon": "mdi:swap-horizontal",
        "data_key": "substitution",
    },
    SENSOR_TIMETABLE: {
        "name": "Stundenplan",
        "icon": "mdi:timetable",
        "data_key": "timetable",
    },
    SENSOR_CHILDREN: {
        "name": "Kinder",
        "icon": "mdi:account-child",
        "data_key": "children",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ElternPortal API sensors."""
    coordinator: ElternPortalCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        ElternPortalSensor(
            coordinator=coordinator,
            entry=entry,
            sensor_type=sensor_type,
            description=description,
        )
        for sensor_type, description in SENSORS.items()
    )


class ElternPortalSensor(
    CoordinatorEntity[ElternPortalCoordinator], SensorEntity
):
    """A single ElternPortal API sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ElternPortalCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        description: dict[str, str],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._data_key = description["data_key"]
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_name = description["name"]
        self._attr_icon = description["icon"]

    @property
    def native_value(self) -> int | None:
        """Return the number of items."""
        if self.coordinator.data is None:
            return None
        return len(self.coordinator.data.get(self._data_key, []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the full list of items as attribute."""
        if self.coordinator.data is None:
            return {}
        return {
            ATTR_ENTRIES: self.coordinator.data.get(self._data_key, []),
            ATTR_LAST_FETCH: (
                self.coordinator.last_update_success_time.isoformat()
                if self.coordinator.last_update_success_time
                else None
            ),
        }