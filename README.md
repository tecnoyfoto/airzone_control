# Airzone Control Integration

[🇪🇸 Lee este documento en español](README.es.md)

This custom integration allows controlling and monitoring Airzone HVAC systems via their local API (default port 3000). Unlike the official Home Assistant integration, **Airzone Control**:

- Supports multi-zone setups.
- Exposes extra sensors (temperature, humidity, battery, firmware, IAQ, diagnostics, power consumption).
- Groups entities by device.
- Provides a manual “Master Mode” selector to override the central thermostat.

---

## 📦 Installation

### Via HACS (recommended)

1. In Home Assistant, go to **HACS → Integrations**.  
2. Click the ⋮ menu (top right) → **Custom repositories**.  
3. Add:
   - **Repository**: `https://github.com/tecnoyfoto/airzone_control`
   - **Category**: **Integration**  
4. Click **Add**.  
5. Back in **HACS → Integrations**, search for **Airzone Control**, click **Install**, and reboot Home Assistant.

### Manual

> Only if you don’t use HACS.  

1. Download or clone to `<config_dir>/custom_components/airzone_control` so that your tree looks like:

   ```
   custom_components/
   └── airzone_control/
       ├── __init__.py
       ├── manifest.json
       ├── config_flow.py
       ├── const.py
       ├── coordinator.py
       ├── climate.py
       ├── sensor.py
       ├── switch.py
       ├── select.py
       └── translations/
           ├── en.json
           ├── es.json
           └── ca.json
   ```
2. Restart Home Assistant.  
3. Go to **Settings → Devices & Services → + Add Integration**, search **Airzone Control**, enter your Webserver IP and port (`3000`), then submit.

---

## ⚙️ Configuration

- On startup the integration auto-discovers all zones (1–8 by default).
- Global “Airzone System” device groups system-wide sensors and switches.
- A “Master Mode” selector to force **Stop** ⛔ or **Heat** 🔥 on the system.

---

## 🗂️ Entities

### Climate
- One `climate` entity per zone for On/Off, mode, setpoint and fan/swing controls.

### Sensors
- **Zone sensors**: temperature, humidity, battery level, firmware, heat/cold/air demand, open-window, dual setpoints, power consumption.
- **IAQ sensors**: CO₂, PM2.5, PM10, TVOC, pressure, index, score, ventilation mode.
- **System sensors**: global mode, fan speed, sleep mode, system ID, firmware, errors, units.
- **Aggregate**: “Zones amb Bateria Baixa” lists zones with low battery.

### Switches
- **Airzone System On/Off**
- **Airzone ECO Mode** (if supported by your API)

### Selector
- **Airzone Manual Mode** to override the master thermostat (Stop ⛔ or Heat 🔥).

---

## 📝 Changelog

### v1.1.1 – Final HACS compliant
- Reorganized to `custom_components/airzone_control/`
- Bumped `version` to **1.1.1**

### v1.1.0 – HACS support
- Added `hacs.json` with `"content_in_root": false`.
- Authors field set to **Tecnoyfoto**.

For full history, see [Releases][release-link].

---

## 💡 FAQ

- **Only some zones report humidity?**
  Some thermostats don’t report humidity or do so intermittently (low battery or comms issues).
- **What is “Error 8”?**
  Indicates a Lite thermostat communication problem, often low battery.

---

## 🤝 Contributing

PRs and issues are welcome at [GitHub][repo-link].

---

## 📜 License

This project is licensed under [CC BY-NC-SA 4.0][license-link].

---

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-orange  
[hacs-link]: https://github.com/hacs/integration  
[release-badge]: https://img.shields.io/github/v/release/tecnoyfoto/airzone_control?label=release  
[release-link]: https://github.com/tecnoyfoto/airzone_control/releases  
[repo-link]: https://github.com/tecnoyfoto/airzone_control  
[license-link]: https://creativecommons.org/licenses/by-nc-sa/4.0/
