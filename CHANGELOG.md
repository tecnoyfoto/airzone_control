[🇪🇸 Leer en español](CHANGELOG.es.md)

# Changelog

## 1.6.1 - 2025-12-21

### Fixed
- **Global Mode** now matches the Airzone app behavior.
  - Global mode state is based on `mode` (not on `on`).
  - **Off/Stop**: applies global Stop `mode` and forces `on=0` on all zones.
  - **Heat/Cool/Fan/Dry/Auto**: updates only the global `mode` (broadcast) without powering zones on automatically.
- More consistent UI: when Global Mode is Stop, zones only show valid options.

## 1.6.0
- Zone thermostats, master thermostat, group thermostats and extra entities depending on the installation.

## 1.5.1
- Internationalization (i18n) updates and new languages.

## 1.5.0
- Per-zone selects (Mode, Fan speed, IAQ ventilation), Global Mode select, Webserver sensors and “Hotel” buttons.
