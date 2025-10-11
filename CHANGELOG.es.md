[🇬🇧 Read this in English](CHANGELOG.md) • [🇪🇸 Leer en español](CHANGELOG.es.md)

# Cambios

## [1.5.1] - 2025-10-11

### 🌐 Internacionalización (i18n)
- Traducciones completamente actualizadas para:
  - 🇪🇸 Español  
  - 🇬🇧 Inglés  
  - 🇨🇦 Catalán  
  - 🇫🇷 Francés  
  - 🇮🇹 Italiano  
  - 🇵🇹 Portugués  
  - 🇩🇪 Alemán  
- Se añadió soporte para nuevos idiomas:
  - 🇬🇷 Gallego (`gl`)  
  - 🇳🇱 Neerlandés (`nl`)  
  - 🇪🇺 Euskera (`eu`)  
- Estructura unificada de `translation_key` para todas las entidades (`sensor`, `select`, `button`, etc.).
- Correcciones menores en nombres de entidades.
- Sin cambios funcionales en la lógica de la integración.

---

## [1.5.0] - 2025-10-10

### 🚀 Añadido
- Nuevas entidades `select`:
  - **Modo por zona** (`select.zone_mode`): cambia solo el modo de la zona.
  - **Modo global** (`select.global_mode`): aplica un modo a todas las zonas a la vez.
  - **Velocidad del ventilador por zona** (`select.zone_speed`): disponible para sistemas de ventilación/ERV. Compatible con `speed_values`, `speeds` y `speed`, incluyendo `Auto`.
  - **Ventilación IAQ** (`select.iaq_ventilation`): selector para `iaq_mode_vent` en sensores IAQ.
- Sensores del Webserver bajo el dispositivo `Airzone Webserver`:
  - `cloud_connected`, `ws_version`, `transport`, `ws_mac`, `ws_interface`, `ws_type`, `ws_firmware`, `lmachine_firmware`, `ws_wifi_channel`, `ws_wifi_quality`, `ws_wifi_rssi`, `ws_wifi_quality_text`.
- Botones de hotel rediseñados:
  - `Apagar todo`, `Encender todo` y `Copiar consigna` vía `PUT /hvac` utilizando iteración por zona y gestión de errores.

### 🌐 Internacionalización (i18n)
- Todas las nuevas entidades utilizan `_attr_translation_key`.
- Archivos de traducción actualizados: `en.json`, `es.json`, `ca.json`.
- Etiquetas dinámicas mostradas según el idioma del sistema HA:
  - Modos (calor, frío, seco, etc.), velocidades (auto, baja, media, alta...), sí/no, etc.
- Para aplicar correctamente los nuevos nombres:
  1. Establece el idioma de tu HA en `Ajustes → Sistema → General → Idioma`.
  2. Reinicia HA.
  3. Haz clic en “Restaurar nombre predeterminado” en las entidades antiguas.

### 🧱 Estructura de entidades y estabilidad
- Todas las nuevas entidades tienen `unique_id` y `device_info` correctos.
- Agrupadas bajo el dispositivo adecuado: sistema HVAC, zona, sensor IAQ o Webserver.
- Evita entidades huérfanas o mal ubicadas en la interfaz.

### 🔧 Robustez y mejoras internas
- Alias para claves dependientes del firmware (`temp_outdoor`, `outdoorTemp`, `iaq_home`, etc.).
- Conversiones seguras de tipo (`int`, `float`, normalización de unidades).
- Eliminación de duplicaciones internas de código (helpers, bases).
- Construcción dinámica de modos y velocidades: deduplicación, ordenamiento, inclusión segura de `off`.
- Registros de depuración bajo `custom_components.airzone_control`.
- Sensores IAQ y Webserver solo creados si hay valores disponibles.
- Menos entidades vacías o "fantasma".

### 🧪 Compatibilidad con la API
- Adaptado para versiones 1.76 y 1.77 de la API.
- Soporta nuevos campos en `/hvac`, `/iaq` y `/webserver`.
- Compatible hacia atrás con instalaciones antiguas (sin cambios disruptivos).

### 🌡️ Sistema HVAC
- Soporte para sobrescribir temperatura exterior desde cualquier sensor de HA.
  - Convierte automáticamente °F/K → °C.
  - Atributos: `source`, `override_entity`.
- Nuevos sensores:
  - `mc_connected`, `system_firmware`, `system_type`, `system_technology`, `manufacturer`, `num_airqsensors`, `return_temp`, `work_temp`, `outdoor_temp`.
  - `cond_risk_master` añadido como marcador de posición.

### 🧬 IAQ
- Las entidades solo se crean si existen valores.
- Nuevos sensores IAQ:
  - `pressure_value`, `abs_humidity_gm3`, `humidex_master`, `humidex_master_pct`, `needs_ventilation`, `iaq_index`, `iaq_index_text`, `iaq_home_text`, etc.

### 🌍 Zona
- Creación condicional basada en claves disponibles.
- Nuevos sensores por zona:
  - Temperatura, humedad, demandas (`air`, `cold`, `heat`, `floor`), estado (`open_window`, `errors`), `eco_adapt`, `units`.
- Corrección crítica: ternario roto en `ZoneUnitsSensor` solucionado.

### 🛠 Cambios
- Nombres internos más claros (`unique_id`, `translation_key`).
- Etiquetas de calidad WiFi añadidas (Webserver).
- Panel de la integración más limpio y coherente.

### ⚠️ Cambios importantes / Problemas conocidos
- Si tu sistema HA no está en español y las entidades aparecen en español:
  - Cambia el idioma del sistema en `Ajustes → Sistema → Idioma`, reinicia HA y haz clic en “Restaurar nombre predeterminado”.
- Las entidades antiguas pueden aparecer en gris (no disponibles). Puedes eliminarlas si ya no se usan.
