# Changelog

## [1.5.0] - 2025-10-10

### 🚀 Added
- Nuevos `selects` para:
  - **Modo por zona** (`select.zone_mode`): cambia solo el modo de la zona.
  - **Modo global** (`select.global_mode`): aplica un modo a todas las zonas.
  - **Velocidad por zona** (`select.zone_speed`): disponible en sistemas con ventilación/ERV. Soporta `speed_values`, `speeds` y `speed`, incluyendo `Auto`.
  - **Ventilación IAQ** (`select.iaq_ventilation`): selector de `iaq_mode_vent` para sensores IAQ.
- Sensores Webserver bajo el dispositivo `Airzone Webserver`:
  - `cloud_connected`, `ws_version`, `transport`, `ws_mac`, `ws_interface`, `ws_type`, `ws_firmware`, `lmachine_firmware`, `ws_wifi_channel`, `ws_wifi_quality`, `ws_wifi_rssi`, `ws_wifi_quality_text`.
- Botones Hotel reimplementados:
  - `Apagar todo`, `Encender todo` y `Copiar consigna a todas` usando `PUT /hvac` con iteración y gestión de errores.

### 🌐 Internationalization (i18n)
- Todas las nuevas entidades usan `_attr_translation_key`.
- Archivos de traducción actualizados: `translations/es.json`, `en.json`, `ca.json`.
- Etiquetado dinámico según idioma del sistema de HA:
  - Modos (`calor`, `frío`, `deshumidificación`, etc.), velocidades (`auto`, `baja`, `media`, `alta`...), `sí/no`, etc.
- Nota: para que los nombres se traduzcan correctamente, es necesario:
  1. Cambiar el idioma global del sistema en `Settings → System → General → Language`.
  2. Reiniciar HA.
  3. Pulsar “Restaurar nombre por defecto” en las entidades antiguas.

### 🧱 Entity structure & stability
- Todas las entidades nuevas tienen `unique_id` y `device_info` correcto.
- Aparecen agrupadas bajo los dispositivos adecuados: Sistema HVAC, Zona, IAQ Sensor o Webserver.
- Evita entidades huérfanas y mejora la gestión desde el UI.

### 🔧 Robustness & internal improvements
- Uso de alias para claves según versión de firmware (`temp_outdoor`, `outdoorTemp`, `iaq_home`, etc.).
- Conversión segura de tipos (`int`, `float`, unidades normalizadas).
- Eliminación de código duplicado interno (helpers, bases).
- Construcción dinámica de modos y velocidades: deduplicación, orden, `fallback`, inclusión segura de `off`.
- Logs útiles en `custom_components.airzone_control`.
- IAQ y Webserver: solo se crean entidades si hay datos.
- Evita entidades zombie o en gris sin datos reales.

### 🧪 API compatibility
- Adaptado y probado con versiones de API 1.76 y 1.77.
- Soporta nuevos campos de `/hvac`, `/iaq` y `/webserver`.
- Compatible con sistemas antiguos (sin romper payloads).

### 🌡️ HVAC System
- Sensor de temperatura exterior con prioridad al override desde HA.
  - Convierte automáticamente °F/K → °C.
  - Atributos: `source`, `override_entity`.
- Nuevos sensores:
  - `mc_connected`, `system_firmware`, `system_type`, `system_technology`, `manufacturer`, `num_airqsensors`, `return_temp`, `work_temp`, `outdoor_temp`.
  - `cond_risk_master` incluido como placeholder.

### 🧬 IAQ
- Creación selectiva según datos presentes.
- Nuevos sensores IAQ:
  - `pressure_value`, `abs_humidity_gm3`, `humidex_master`, `humidex_master_pct`, `needs_ventilation`, `iaq_index`, `iaq_index_text`, `iaq_home_text`, etc.

### 🌍 Zona
- Creación condicional según claves presentes.
- Nuevos sensores por zona:
  - Temperatura, humedad, demandas (`air`, `cold`, `heat`, `floor`), estado (`open_window`, `errors`), `eco_adapt`, `units`.
- Fix: se corrige un ternario roto en `ZoneUnitsSensor` que rompía la carga.

### 🛠 Changed
- Mayor claridad en los nombres internos (`unique_id`, `translation_key`).
- Etiquetas dinámicas de calidad WiFi (Webserver).
- Mejora visual y funcional en el panel de integración.

### ⚠️ Breaking / Known Issues
- Si tu Home Assistant está en un idioma distinto al español y ves nombres en castellano:
  - Cambia el idioma del sistema en `Settings → System → Language`, reinicia HA, y pulsa “Restaurar nombre por defecto” en las entidades afectadas.
- Entidades antiguas pueden quedar en gris. Elimínalas si ya no son necesarias.

---

¿Quieres que te genere este archivo directamente como `CHANGELOG.md` en tu estructura del proyecto (`E:\github\airzone_control\CHANGELOG.md`) y/o te lo subo aquí para que lo descargues?