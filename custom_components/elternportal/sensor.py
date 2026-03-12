"""Sensor platform for ElternPortal API."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_CHILD_NAME,
    ATTR_CLASS_NAME,
    ATTR_ENTRIES,
    ATTR_LAST_FETCH,
    CONF_CHILD_NAME,
    CONF_SCHOOL_SLUG,
    DOMAIN,
    SENSOR_APPOINTMENTS,
    SENSOR_BLACKBOARD,
    SENSOR_EXAMS,
    SENSOR_LETTERS,
    SENSOR_MESSAGES,
    SENSOR_SCHOOL_INFO,
    SENSOR_SURVEYS,
    SENSOR_TIMETABLE,
)
from .coordinator import ElternPortalCoordinator

_LOGGER = logging.getLogger(__name__)

STRIP_FIELDS: dict[str, set[str]] = {
    "letters": {"body", "link"},
    "blackboard": {"content"},
    "messages": {"body"},
    "school_info": {"details"},
}

SENSORS: dict[str, dict[str, str]] = {
    SENSOR_SCHOOL_INFO: {
        "name": "Schulinformationen",
        "icon": "mdi:school-outline",
        "data_key": "school_info",
    },
    SENSOR_TIMETABLE: {
        "name": "Stundenplan",
        "icon": "mdi:timetable",
        "data_key": "timetable",
    },
    SENSOR_EXAMS: {
        "name": "Schulaufgaben",
        "icon": "mdi:clipboard-text-clock-outline",
        "data_key": "exams",
    },
    SENSOR_APPOINTMENTS: {
        "name": "Termine",
        "icon": "mdi:calendar-clock",
        "data_key": "appointments",
    },
    SENSOR_BLACKBOARD: {
        "name": "Schwarzes Brett",
        "icon": "mdi:bulletin-board",
        "data_key": "blackboard",
    },
    SENSOR_LETTERS: {
        "name": "Elternbriefe",
        "icon": "mdi:email-outline",
        "data_key": "letters",
    },
    SENSOR_MESSAGES: {
        "name": "Kommunikation Fachlehrer",
        "icon": "mdi:message-text-outline",
        "data_key": "messages",
    },
    SENSOR_SURVEYS: {
        "name": "Umfragen",
        "icon": "mdi:poll",
        "data_key": "surveys",
    },
}


def _slugify(text: str) -> str:
    """Create a slug from text."""
    text = text.lower().strip()
    text = re.sub(r"[äÄ]", "ae", text)
    text = re.sub(r"[öÖ]", "oe", text)
    text = re.sub(r"[üÜ]", "ue", text)
    text = re.sub(r"[ß]", "ss", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text


def _build_entity_id(slug: str, child_name: str, sensor_type: str) -> str:
    """Build consistent entity ID part."""
    parts = [_slugify(slug)]
    if child_name:
        parts.append(_slugify(child_name))
    parts.append(_slugify(sensor_type))
    return "_".join(parts)


def _slim_entries(data_key: str, entries: list[dict]) -> list[dict]:
    """Remove large text fields to stay under recorder 16KB limit."""
    fields_to_strip = STRIP_FIELDS.get(data_key)
    if not fields_to_strip or not entries:
        return entries
    slim = []
    for entry in entries:
        slim_entry = {
            k: v for k, v in entry.items() if k not in fields_to_strip
        }
        slim.append(slim_entry)
    return slim


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

    _attr_has_entity_name = False

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
        self._sensor_type = sensor_type
        self._description = description
        self._entry = entry
        self._attr_icon = description["icon"]

        child_name = entry.data.get(CONF_CHILD_NAME, "")
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"

        slug = entry.data.get(CONF_SCHOOL_SLUG, "elternportal")
        sensor_label = description["name"]
        entity_slug = _build_entity_id(slug, child_name, sensor_label)
        self.entity_id = f"sensor.{entity_slug}"

    def _get_child_name(self) -> str:
        child = self._entry.options.get(CONF_CHILD_NAME, "")
        if child:
            return child
        child = self._entry.data.get(CONF_CHILD_NAME, "")
        if child:
            return child
        if self.coordinator.child_name:
            return self.coordinator.child_name
        return ""

    def _get_entries(self) -> list:
        if self.coordinator.data is None:
            return []
        data = self.coordinator.data.get(self._data_key, [])
        if isinstance(data, list):
            return data
        return []

    @property
    def name(self) -> str:
        slug = self._entry.data.get(CONF_SCHOOL_SLUG, "elternportal")
        child = self._get_child_name()
        sensor_name = self._description["name"]
        if child:
            return f"{slug} {child} {sensor_name}"
        return f"{slug} {sensor_name}"

    @property
    def native_value(self) -> int | None:
        if self.coordinator.data is None:
            return None
        entries = self._get_entries()
        return len(entries) if entries else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self.coordinator.data is None:
            return {}

        entries = self._get_entries()

        last_fetch = None
        if (
            hasattr(self.coordinator, "last_update_success_time")
            and self.coordinator.last_update_success_time
        ):
            last_fetch = self.coordinator.last_update_success_time.isoformat()
        elif self.coordinator.last_update_success:
            last_fetch = dt_util.now().isoformat()

        slim = _slim_entries(self._data_key, entries)

        attrs: dict[str, Any] = {
            ATTR_ENTRIES: slim,
            ATTR_LAST_FETCH: last_fetch,
        }

        if self._data_key == "letters":
            unread = sum(
                1
                for e in entries
                if isinstance(e, dict) and not e.get("acknowledged", True)
            )
            attrs["unread_count"] = unread

        child_name = self._get_child_name()
        if child_name:
            attrs[ATTR_CHILD_NAME] = child_name

        class_name = self.coordinator.class_name
        if class_name:
            attrs[ATTR_CLASS_NAME] = class_name

        return attrs