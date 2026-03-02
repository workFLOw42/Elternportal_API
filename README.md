# ElternPortal API for Home Assistant

[![GitHub Release](https://img.shields.io/github/release/workFLOw42/Elternportal_API.svg?style=for-the-badge)](https://github.com/workFLOw42/Elternportal_API/releases)
[![License](https://img.shields.io/github/license/workFLOw42/Elternportal_API.svg?style=for-the-badge)](LICENSE)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

<p align="center">
  <img src="https://raw.githubusercontent.com/workFLOw42/ElternPortal_API/main/images/logo-hires.png" alt="ElternPortal API" width="256">
</p>

A Home Assistant custom integration for [ElternPortal](https://eltern-portal.org) – the school communication platform used by many German schools.

Based on the concepts of the [elternportal-api](https://github.com/philippdormann/elternportal-api) by Philipp Dormann.

---

## Features

| Sensor | State | Attributes |
|--------|-------|------------|
| **Schulinformationen** | Number of info entries | School information (key-value pairs) |
| **Stundenplan** | Number of rows | Full timetable (subject, teacher, room per slot) |
| **Schulaufgaben** | Number of exams | Upcoming exams (date, subject, title) |
| **Termine** | Number of appointments | General appointments (date, title, details) |
| **Schwarzes Brett** | Number of entries | Blackboard entries (title, content, date) |
| **Elternbriefe** | Number of letters | Parent letters (title, date, link, new-flag) |
| **Kommunikation Fachlehrer** | Number of messages | Teacher messages (subject, sender, date, unread) |
| **Kinder** | Number of children | Children information (name, class) |

> **Manual fetch only** – Data is fetched exclusively via the `elternportal.fetch_data` service.
> No automatic polling. Trigger it from an automation, script, or the Developer Tools.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **ElternPortal API**
3. Enter your credentials:
   - **School Slug** – subdomain of your school, e.g. `aegymuc` from `aegymuc.eltern-portal.org`
   - **Username** – your email address
   - **Password** – your password

---

## Service

### `elternportal.fetch_data`

Fetches all data from ElternPortal and updates every sensor.

```yaml
service: elternportal.fetch_data
data: {}
```

---

## Endpoints

| Sensor | URL Path |
|--------|----------|
| Schulinformationen | `/service/schulinformationen` |
| Stundenplan | `/service/stundenplan` |
| Schulaufgaben | `/service/termine/liste/schulaufgaben` |
| Termine | `/service/termine/liste/allgemein` |
| Schwarzes Brett | `/aktuelles/schwarzes_brett` |
| Elternbriefe | `/aktuelles/elternbriefe` |
| Kommunikation Fachlehrer | `/meldungen/kommunikation_fachlehrer` |
| Kinder | `/service/kinder` |

---

## Example Automation

```yaml
automation:
  - alias: "ElternPortal – Daten abrufen"
    trigger:
      - platform: time_pattern
        hours: "/2"
    action:
      - service: elternportal.fetch_data

  - alias: "ElternPortal – Neue Elternbriefe"
    trigger:
      - platform: state
        entity_id: sensor.elternportal_api_elternbriefe
    condition:
      - condition: template
        value_template: >
          {{ trigger.to_state.state | int(0) > trigger.from_state.state | int(0) }}
    action:
      - service: notify.mobile_app
        data:
          title: "Neuer Elternbrief"
          message: >
            Es gibt {{ trigger.to_state.state }} Elternbriefe.

  - alias: "ElternPortal – Neue Schulaufgabe"
    trigger:
      - platform: state
        entity_id: sensor.elternportal_api_schulaufgaben
    condition:
      - condition: template
        value_template: >
          {{ trigger.to_state.state | int(0) > trigger.from_state.state | int(0) }}
    action:
      - service: notify.mobile_app
        data:
          title: "Neue Schulaufgabe"
          message: >
            {{ trigger.to_state.state }} Schulaufgaben eingetragen.

  - alias: "ElternPortal – Schwarzes Brett"
    trigger:
      - platform: state
        entity_id: sensor.elternportal_api_schwarzes_brett
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state | int(0) > 0 }}"
    action:
      - service: notify.mobile_app
        data:
          title: "Schwarzes Brett"
          message: >
            {{ trigger.to_state.state }} Einträge am Schwarzen Brett.
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Login fails | Verify the school slug matches your school URL (e.g. `aegymuc` from `aegymuc.eltern-portal.org`) |
| No data after setup | Call `elternportal.fetch_data` – there is no automatic polling |
| Sensor shows 0 | Some schools don't use all features |
| Parsing issues | HTML structure may vary per school – open an issue with details |

---

## Credits

- [elternportal-api](https://github.com/philippdormann/elternportal-api) by Philipp Dormann
- Inspired by [DSB_Mobile_Api](https://github.com/workFLOw42/DSB_Mobile_Api) and [ha-deutsche-ferien](https://github.com/workFLOw42/ha-deutsche-ferien)