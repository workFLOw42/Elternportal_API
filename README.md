# 📋 ElternPortal API – Home Assistant Integration

<p align="center">
  <img src="https://raw.githubusercontent.com/workFLOw42/Elternportal_API/main/images/logo-hires.png" alt="ElternPortal API" width="256">
</p>

<p align="center">
  <a href="https://github.com/workFLOw42/Elternportal_API/actions/workflows/validate.yml">
    <img src="https://github.com/workFLOw42/Elternportal_API/actions/workflows/validate.yml/badge.svg" alt="Validate Integration">
  </a>
  <a href="https://github.com/hacs/integration">
    <img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom">
  </a>
  <a href="https://github.com/workFLOw42/Elternportal_API/releases">
    <img src="https://img.shields.io/github/v/release/workFLOw42/Elternportal_API" alt="GitHub Release">
  </a>
  <a href="https://github.com/workFLOw42/Elternportal_API/releases">
    <img src="https://img.shields.io/github/downloads/workFLOw42/Elternportal_API/total?label=Downloads&color=blue" alt="Downloads">
  </a>
  <a href="https://github.com/workFLOw42/Elternportal_API">
    <img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.elternportal.total&label=HACS%20Installs&color=41BDF5" alt="HACS Installs">
  </a>
  <a href="https://github.com/workFLOw42/Elternportal_API/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT">
  </a>
</p>

<p align="center">
  Custom Home Assistant integration for <a href="https://eltern-portal.org/">Eltern-Portal</a> – the school communication platform used by many schools in Bavaria, Germany.
</p>

---

## ✨ Features

| Sensor | Description | Icon |
|---|---|---|
| **Schulinformationen** | School contact details & teacher directory | 🏫 |
| **Stundenplan** | Timetable with subjects, rooms & teacher assignments | 📅 |
| **Schulaufgaben** | Exam schedule (Schulaufgaben, Tests, Kurzarbeiten) | 📝 |
| **Termine** | General school appointments & events | 📆 |
| **Schwarzes Brett** | Bulletin board messages (active + archived) | 📌 |
| **Elternbriefe** | Parent letters with read/unread status | ✉️ |
| **Kommunikation Fachlehrer** | Teacher communication messages | 💬 |
| **Umfragen** | Surveys & polls with voting status | 📊 |

### Additional Features

- 🧒 **Automatic child detection** – name and class are auto-detected from the portal
- 🏷️ **Smart sensor naming** – sensors are named `[school_slug] [child_name] [sensor]`
- ⚙️ **Options flow** – configure child name via UI (Settings → Integrations → Configure)
- 🔄 **Manual fetch** – data is fetched on demand via `elternportal.fetch_data` service
- 🔐 **Secure authentication** – CSRF-token based login with session management

---

## 📦 Installation

### HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Click **⋮** (top right) → **Custom repositories**
3. Add `https://github.com/workFLOw42/Elternportal_API` as **Integration**
4. Search for **ElternPortal API** and install
5. Restart Home Assistant

### Manual Installation

1. Download the [latest release](https://github.com/workFLOw42/Elternportal_API/releases)
2. Copy the `custom_components/elternportal` folder to your `config/custom_components/` directory
3. Restart Home Assistant

---

## ⚙️ Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **ElternPortal API**
3. Enter your credentials:

| Field | Description | Example |
|---|---|---|
| **School slug** | Subdomain of your school's Eltern-Portal URL | `aegymuc` |
| **Username** | Your login email | `parent@example.com` |
| **Password** | Your login password | `••••••••` |

> 💡 The school slug is the part before `.eltern-portal.org` in your school's URL.
> For example: `https://aegymuc.eltern-portal.org` → slug is `aegymuc`

### Options (Child Name)

1. Go to **Settings** → **Devices & Services**
2. Find **ElternPortal API** and click **Configure**
3. Enter the **child name** (used in sensor naming)
4. Leave empty for automatic detection

---

## 🔄 Fetching Data

This integration uses **manual fetch only** (no automatic polling). To fetch data:

### Via Service Call

```yaml
service: elternportal.fetch_data
data: {}
```

### Via Automation

```yaml
automation:
  - alias: "Fetch ElternPortal data every morning"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: elternportal.fetch_data
```

### Via Developer Tools

Go to **Developer Tools** → **Services** → search for `elternportal.fetch_data` → **Call Service**

---

## 📊 Sensor Details

Each sensor shows the **number of entries** as its state and provides the **full data** in the `entries` attribute.

### Example: Schulaufgaben Sensor

**State:** `22` (number of exams)

**Attributes:**

```yaml
entries:
  - date: "11.03.2026"
    description: "Schulaufgabe in Deutsch (GEN)"
    month: "März"
    year: "2026"
  - date: "20.03.2026"
    description: "Schulaufgabe in Mathematik (GEI)"
    month: "März"
    year: "2026"
child_name: "Samuel Greiffert"
class_name: "6D"
last_fetch: "2026-03-04T10:28:53.344191"
```

### Example: Elternbriefe Sensor

**State:** `94` (number of letters)

**Attributes:**

```yaml
entries:
  - number: "#94"
    title: "Tag der Demokratie am 18.März 2026"
    date: "03.03.2026 14:08:24"
    acknowledged: false
    has_file: true
    classes: "Klasse/n: 6D"
  - number: "#93"
    title: "Terminübersicht zu den medienpädagogischen Elternabenden"
    date: "27.02.2026 14:53:35"
    acknowledged: true
    has_file: true
    classes: "Klasse/n: 6D"
```

### Example: Schwarzes Brett Sensor

**State:** `4` (number of entries)

**Attributes:**

```yaml
entries:
  - title: "Nachhilfe am AEG"
    date: "11.03.2025 00:00:00"
    archived: false
    has_attachment: true
    attachment: "Nachhilfe am AEG.docx herunterladen"
  - title: "Versand des 2. Leistungsstandberichts"
    date: "12.02.2026 - 12.02.2026"
    archived: true
    content: "Sehr geehrte Eltern und Erziehungsberechtigte, ..."
```

---

## 🏠 Dashboard Examples

### Upcoming Exams Card (Markdown)

```yaml
type: markdown
title: 📝 Nächste Schulaufgaben
content: >
  {% set exams = state_attr('sensor.aegymuc_samuel_greiffert_schulaufgaben', 'entries') %}
  {% if exams %}
  {% for exam in exams[:5] %}
  - **{{ exam.date }}** – {{ exam.description }}
  {% endfor %}
  {% else %}
  Keine Schulaufgaben gefunden.
  {% endif %}
```

### Unread Letters Card (Markdown)

```yaml
type: markdown
title: ✉️ Ungelesene Elternbriefe
content: >
  {% set letters = state_attr('sensor.aegymuc_samuel_greiffert_elternbriefe', 'entries') %}
  {% if letters %}
  {% for letter in letters if not letter.acknowledged %}
  - **{{ letter.title }}** ({{ letter.date }})
  {% endfor %}
  {% else %}
  Alle Elternbriefe gelesen ✅
  {% endif %}
```

### Open Surveys Card (Markdown)

```yaml
type: markdown
title: 📊 Offene Umfragen
content: >
  {% set surveys = state_attr('sensor.aegymuc_samuel_greiffert_umfragen', 'entries') %}
  {% if surveys %}
  {% for survey in surveys if not survey.voted %}
  - **{{ survey.title }}** (bis {{ survey.end_date }})
  {% endfor %}
  {% else %}
  Keine offenen Umfragen 👍
  {% endif %}
```

---

## 🐛 Troubleshooting

| Problem | Solution |
|---|---|
| **Login fails** | Verify your credentials at `https://[slug].eltern-portal.org` |
| **No data after setup** | Call the `elternportal.fetch_data` service manually |
| **Sensors show 0** | Check HA logs for parsing errors: **Settings → System → Logs** |
| **CSRF token error** | The portal may be temporarily unavailable – retry later |
| **Wrong child name** | Configure via **Settings → Integrations → ElternPortal → Configure** |

### Enable Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.elternportal: debug
```

---

## 📋 Changelog

### v2.0.0 (2025-03-04)

- 🔧 **Complete parser rewrite** – all parsers rebuilt based on real HTML structure
- 🆕 **Umfragen/Surveys sensor** – new sensor for polls and surveys
- 🧒 **Automatic child detection** – name and class auto-detected from portal navigation
- 🏷️ **Smart sensor naming** – `[school_slug] [child_name] [sensor_name]`
- ⚙️ **Options flow** – configure child name via UI
- 🐛 **Fixed**: Schulaufgaben/Termine sensors showing privacy policy instead of actual data
- 🐛 **Fixed**: Schulinformationen parser not matching actual HTML structure
- 🐛 **Fixed**: Schwarzes Brett parser missing active/archived entries
- 🐛 **Fixed**: Elternbriefe parser not handling paired-row structure

### v1.1.0

- Initial release

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 🙏 Credits

- Built for [Home Assistant](https://www.home-assistant.io/)
- Data provided by [Eltern-Portal](https://eltern-portal.org/) by art soft and more GmbH
- Inspired by [DSB_Mobile_Api](https://github.com/workFLOw42/DSB_Mobile_Api) and [ha-deutsche-ferien](https://github.com/workFLOw42/ha-deutsche-ferien)