[🇪🇸 Leer en español](CHANGELOG.es.md) • [🇬🇧 Read this in English](CHANGELOG.md)

# Registro de cambios

## [1.6.0] - 2025-12-17

- Añadido el **termostato maestro** (`climate`) por sistema, para controlar todas las zonas desde una sola entidad.
- Añadidos **termostatos de grupo** (`climate`) para controlar varias zonas como una sola.
- Añadida **UI en Opciones** para crear grupos mediante:
  - Nombre de grupo + selección de zonas (lista de checks)
  - Modo JSON avanzado sin límite práctico de grupos
- Los grupos ya soportan **encender/apagar** a nivel de grupo.
- Al guardar opciones, la integración hace **recarga automática**, y los nuevos grupos aparecen sin reiniciar Home Assistant.
- Mejora de traducciones para configuración y opciones.


## [1.5.1] - 2025-10-11

### 🌐 Internacionalización (i18n)
- Traducciones completamente actualizadas en:
  - 🇪🇸 Español
  - 🇬🇧 Inglés
  - 🇨🇦 Catalán
  - 🇫🇷 Francés
  - 🇮🇹 Italiano
  - 🇵🇹 Portugués
  - 🇩🇪 Alemán
- Nuevos idiomas añadidos:
  - 🇬🇷 Gallego (`gl`)
  - 🇳🇱 Neerlandés (`nl`)
  - 🇪🇺 Euskera (`eu`)
- Todas las entidades (`sensor`, `select`, `button`, etc.) utilizan ahora claves `translation_key` para mostrar nombres traducidos según el idioma de Home Assistant.
- Correcciones menores en nombres y etiquetas visibles.
- Sin cambios en la lógica de la integración.


## [1.5.0] - 2025-10-10

### 🚀 Añadido
- Nuevas entidades `select`:
  - **Modo por zona** (`select.zone_mode`): cambia solo el modo de una zona concreta.
  - **Modo global** (`select.global_mode`): aplica un modo a todas las zonas a la vez.
  - **Velocidad de ventilador por zona** (`select.zone_speed`): disponible en sistemas de ventilación/ERV. Soporta `speed_values`, `speeds` y `speed`, incluyendo `Auto`.
  - **Ventilación IAQ** (`select.iaq_ventilation`): selector para `iaq_mode_vent` en sensores IAQ.
- Nuevos sensores del Webserver, agrupados bajo el dispositivo `Airzone Webserver`:
  - `cloud_connected`, `ws_version`, `transport`, `ws_mac`, `ws_interface`, `ws_type`, `ws_firmware`, `lmachine_firmware`, `ws_wifi_channel`, `ws_wifi_quality`, `ws_wifi_rssi`, `ws_wifi_quality_text`.
- Rediseño de botones Hotel:
  - Apagar todo, encender todo y copiar consigna mediante `PUT /hvac` con gestión por zonas y control de errores.

### 🌐 Internacionalización (i18n)
- Todas las nuevas entidades utilizan `_attr_translation_key`.
- Archivos `en.json`, `es.json`, `ca.json` actualizados.
- Las etiquetas de entidades se muestran ahora según el idioma configurado en Home Assistant:
  - Modos (calor, frío, seco...), velocidades (auto, baja, media, alta...), sí/no, etc.
- Para aplicar correctamente los nuevos nombres:
  1. Ve a `Ajustes → Sistema → General → Idioma` en Home Assistant.
  2. Reinicia HA.
  3. Haz clic en “Restaurar nombre por defecto” en las entidades antiguas.

### 🧱 Estructura y estabilidad
- Todas las nuevas entidades incluyen `unique_id` y `device_info` completos.
- Correcta agrupación de sensores según el dispositivo: sistema HVAC, zona, sensor IAQ o Webserver.
- Evita entidades huérfanas o mal agrupadas en la interfaz.

### 🔧 Robustez e internas
- Compatibilidad con múltiples nombres de claves según el firmware (`temp_outdoor`, `outdoorTemp`, `iaq_home`, etc.).
- Conversión segura de tipos (`int`, `float`, unidades...).
- Eliminación de duplicación interna de código (helpers, bases).
- Construcción dinámica de modos y velocidades: ordenados, sin duplicados, inclusión segura de `off`.
- Registros de depuración (`logger.debug`) bajo `custom_components.airzone_control`.
- Sensores IAQ y Webserver solo se crean si hay datos disponibles.
- Menos entidades vacías o "zombies".

### 🧪 Compatibilidad API
- Adaptación a las versiones 1.76 y 1.77 de la API local.
- Soporte para nuevos campos en `/hvac`, `/iaq` y `/webserver`.
- Compatible con instalaciones más antiguas (no rompe nada).

### 🌡️ Sistema HVAC
- Soporte para anular temperatura exterior mediante cualquier sensor de Home Assistant:
  - Auto-conversión de °F/K a °C.
  - Atributos: `source`, `override_entity`.
- Nuevos sensores:
  - `mc_connected`, `system_firmware`, `system_type`, `system_technology`, `manufacturer`, `num_airqsensors`, `return_temp`, `work_temp`, `outdoor_temp`.
  - Añadido `cond_risk_master` como placeholder.

### 🧬 Sensores IAQ
- Solo se crean si hay datos reales.
- Nuevos sensores IAQ:
  - `pressure_value`, `abs_humidity_gm3`, `humidex_master`, `humidex_master_pct`, `needs_ventilation`, `iaq_index`, `iaq_index_text`, `iaq_home_text`, etc.

### 🌍 Zona
- Creación condicional de sensores según claves disponibles.
- Nuevos sensores por zona:
  - Temperatura, humedad, demandas (`air`, `cold`, `heat`, `floor`), estado (`open_window`, `errors`), `eco_adapt`, `units`.
- Corrección crítica: ternario roto en `ZoneUnitsSensor` corregido.

### 🛠 Cambios internos
- Identificadores y claves de traducción más claros (`unique_id`, `translation_key`).
- Etiquetas de calidad WiFi añadidas (Webserver).
- Panel de integración más limpio y consistente.

### ⚠️ Errores conocidos / cambios importantes
- Si tu sistema HA está en otro idioma y ves entidades en español:
- Cambia el idioma del sistema desde `Ajustes → Sistema → Idioma`, reinicia y pulsa “Restaurar nombre por defecto”.
- Las entidades antiguas podrían aparecer como no disponibles (gris). Puedes eliminarlas si ya no las usas.
