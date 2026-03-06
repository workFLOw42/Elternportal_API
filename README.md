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
| **Elternbriefe** | Parent letters with unread count & metadata | ✉️ |
| **Kommunikation Fachlehrer** | Teacher communication messages | 💬 |
| **Umfragen** | Surveys & polls with voting status | 📊 |

### Additional Features

- 🧒 **Child name in setup flow** – set a name or short code during initial setup for consistent entity IDs
- 🏷️ **Smart sensor naming** – entity IDs follow `sensor.[slug]_[child]_[sensor]` pattern
- 👨‍👩‍👧‍👦 **Multi-child support** – add the integration multiple times, one per child
- ⚙️ **Options flow** – change display name via UI (Settings → Integrations → Configure)
- 🔄 **Manual fetch** – data is fetched on demand via `elternportal.fetch_data` service
- 🔐 **Secure authentication** – CSRF-token based login with session management
- 📏 **Recorder-safe** – large text fields (body, content) are stripped from attributes to stay under 16KB
- 🛡️ **Stale-data protection** – sensors keep last good data when the portal is temporarily unreachable
- 🔁 **Auto session recovery** – automatic re-login and session refresh on connection loss

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

### Initial Setup (2 Steps)

**Step 1 – Credentials:**

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **ElternPortal API**
3. Enter your credentials:

| Field | Description | Example |
|---|---|---|
| **School slug** | Subdomain of your school's Eltern-Portal URL | `gymnasium-musterstadt` |
| **Username** | Your login email | `parent@example.com` |
| **Password** | Your login password | `••••••••` |

> 💡 The school slug is the part before `.eltern-portal.org` in your school's URL.
> For example: `https://gymnasium-musterstadt.eltern-portal.org` → slug is `gymnasium-musterstadt`

**Step 2 – Child Name:**

4. Enter a **name or short code** for your child

| Input | Entity ID Example | Friendly Name |
|---|---|---|
| `MAX` | `sensor.gymnasium_musterstadt_max_schulaufgaben` | gymnasium-musterstadt MAX Schulaufgaben |
| `Lisa M` | `sensor.gymnasium_musterstadt_lisa_m_schulaufgaben` | gymnasium-musterstadt Lisa M Schulaufgaben |
| *(empty)* | `sensor.gymnasium_musterstadt_schulaufgaben` | gymnasium-musterstadt Schulaufgaben |

> ⚠️ **Entity IDs are set during initial setup and cannot be changed later.** Choose wisely – especially when you have multiple children at the same school.

### Multiple Children

Add the integration once per child:

1. **Settings** → **Devices & Services** → **Add Integration** → **ElternPortal API**
2. Use the **same credentials** but a **different child name**
3. Each child gets its own set of sensors with unique entity IDs

### Options (Display Name)

1. Go to **Settings** → **Devices & Services**
2. Find **ElternPortal API** and click **Configure**
3. Change the **display name** (affects friendly name only, not entity IDs)

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

## 🛡️ Connection Resilience

The integration includes built-in protection against intermittent connection issues:

- **Stale-data protection**: If the portal returns empty data but previously had valid entries, the integration keeps the last good data instead of showing empty sensors
- **Auto session recovery**: When a session expires or drops, the integration automatically creates a fresh session and retries
- **Graceful degradation**: If individual endpoints fail but others succeed, partial data is preserved
- **Max retry threshold**: After 3 consecutive empty fetches, the empty data is accepted (handles legitimate cases like end of school year)

Check the Home Assistant logs for messages like:
- `ElternPortal returned empty critical data (attempt 1/3)` – stale-data protection active
- `Fresh session recovered X critical entries!` – auto-recovery succeeded
- `Auth recovery failed. Keeping last good data.` – using cached data

---

## 📊 Sensor Details

Each sensor shows the **number of entries** as its state. Attributes contain **metadata only** – large text fields (body, content, links) are stripped to stay under the Home Assistant recorder limit of 16KB.

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
child_name: "MAX"
class_name: "7B"
last_fetch: "2026-03-04T10:28:53.344191"
```

### Example: Elternbriefe Sensor

**State:** `94` (number of letters)

**Attributes:**
```yaml
entries:
  - number: "#94"
    title: "Elternabend am 18. März"
    date: "03.03.2026 14:08:24"
    acknowledged: false
    has_file: true
    classes: "Klasse/n: 7B"
  - number: "#93"
    title: "Terminübersicht Elternabende"
    date: "27.02.2026 14:53:35"
    acknowledged: true
    has_file: true
    classes: "Klasse/n: 7B"
unread_count: 3
child_name: "MAX"
class_name: "7B"
last_fetch: "2026-03-04T12:41:17.144487"
```

> 💡 The `unread_count` attribute shows the number of unacknowledged letters. The `body` and `link` fields are intentionally excluded from attributes to prevent recorder database issues.

### Example: Schwarzes Brett Sensor

**State:** `4` (number of entries)

**Attributes:**
```yaml
entries:
  - title: "Nachhilfe-Angebot"
    date: "11.03.2025 00:00:00"
    archived: false
    has_attachment: true
    attachment: "Nachhilfe.docx herunterladen"
  - title: "Leistungsstandbericht"
    date: "12.02.2026 - 12.02.2026"
    archived: true
child_name: "MAX"
class_name: "7B"
last_fetch: "2026-03-04T12:41:17.144487"
```

> 💡 The `content` field is excluded from Schwarzes Brett attributes. Only metadata (title, date, archived status, attachment info) is stored.

---

## 🏠 Dashboard Examples

### Upcoming Exams Card (Markdown)

```yaml
type: markdown
title: 📝 Nächste Schulaufgaben
content: >
  {% set exams = state_attr('sensor.gymnasium_musterstadt_max_schulaufgaben', 'entries') %}
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
  {% set unread = state_attr('sensor.gymnasium_musterstadt_max_elternbriefe', 'unread_count') %}
  {% set letters = state_attr('sensor.gymnasium_musterstadt_max_elternbriefe', 'entries') %}
  **{{ unread }} ungelesene Briefe**
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
  {% set surveys = state_attr('sensor.gymnasium_musterstadt_max_umfragen', 'entries') %}
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
| **Sensors show 0** | Check HA logs for "empty critical data" messages – may be a session issue |
| **CSRF token error** | The portal may be temporarily unavailable – retry later |
| **Wrong child name** | Entity IDs are set at setup – delete & re-add integration to change |
| **Recorder 16KB warning** | Should not occur – if it does, check for custom parser changes |
| **"Keeping last good data"** | Normal behavior – integration auto-recovers on next fetch |

### Enable Debug Logging

```yaml
logger:
  default: info
  logs:
    custom_components.elternportal: debug
```

---

## 📋 Changelog

### v2.3.0
- 🛡️ **Stale-data protection** – sensors keep last good data when portal returns empty results
- 🔁 **Auto session recovery** – automatic fresh session creation on connection loss / auth expiry
- ⏱️ **Connection timeout** – 30s total / 10s connect timeout prevents hanging requests
- 🔍 **Total failure detection** – raises proper error when ALL endpoints fail (vs. partial success)
- 📝 **Enhanced logging** – fetch service logs entry counts, coordinator logs recovery attempts
- 🐛 **Fixed**: Sensors dropping to 0 when ElternPortal session expires mid-operation

### v2.2.0
- 🧒 **Child name in setup flow** – set name/short code during initial setup for consistent entity IDs
- 👨‍👩‍👧‍👦 **Multi-child support** – add integration multiple times with different child names
- 📏 **Recorder-safe attributes** – large text fields stripped to stay under 16KB limit
- 🆕 **Unread count** – `unread_count` attribute on Elternbriefe sensor
- 🐛 **Fixed**: OptionsFlow compatibility with HA 2024.x+

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