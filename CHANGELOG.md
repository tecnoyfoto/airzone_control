[🇪🇸 Leer en español](CHANGELOG.es.md)

# Changelog

## 1.7.0 - 2026-04-12

### Added
- New Local API compatibility layer for newer Airzone schemas and prefixes.
- System sensors: `energy_consump`, `energy_produced`, `power_gen_heat`, `consumption_ue`.
- Zone sensors: `battery`, `coverage`, `sleep`, `aq_quality`, `acs_temp`, `acs_setpoint`.
- Zone selects: `sleep`, `slats_vertical`, `slats_horizontal`, `slats_vswing`, `slats_hswing`, `erv_mode`.
- Binary sensors: `battery_low`, `antifreeze`.
- ACS/DHW switches: `acs_power`, `acs_powerful`.
- English and Spanish translation entries for the new entities.

### Changed
- System data is now populated in the coordinator and exposed through `get_system()`.
- Version detection now uses `POST /version`.
- Conservative `/integration` driver registration is attempted when supported.
- New entities are created dynamically only when the hardware exposes the required fields, keeping existing installations stable.

## 1.6.2 - 2025-12-31

### Added
- **Diagnostics download**: “Download diagnostics” now generates a JSON snapshot of the integration for easier debugging/reporting.
- **Debug attributes**: entities expose `systemID` and `zoneID` (and `group_id` where applicable).
- **More device information** (when provided by the API): serial number and firmware version.
- **Human-readable errors**: error sensor values are now readable descriptions (with debug codes kept as attributes).
  - Special mapping: **Error 8 → “Low battery”**.
  - Error descriptions translated across supported languages.
- **Long-term statistics restored**: sensors correctly declare `state_class` again (including IAQ sensors: CO₂, TVOC, PM2.5, PM10, pressure).

### Fixed
- **Master thermostat behavior**:
  - The master shows **ON** when at least one zone is ON.
  - Master target temperature updates **do not power zones on**.
- **Hotel buttons reliability**: turn-all-on/off actions are more robust (paced writes + verification/retries).
- **Stability fix**: avoid update-loop errors when an entity ends up without a `zone_id` (None).

## 1.6.1 - 2025-12-21

### Fixed
- **Modo Global**: ahora replica el comportamiento de la app de Airzone.
  - El estado del modo global se basa en `mode` (no en `on`).
  - **Apagado/Stop**: aplica `mode=Stop` a nivel global y fuerza `on=0` en todas las zonas.
  - **Calor/Frío/Ventilación/Seco/Auto**: cambia solo el `mode` global (broadcast) sin encender zonas automáticamente.
- UI más coherente: cuando el modo global está en stop, las zonas muestran solo opciones válidas.

## 1.6.0
- Termostatos por zona, termostato maestro, termostatos de grupo y entidades extra según instalación.

## 1.5.1
- Internacionalización (i18n) y ampliación de idiomas.

## 1.5.0
- Selects por zona (Modo, Velocidad, Ventilación IAQ), selector de Modo Global, sensores del Webserver y botones “Hotel”.
