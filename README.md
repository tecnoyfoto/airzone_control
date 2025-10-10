# Airzone Control (Local API) – Home Assistant

[🇪🇸 Leer en español](README.es.md)

**Unofficial** integration to control and monitor Airzone via the **Local API** (port 3000). It works **fully offline** and is designed for multi-zone setups and/or multiple Airzone devices on the same network.

Compared to the official integration, **Airzone Control**:
- Supports **multiple devices** (Airzone Webserver / Aidoo Pro / Aidoo Pro Fancoil), each with its own zones and sensors.
- Exposes richer entities: zone temperature, errors, webserver info (firmware, Wi-Fi signal/channel), **IAQ** (CO₂, PM, TVOC, pressure, score), profiles/diagnostics, etc.
- Groups entities per **device** and **zone**, making dashboards and automations easier.
- Provides a **“Master mode”** selector (stop/heat) when supported by the device.

> **Note:** the Local API runs on **Airzone Webserver** or **Aidoo Pro**. Controllers like **Flexa 3** alone **do not** expose the REST API. You need a Webserver/Aidoo in your installation.

---

## ✨ What’s new (v1.5.0)

- New zone `select` entities: **Mode**, **Speed**, and **IAQ Ventilation**.
- **Global Mode** selector to change all zones at once.
- New **Webserver sensors**: cloud status, firmware, type, Wi-Fi quality, and more.
- Redesigned **Hotel buttons**: power on/off all zones and copy setpoint.
- All new entities include translations and stable `unique_id`s.
- Extended and tested support for Local API **v1.76 and v1.77**.
- General improvements to entity structure, multi-device support, and robustness.

- **Multi-device support:** add **multiple Airzone devices** on the same network (one config entry per device).
- **mDNS discovery + manual add:** devices show up under *Discovered* when your network allows it; otherwise, add them by IP.
- **More robust** handling of capabilities and Local API variants.

> 🧨 **Breaking change:** to avoid collisions across systems/zones, some internal `unique_id` values changed. Home Assistant may update certain existing `entity_id` (see **Migration**).

---

## ✅ Requirements

- **Airzone Webserver** or **Aidoo Pro/Fancoil** with **Local API v1** (port **3000**).
- The device must be reachable from your HA host (same LAN or proper routing/firewall rules).

**Quick API check:**
- In a browser:  
  - `http://<IP>:3000/api/v1/webserver` → device info JSON  
  - `http://<IP>:3000/api/v1/version` → `{"schema":"1.xx"}`  
- If they don’t respond, that device isn’t exposing the Local API (or there’s a network/firmware issue).

---

## 🧩 Installation

### Via HACS (recommended)
1. **HACS → Integrations →** ⋮ **Custom repositories**  
2. Add `https://github.com/tecnoyfoto/airzone_control` as **Integration**  
3. Install **Airzone Control** and **restart** Home Assistant

### Manual
1. Copy `custom_components/airzone_control` into your HA config:

custom_components/
  └── airzone_control/
    ├── init.py
    ├── manifest.json
    ├── config_flow.py
    ├── const.py
    ├── coordinator.py
    ├── api_modes.py
    ├── climate.py
    ├── sensor.py
    ├── binary_sensor.py
    ├── select.py
    ├── switch.py
    ├── button.py
    └── translations/
      ├── en.json
      ├── es.json
      └── ca.json

2. **Restart** Home Assistant.

---

## ⚙️ Configuration

### mDNS discovery
- Go to **Settings → Devices & services → Discovered** and click **Configure** on each Airzone device.
- If your network doesn’t allow mDNS (VLANs, AP isolation, guest SSIDs…), use manual setup.

### Manual add (IP)
1. **Settings → Devices & services → + Add integration → Airzone Control**  
2. Host = **Webserver/Aidoo IP**, Port = **3000**

### Multiple installations
- Repeat discovery/manual add **once per device**.  
- The integration creates one config entry per device, with its **zones** and **sensors** underneath.

---

## 💡 Entities & features

### Zone climate
- On/off, target temperature, hvac modes based on what the API exposes (Heat/Cool/Dry/Fan/Auto/Stop).  
- Next version: **dynamic fan speeds** (map `speed/speeds/speed_values/speed_type`).

### Sensors
- **Zone:** Temperature, errors (others when exposed by the API).  
- **System:** Errors, profile/diagnostics, number of zones, etc.  
- **Webserver:** Firmware, Wi-Fi quality, RSSI, channel, interface, MAC, type.  
- **IAQ:** CO₂, PM2.5, PM10, TVOC, pressure, score/index (when Airzone IAQ sensors are present).

---

## 🔁 Migration (Breaking change)

To support **multiple devices** safely, some `unique_id` values are now **unique per system/zone**. Since Home Assistant binds `entity_id` to `unique_id`, **some `entity_id` may change** after updating.

**If you see “Entity not found”:**
1. **Settings → Entities**, filter by **Integration: Airzone Control** to find the new entity.  
2. If you want to keep the old name, edit the entity and change its **Entity ID**.  
3. Update automations/dashboards where warnings appear.

*Tip:* take a **backup** before updating.

---

## 🛠 Troubleshooting

- **Cannot connect:** use the **Webserver/Aidoo IP** (not the controller), confirm `/webserver` and `/version`, check firewall/VLANs.  
- **Missing modes:** they depend on what the API exposes for that zone. Check the profile in the Airzone app or share the `/hvac` JSON.  
- **Not discovered:** add by IP (mDNS may be blocked in your network).

---

## 🧭 Compatibility (quick)

- **Yes:** Airzone **Webserver** (Hub/5G/Wi-Fi), **Aidoo Pro**, **Aidoo Pro Fancoil** with Local API v1.  
- **No:** **Flexa 3** alone (without Webserver/Aidoo) — does not expose the REST API.  
- **Port:** 3000. Main endpoints: `/api/v1/webserver`, `/api/v1/version`, `/api/v1/hvac`, `/api/v1/iaq`.

---

## 📈 Roadmap (1.5.0)

- **Dynamic fan speeds** (per-zone select + sync with `climate.fan_mode`).  
- **Firmware update from Home Assistant** (when supported by device/API).  
- Diagnostics improvements.

---

## 🤝 Contributing

Issues and PRs are welcome:  
**Repo:** https://github.com/tecnoyfoto/airzone_control

---


---

### 📄 Changelog

See the full release history in [`CHANGELOG.md`](./CHANGELOG.md)


## 📜 License
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
