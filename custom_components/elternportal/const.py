"""Constants for the ElternPortal API integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "elternportal"

CONF_SCHOOL_SLUG: Final = "school_slug"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_CHILD_NAME: Final = "child_name"

# API
BASE_URL_TEMPLATE: Final = "https://{}.eltern-portal.org"
ENDPOINT_LOGIN: Final = "/includes/project/auth/login.php"
ENDPOINT_LOGOUT: Final = "/includes/project/auth/logout.php"

# Pfade
PATH_SCHOOL_INFO: Final = "/service/schulinformationen"
PATH_TIMETABLE: Final = "/service/stundenplan"
PATH_EXAMS: Final = "/service/termine/liste/schulaufgaben"
PATH_APPOINTMENTS: Final = "/service/termine/liste/allgemein"
PATH_BLACKBOARD: Final = "/aktuelles/schwarzes_brett"
PATH_LETTERS: Final = "/aktuelles/elternbriefe"
PATH_MESSAGES: Final = "/meldungen/kommunikation_fachlehrer"
PATH_SURVEYS: Final = "/aktuelles/umfragen"

# Service
SERVICE_FETCH_DATA: Final = "fetch_data"

# Sensor keys
SENSOR_SCHOOL_INFO: Final = "school_info"
SENSOR_TIMETABLE: Final = "timetable"
SENSOR_EXAMS: Final = "exams"
SENSOR_APPOINTMENTS: Final = "appointments"
SENSOR_BLACKBOARD: Final = "blackboard"
SENSOR_LETTERS: Final = "letters"
SENSOR_MESSAGES: Final = "messages"
SENSOR_SURVEYS: Final = "surveys"

# Attribute keys
ATTR_ENTRIES: Final = "entries"
ATTR_LAST_FETCH: Final = "last_fetch"
ATTR_CHILD_NAME: Final = "child_name"
ATTR_CLASS_NAME: Final = "class_name"
ATTR_PARSER_HEALTH: Final = "parser_health"

# Parser health status
HEALTH_OK: Final = "ok"
HEALTH_EMPTY: Final = "empty"
HEALTH_DEGRADED: Final = "degraded"