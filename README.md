[🇪🇸 Leer en español](README.es.md)

# Airzone Control Integration (Local API) – Home Assistant

**Unofficial** integration to control and monitor Airzone systems using the **Local API** (port 3000). Works **without cloud** and is designed for multi‑zone installations and/or multiple Airzone devices on the same network.

Compared to the official integration, **Airzone Control**:
- Supports **multiple devices** (Airzone Webserver / Aidoo Pro / Aidoo Pro Fancoil), each with its zones and sensors.
- Exposes more entities: zone temperature, errors, webserver data (firmware, Wi‑Fi signal, channel), **IAQ** (CO₂, PM, TVOC, pressure, score), profiles/diagnostics, etc.
- Groups entities by **device** and **zone**, making dashboards and automations easier.
- Provides a **“Master mode”** selector (stop/heating) when the device supports it.

> **Important:** the Local API lives in the **Airzone Webserver** or **Aidoo Pro**. Controllers like **Flexa 3** alone **do not** expose the REST API. You need Webserver/Aidoo in the installation.

---

## ✨ What’s new (v1.7.0)

### Local API update for newer Airzone schemas
- Improved Local API prefix detection for more Airzone Webserver/Aidoo variants.
- Version discovery now uses `POST /version` for more reliable schema detection.
- The coordinator now populates `systems` properly and exposes `get_system()` consistently.
- Conservative driver registration via `/integration` when supported by the device.

### New dynamic entities for supported hardware
The integration now creates new entities only when the connected device actually exposes those fields:
- **System sensors**: energy consumption, energy produced, heat generation power, UE consumption.
- **Zone sensors**: battery level, coverage, sleep timer, air quality, DHW temperature, DHW setpoint.
- **Zone selects**: sleep, vertical/horizontal slats, vertical/horizontal swing, ERV mode.
- **Binary sensors**: low battery, antifreeze.
- **ACS/DHW switches**: DHW power and DHW powerful mode.

### Safe upgrade for existing installations
- Existing climate/group/system logic is preserved.
- Installations that do not expose ACS, slats, ERV or energy fields remain unchanged.
- This release is still **Local API only**. Cloud API support is not included yet.

---

## ✨ What’s new (v1.6.2)

### 🧩 Master thermostat & “Hotel” buttons (turn all on/off)
- The **master thermostat** now reflects the system state correctly: it is **ON if at least 1 zone is ON**, and only turns OFF when **all** zones are OFF.
- Changing the master **target temperature** applies the setpoint to **all zones (ON or OFF)** **without powering them on**.
- **Hotel buttons** (Turn all ON / Turn all OFF) are more reliable: paced commands + verification/retries so zones reach the expected final state.

### 🩺 Diagnostics download (now working)
From the device page you can click **“Download diagnostics”** to generate a JSON snapshot of the integration (useful for debugging/reporting without digging through logs).

### 🧪 Debug attributes: `systemID`, `zoneID` (and `group_id` when applicable)
Entities expose the real Airzone identifiers as attributes. Useful to:
- quickly verify which zone is which,
- debug automations,
- cross-check data against the API.

### ℹ️ More information in the device page
When returned by the API, the **Device information** card may show:
- serial number,
- firmware version.

### 🛑 Errors: from “Error X” to human-readable text + translations
- The error sensor now shows a readable description (e.g., “Low battery”, “Communication failure”, etc.).
- Debug details remain available as attributes (codes/lists).
- Special case: **Error 8 ⇒ “Low battery”**.
- Error descriptions are translated across the integration languages.

### 📈 Long-term statistics restored (`state_class`)
- “Regular” sensors (temperature, humidity, demand, etc.) correctly declare `state_class` and units/classes again.
- Same for IAQ sensors (CO₂, TVOC, PM2.5, PM10, pressure), removing warnings and restoring statistics/history.

### 🛠️ Robustness: don’t crash on missing `zone_id`
Fixed a case where an entity could end up with a missing `zone_id` (None) and trigger errors in the update loop. It’s now handled safely.

> Note: **Global Mode** remains independent. Neither the master thermostat nor the Hotel buttons ever change the global mode.


## ✨ What’s new (v1.6.1)

### ✅ Global Mode: 1:1 behavior with the Airzone app
From this version on, **Global Mode** matches the real Airzone app behavior:

- Global Mode state is based on the `mode` field (global mode), **not** on whether zones are powered on/off (`on`).
  - Example: if the system is in **Heat** but all zones are `on=0`, Global Mode must still show **Heat** (because heat is allowed).

- When selecting **Off/Stop** (global):
  - applies Stop `mode` globally **and**
  - forces **all zones to `on=0`** (off).
  - Result: zones cannot be turned on until the administrator removes the stop.

- When selecting **Heat / Cool / Fan / Dry / Auto** (depending on what your API exposes):
  - updates **only** the global `mode` (broadcast),
  - **without powering zones on** (zones keep their current `on` state).
  - Result: the mode is “allowed”, while each zone remains independent.

### 🧠 More consistent UI
When Global Mode is **Stop/Off**, it is normal for individual thermostats/mode selects to show **only valid options** (for example, only “Off”). This prevents selecting modes the system won’t accept while global lock is active.

---

## ✨ What’s new (v1.6.0)

### Added
- Zone thermostats (one `climate` per zone).
- Master thermostat (per Airzone system).
- **Group thermostats** (one `climate` per group):
  - Change temperature, mode and **turn on/off**.
  - Applies the action to all zones in the group.
- Additional entities (sensors/selects/switches/buttons) depending on your installation.

---

## 📦 Installation (quick)

1. Copy this folder into:
   `config/custom_components/airzone_control/`
2. Restart Home Assistant.
3. Add the integration from:
   **Settings → Devices & Services → Add integration → Airzone Control**

---

## ⚙️ Configuration

### Basic setup
- **Host**: Airzone webserver IP
- **Port**: webserver port
- The integration auto‑detects the API prefix (and allows selecting it manually if needed).

### Options
Open:
**Settings → Devices & Services → Airzone Control → (gear icon) Options**

You can configure:
- **Polling interval**
- **Groups (easy UI)**
- **Groups (advanced JSON)**

---

## 👥 Group thermostats

### Easy UI (recommended)
In **Options**, you will find several group “slots” (default: 8):
- **Group X – Name**
- **Group X – Zones** (checkbox list)

Leave `Groups (advanced JSON)` empty, save, and the new `climate.*` entities for groups will appear.

> Note: saving options reloads the integration automatically and groups appear without restarting Home Assistant.

### Advanced JSON (no practical limit)
If you fill `Groups (advanced JSON)`, it has priority and UI groups are ignored.
Format:

```json
[
  {
    "id": "day_area",
    "name": "Day area",
    "zones": ["1/3", "1/4", "1/5"]
  },
  {
    "id": "night_area",
    "name": "Night area",
    "zones": ["1/1", "1/2"]
  }
]
```

---

## ✅ Requirements

- **Airzone Webserver** or **Aidoo Pro/Fancoil** with **Local API v1** (port **3000**).
- Home Assistant must reach the device IP (same LAN or proper routing/firewall rules).

**Quick API check:**
- In a browser:
  - `http://<IP>:3000/api/v1/webserver` → device JSON
  - `http://<IP>:3000/api/v1/version` → `{"schema":"1.xx"}`

---

## 📦 Installation (detailed)

### HACS (recommended)
1. **HACS → Integrations →** ⋮ **Custom repositories**
2. Add `https://github.com/tecnoyfoto/airzone_control` (*Integration*)
3. Install **Airzone Control** and **restart** Home Assistant

### Manual
1. Copy `custom_components/airzone_control` into your HA configuration folder:

```
custom_components/
  └── airzone_control/
      ├── __init__.py
      ├── manifest.json
      ├── config_flow.py
      ├── const.py
      ├── coordinator.py
      ├── api_modes.py
      ├── climate.py
      ├── i18n.py
      ├── sensor.py
      ├── binary_sensor.py
      ├── select.py
      ├── switch.py
      ├── button.py
      └── translations/
          ├── en.json
          ├── es.json
          ├── ca.json
          ├── fr.json
          ├── it.json
          ├── pt.json
          ├── de.json
          ├── gl.json
          ├── nl.json
          └── eu.json
```

2. **Restart** Home Assistant.

---

## ⚙️ Configuration (detailed)

### mDNS discovery
- Go to **Settings → Devices & Services → Discovered** and click **Configure** on each Airzone device.
- If your network blocks mDNS (VLAN, Wi‑Fi isolation, etc.), use manual setup.

### Manual setup (IP)
1. **Settings → Devices & Services → + Add Integration → Airzone Control**
2. Host = **Webserver/Aidoo IP**, Port = **3000**

### Multiple installations
- Add one entry per Airzone device.
- The integration creates entities for zones and sensors per device.

---

## 🗂️ Entities

### Climate (per zone)
- On/off, setpoint, available modes depending on API (Heat/Cool/Dry/Fan/Auto/Stop).
- Next: fully dynamic fan speed mapping (`speed/speeds/speed_values/speed_type`).

### Sensors
- **Zone:** temperature, errors, (others if exposed)
- **System:** errors, profile/diagnostics, zone count, etc.
- **Webserver:** firmware, Wi‑Fi quality, RSSI, channel, interface, MAC, type
- **IAQ:** CO₂, PM2.5, PM10, TVOC, pressure, score/index (if Airzone IAQ sensors exist)

---

## 🔁 Migration (Breaking change)

To support multiple devices without collisions, some `unique_id` values became unique per system/zone. Home Assistant binds `entity_id` to `unique_id`, so some `entity_id` may change after updating.

If you see “Entity not found”:
1. **Settings → Entities**, filter by **Integration: Airzone Control**, find the new entity.
2. If needed, edit the entity and set your preferred **Entity ID**.
3. Update automations/dashboards accordingly.

> Tip: make a **backup** before updating.

---

## 🛠️ Troubleshooting

- **No connection:** use Webserver/Aidoo IP (not the controller IP), check `/webserver` and `/version`, review firewall/VLAN.
- **Missing modes:** depends on what the API exposes. Check the Airzone app profile or share `/hvac` JSON.
- **Not discovered:** add by IP (mDNS may be blocked).

---

## 🧭 Quick compatibility

- **Yes:** Airzone **Webserver** (Hub/5G/Wi‑Fi), **Aidoo Pro**, **Aidoo Pro Fancoil** with Local API v1.
- **No:** **Flexa 3** alone (without Webserver/Aidoo).
- **Port:** 3000. Main endpoints: `/api/v1/webserver`, `/api/v1/version`, `/api/v1/hvac`, `/api/v1/iaq`.

---

## 🌐 Available translations

- Spanish 🇪🇸
- English 🇬🇧
- Catalan 🇨🇦
- French 🇫🇷
- Italian 🇮🇹
- Portuguese 🇵🇹
- German 🇩🇪
- Galician 🇬🇷
- Dutch 🇳🇱
- Basque 🇪🇺

---

## 🤝 Contributing

Suggestions, issues and PRs:
**Repo:** https://github.com/tecnoyfoto/airzone_control

---

### 📄 Changelog

See full version history in [`CHANGELOG.md`](./CHANGELOG.md)

## 📜 License
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
