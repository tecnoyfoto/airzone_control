[🇬🇧 Read this in English](CHANGELOG.md)

# Changelog

## 1.6.2 - 2025-12-31

### Añadido
- **Descarga de diagnósticos**: “Descargar diagnósticos” genera un JSON con una instantánea de la integración para facilitar depuración/reportes.
- **Atributos de depuración**: las entidades exponen `systemID` y `zoneID` (y `group_id` cuando aplica).
- **Más información de dispositivo** (si la API lo devuelve): número de serie y versión de firmware.
- **Errores legibles**: el sensor de errores muestra descripciones entendibles (manteniendo códigos/listas como atributos).
  - Mapeo especial: **Error 8 → “Batería baja”**.
  - Descripciones traducidas a los idiomas soportados.
- **Estadísticas a largo plazo restauradas**: los sensores declaran `state_class` correctamente (incluyendo IAQ: CO₂, TVOC, PM2.5, PM10, presión).

### Arreglado
- **Comportamiento del termostato maestro**:
  - El maestro muestra **ON** si hay al menos una zona encendida.
  - Cambiar la deseada del maestro **no enciende zonas**.
- **Fiabilidad de botones Hotel**: acciones masivas encender/apagar con más robustez (envío controlado + verificación/reintentos).
- **Estabilidad**: evita errores del ciclo de actualización cuando una entidad queda sin `zone_id` (None).

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
