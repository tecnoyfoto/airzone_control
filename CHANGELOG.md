[🇪🇸 Leer en español](CHANGELOG.es.md) • [🇬🇧 Read this in English](CHANGELOG.md)

# Changelog

## [1.6.0] - 2025-12-17

- Added the **master thermostat** (`climate`) per system, to control all zones from a single entity.
- Added **group thermostats** (`climate`) to control multiple zones as one.
- Added an **Options UI** to create groups using:
  - Group name + zone selection (checkbox list)
  - Advanced JSON mode with no practical group limit
- Groups now support **turn on/off** at group level.
- Saving options triggers an **automatic integration reload**, so new group entities appear without restarting Home Assistant.
- Improved translations for configuration and options.


## [1.5.1] - 2025-10-11

### 🌐 Internationalization (i18n)
- Fully updated translations for:
  - 🇪🇸 Spanish
  - 🇬🇧 English
  - 🇨🇦 Catalan
  - 🇫🇷 French
  - 🇮🇹 Italian
  - 🇵🇹 Portuguese
  - 🇩🇪 German
- Added support for new languages:
  - 🇬🇷 Galician (`gl`)
  - 🇳🇱 Dutch (`nl`)
  - 🇪🇺 Basque (`eu`)
- Unified `translation_key` structure for all entities (`sensor`, `select`, `button`, etc.).
- Minor corrections in entity names.
- No functional changes to the integration logic.


## [1.5.0] - 2025-10-10

### 🚀 Added
- New `select` entities:
  - **Zone mode** (`select.zone_mode`): changes only the mode of the zone.
  - **Global mode** (`select.global_mode`): applies a mode to all zones at once.
  - **Zone fan speed** (`select.zone_speed`): available for ventilation/ERV systems. Supports `speed_values`, `speeds`, and `speed`, including `Auto`.
  - **IAQ ventilation** (`select.iaq_ventilation`): selector for `iaq_mode_vent` in IAQ sensors.
- Webserver sensors under `Airzone Webserver` device:
  - `cloud_connected`, `ws_version`, `transport`, `ws_mac`, `ws_interface`, `ws_type`, `ws_firmware`, `lmachine_firmware`, `ws_wifi_channel`, `ws_wifi_quality`, `ws_wifi_rssi`, `ws_wifi_quality_text`.
- Redesigned Hotel buttons:
  - `Turn all off`, `Turn all on`, and `Copy setpoint` via `PUT /hvac` using per-zone iteration and error handling.

### 🌐 Internationalization (i18n)
- All new entities use `_attr_translation_key`.
- Updated translation files: `en.json`, `es.json`, `ca.json`.
- Dynamic labels shown according to HA system language:
  - Modes (heat, cool, dry, etc.), speeds (auto, low, medium, high...), yes/no, etc.
- To correctly apply new names:
  1. Set your HA language in `Settings → System → General → Language`.
  2. Restart HA.
  3. Click “Restore default name” on old entities.

### 🧱 Entity structure & stability
- All new entities have proper `unique_id` and `device_info`.
- Grouped under the correct device: HVAC system, Zone, IAQ sensor or Webserver.
- Prevents orphaned or misplaced entities in the UI.

### 🔧 Robustness & internal improvements
- Aliases for firmware-dependent keys (`temp_outdoor`, `outdoorTemp`, `iaq_home`, etc.)
- Safe type conversions (`int`, `float`, unit normalization).
- Removed internal code duplication (helpers, bases).
- Dynamic construction of modes and speeds: deduplication, ordering, fallback, safe inclusion of `off`.
- Debug logs under `custom_components.airzone_control`.
- IAQ & Webserver sensors created only if values are present.
- Fewer zombie or empty entities.

### 🧪 API compatibility
- Adapted for API versions 1.76 and 1.77.
- Supports new fields in `/hvac`, `/iaq`, and `/webserver`.
- Backwards-compatible with older installations (no breaking changes).

### 🌡️ HVAC system
- External temperature override supported via any HA sensor.
  - Auto-converts °F/K → °C.
  - Attributes: `source`, `override_entity`.
- New sensors:
  - `mc_connected`, `system_firmware`, `system_type`, `system_technology`, `manufacturer`, `num_airqsensors`, `return_temp`, `work_temp`, `outdoor_temp`.
  - `cond_risk_master` added as placeholder.

### 🧬 IAQ
- Entities created only if values exist.
- New IAQ sensors:
  - `pressure_value`, `abs_humidity_gm3`, `humidex_master`, `humidex_master_pct`, `needs_ventilation`, `iaq_index`, `iaq_index_text`, `iaq_home_text`, etc.

### 🌍 Zone
- Conditional creation based on available keys.
- New per-zone sensors:
  - Temperature, humidity, demands (`air`, `cold`, `heat`, `floor`), state (`open_window`, `errors`), `eco_adapt`, `units`.
- Critical fix: broken ternary in `ZoneUnitsSensor` now corrected.

### 🛠 Changed
- Clearer internal names (`unique_id`, `translation_key`).
- WiFi quality labels added (Webserver).
- Integration panel now cleaner and more consistent.

### ⚠️ Breaking / Known Issues
- If your HA system is not in Spanish and entities appear in Spanish:
- Change system language in `Settings → System → Language`, restart HA, and click “Restore default name”.
- Legacy entities may appear in gray (unavailable). You can safely delete them if no longer needed.
