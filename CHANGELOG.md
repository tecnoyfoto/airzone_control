[Leer en español](CHANGELOG.es.md)

# Changelog

## 1.9.0 - 2026-08-01

### Added

- Automatic discovery of Local API controllers through Zeroconf, while keeping manual IP configuration available.
- Reauthentication flow for renewing Cloud API entry credentials.
- TLS verification option for Local API connections; it remains enabled by default.
- Independent option to register the integration driver on compatible devices; it remains disabled by default.
- Additional transport and source-status information in support diagnostics.

### Changed

- HTTP connections reuse the Home Assistant managed session and follow the current config-entry lifecycle.
- Entity availability reflects the state of its specific source: HVAC, IAQ, webserver or Cloud device.
- Cloud installation discovery supports paginated results.
- The `complement_local` and `custom` Cloud profiles require at least one selected device before saving.
- The configurable minimum polling interval is `5` seconds for Local API and `15` seconds for Cloud API; the default Cloud value remains `30` seconds.
- Optional entities are created only when the device provides their corresponding fields.
- Mode, fan-speed and air-quality states use stable identifiers and Home Assistant translations.
- English is now the fallback language when a translation is unavailable.
- Cloud energy counter state classes have been adjusted to match the meaning of each field.
- The system switch turns all its zones on or off, and follow-master mode restores its last state after a restart.

### Fixed

- HVAC activity calculation for zone, system and group thermostats now uses the actual demand reported by the device.
- Valid numeric zero values are preserved in sensors and Cloud data.
- Last valid state is retained without presenting a source as available when its update has failed.
- Logical groups, zone references and duplicate identifiers are validated before options are saved.
- Duplicate tasks are avoided while synchronizing zones with the master zone.
- Transport selection and periodic device metadata refresh have been improved.
- Corrected the Zeroconf discovery patterns in the manifest.

### Notes

- Cloud API remains read-only.
- Files generated for support omit configuration data and identifiers that are not needed to analyze integration behavior.
- HTTP response logging has been simplified to retain only the information needed for troubleshooting.

## 1.8.0 - 2026-05-05

### Added

- First public Cloud API phase.
- New Cloud API config flow with email/password authentication.
- Cloud profiles:
  - `full`: expose all supported Cloud categories.
  - `complement_local`: complement an existing Local API entry with Cloud-only devices.
  - `custom`: manually choose Cloud categories and devices.
- Cloud category filters:
  - `climate_zones`
  - `energy`
  - `iaq`
  - `acs`
  - `aux`
- Cloud device selection by stable `cloud_device_id`.
- Cloud energy meter support for `az_energy_clamp`.
- Cloud IAQ support for `az_airqsensor`.
- Cloud IAQ field mapping for CO2, TVOC, pressure, PM1.0, PM2.5, PM10, IAQ score and textual quality.
- Cloud energy meter mapping for imported/returned energy, per-phase energy, power, current and voltage.
- Read-only Cloud climate entities when Cloud climate zones are enabled.
- Option to include or hide IAQ sensors linked to Cloud systems/zones.
- Support for running Local API and Cloud API entries side by side without unique ID collisions.

### Changed

- Cloud entries default to a conservative `30` second polling interval.
- Complementary Cloud entries no longer expose the Cloud webserver device when climate zones are disabled, avoiding duplicated Webserver/Flexa devices.
- Cloud IAQ and Cloud energy meter data keep the last valid state when a single Cloud status fetch fails or returns incomplete data.
- Cloud device selection is no longer preselected by default in complementary/custom profiles.
- Leaving Cloud device selection empty in complementary/custom profiles publishes no Cloud devices for that entry.
- Cloud zone/system device info now uses Cloud-oriented models instead of Local API model names.
- Diagnostics redact email and Cloud user/installation/webserver/device identifiers.
- Cloud identifiers are no longer exposed as entity attributes for IAQ and energy meter sensors.
- Translation files now include all new Cloud config/options keys; secondary languages may use English fallback text until reviewed.

### Fixed

- Restored the `open_window` binary sensor when the Local API exposes it.
- IAQ ventilation binary sensor now uses explicit `needs_ventilation` / `need_ventilation` fields before falling back to the CO2 threshold heuristic.
- Cloud complementary mode can expose energy/IAQ devices without creating duplicated thermostats or webserver entities.

### Notes

- Cloud API write support is intentionally disabled in this release.
- `select`, `switch` and `button` entities are not created for Cloud entries.
- Energy Dashboard classification for some Cloud meter fields may change later once Airzone counter reset behavior is confirmed.

## 1.7.0 - 2026-04-12

### Added

- Local API compatibility layer for newer Airzone schemas and prefixes.
- System sensors: `energy_consump`, `energy_produced`, `power_gen_heat`, `consumption_ue`.
- Zone sensors: `battery`, `coverage`, `sleep`, `aq_quality`, `acs_temp`, `acs_setpoint`.
- Zone selects: `sleep`, `slats_vertical`, `slats_horizontal`, `slats_vswing`, `slats_hswing`, `erv_mode`.
- Binary sensors: `battery_low`, `antifreeze`.
- ACS/DHW switches: `acs_power`, `acs_powerful`.
- English and Spanish translations for the new entities.

### Changed

- System data is now populated in the coordinator and exposed through `get_system()`.
- Version detection now uses `POST /version`.
- Conservative `/integration` driver registration is attempted when supported.
- New entities are created dynamically only when the hardware exposes the required fields.

## 1.6.2 - 2025-12-31

### Added

- Diagnostics download from the device page.
- Debug attributes for `systemID`, `zoneID` and `group_id` where applicable.
- More device information when provided by the API, including serial number and firmware version.
- Human-readable error descriptions.
- Restored long-term statistics metadata for regular and IAQ sensors.

### Fixed

- Master thermostat shows ON when at least one zone is ON.
- Master target temperature updates no longer power zones on.
- Hotel buttons are more reliable.
- Avoid update loop errors when an entity has no `zone_id`.

## 1.6.1 - 2025-12-21

### Fixed

- Global Mode now matches the Airzone app behavior.
- Stop/Off applies global Stop mode and forces all zones off.
- Heat/Cool/Fan/Dry/Auto changes only the global mode without powering zones on.
- Zone UI shows only valid options when Global Mode is stopped.

## 1.6.0

- Added zone thermostats, master thermostat, group thermostats and extra entities depending on the installation.

## 1.5.1

- Internationalization updates and new languages.

## 1.5.0

- Added per-zone selects, Global Mode select, Webserver sensors and Hotel buttons.
