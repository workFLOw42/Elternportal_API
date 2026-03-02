"""Constants for the ElternPortal API integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "elternportal"

CONF_SCHOOL_SLUG: Final = "school_slug"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"

# API
BASE_URL_TEMPLATE: Final = "https://{}.eltern-portal.org"

ENDPOINT_LOGIN: Final = "/includes/project/auth/login.php"
ENDPOINT_LOGOUT: Final = "/includes/project/auth/logout.php"

# Service
SERVICE_FETCH_DATA: Final = "fetch_data"

# Sensor keys
SENSOR_LETTERS: Final = "letters"
SENSOR_BLACKBOARD: Final = "blackboard"
SENSOR_MESSAGES: Final = "messages"
SENSOR_SUBSTITUTION: Final = "substitution"
SENSOR_APPOINTMENTS: Final = "appointments"
SENSOR_TIMETABLE: Final = "timetable"
SENSOR_CHILDREN: Final = "children"

# Attribute keys
ATTR_ENTRIES: Final = "entries"
ATTR_LAST_FETCH: Final = "last_fetch"