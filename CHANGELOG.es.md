[Read this in English](CHANGELOG.md)

# Historial de Cambios

## 1.9.0 - 2026-08-01

### Añadido

- Descubrimiento automático de controladores Local API mediante Zeroconf, manteniendo disponible la configuración manual por IP.
- Flujo de reautenticación para renovar las credenciales de entradas Cloud API.
- Opción de verificación TLS para conexiones Local API; permanece activada por defecto.
- Opción independiente para registrar el driver de integración en equipos compatibles; permanece desactivada por defecto.
- Información adicional de transporte y estado de las distintas fuentes en los diagnósticos de soporte.

### Cambiado

- Las conexiones HTTP reutilizan la sesión administrada por Home Assistant y se integran con el ciclo de vida actual de las entradas de configuración.
- La disponibilidad de las entidades refleja el estado de su fuente concreta: climatización, IAQ, webserver o dispositivo Cloud.
- El descubrimiento de instalaciones Cloud admite resultados paginados.
- Los perfiles Cloud `complement_local` y `custom` requieren seleccionar al menos un dispositivo antes de guardar.
- El intervalo mínimo configurable es de `5` segundos para Local API y `15` segundos para Cloud API; el valor Cloud por defecto continúa siendo `30` segundos.
- Las entidades opcionales solo se crean cuando el equipo publica el campo correspondiente.
- Los estados de modo, velocidad y calidad de aire utilizan identificadores estables y traducciones de Home Assistant.
- El idioma de respaldo para traducciones no disponibles pasa a ser inglés.
- Se han ajustado las clases de estado de los contadores energéticos Cloud según el significado de cada campo.
- El interruptor de sistema enciende o apaga todas sus zonas y el modo «seguir zona maestra» recupera su último estado tras reiniciar.

### Corregido

- Cálculo del estado de actividad de los termostatos de zona, sistema y grupo usando la demanda real publicada por el equipo.
- Manejo de valores numéricos válidos iguales a cero en sensores y datos Cloud.
- Conservación del último estado válido sin presentar como disponibles las fuentes cuya actualización haya fallado.
- Validación de grupos lógicos, referencias de zona e identificadores duplicados antes de guardar opciones.
- Evitadas tareas duplicadas al sincronizar zonas con la zona maestra.
- Mejorada la selección del método de transporte y el refresco periódico de metadatos del equipo.
- Corregidos los patrones de descubrimiento Zeroconf del manifiesto.

### Notas

- Cloud API continúa siendo de solo lectura.
- Los archivos generados para soporte omiten datos de configuración e identificadores que no son necesarios para analizar el funcionamiento de la integración.
- Se ha simplificado el registro de respuestas HTTP para conservar únicamente la información necesaria para diagnosticar errores.

## 1.8.0 - 2026-05-05

### Añadido

- Primera fase pública de Cloud API.
- Nuevo flujo de configuración Cloud API con autenticación por email/contraseña.
- Perfiles Cloud:
  - `full`: publica todas las categorías Cloud soportadas.
  - `complement_local`: complementa una entrada Local API existente con dispositivos solo disponibles en Cloud.
  - `custom`: permite elegir manualmente categorías y dispositivos Cloud.
- Filtros de categorías Cloud:
  - `climate_zones`
  - `energy`
  - `iaq`
  - `acs`
  - `aux`
- Selección de dispositivos Cloud por `cloud_device_id` estable.
- Soporte de medidor energético Cloud `az_energy_clamp`.
- Soporte de sonda IAQ Cloud `az_airqsensor`.
- Mapeo IAQ Cloud para CO2, TVOC, presión, PM1.0, PM2.5, PM10, IAQ score y calidad textual.
- Mapeo de medidor energético Cloud para energía importada/devuelta, energía por fase, potencia, corriente y tensión.
- Entidades climate Cloud de solo lectura cuando se habilitan las zonas Cloud.
- Opción para incluir u ocultar sondas IAQ vinculadas a sistemas/zonas Cloud.
- Soporte para ejecutar entradas Local API y Cloud API juntas sin colisiones de `unique_id`.

### Cambiado

- Las entradas Cloud usan por defecto un intervalo conservador de `30` segundos.
- Las entradas Cloud complementarias ya no exponen el dispositivo webserver Cloud cuando las zonas climate están deshabilitadas, evitando duplicados de Webserver/Flexa.
- Las sondas IAQ Cloud y el medidor energético Cloud conservan el último estado válido cuando una lectura puntual Cloud falla o llega incompleta.
- La selección de dispositivos Cloud ya no viene preseleccionada por defecto en perfiles complementario/personalizado.
- Si la selección de dispositivos Cloud queda vacía en perfiles complementario/personalizado, esa entrada no publica dispositivos Cloud.
- Los modelos de dispositivo para zonas/sistemas Cloud ya no aparecen como modelos de Local API.
- Los diagnósticos redactan email e identificadores Cloud de usuario, instalación, webserver y dispositivo.
- Los identificadores Cloud ya no se exponen como atributos de entidad en sensores IAQ y de medidor energético.
- Los archivos de traducción incluyen todas las claves nuevas de Cloud config/options; algunos idiomas secundarios pueden usar texto inglés como fallback hasta su revisión.

### Corregido

- Recuperado el sensor binario `open_window` cuando la Local API lo expone.
- El sensor binario de ventilación IAQ usa primero los campos explícitos `needs_ventilation` / `need_ventilation` antes de caer a la heurística por CO2.
- El modo Cloud complementario puede publicar dispositivos de energía/IAQ sin crear termostatos ni webserver duplicados.

### Notas

- La escritura Cloud está desactivada intencionadamente en esta versión.
- No se crean entidades `select`, `switch` ni `button` para entradas Cloud.
- La clasificación de algunos campos del medidor Cloud para Energy Dashboard puede cambiar cuando se confirme si ciertos contadores Airzone se reinician por periodo.

## 1.7.0 - 2026-04-12

### Añadido

- Capa de compatibilidad con la Local API para esquemas y prefijos Airzone más recientes.
- Sensores de sistema: `energy_consump`, `energy_produced`, `power_gen_heat`, `consumption_ue`.
- Sensores de zona: `battery`, `coverage`, `sleep`, `aq_quality`, `acs_temp`, `acs_setpoint`.
- Selects de zona: `sleep`, `slats_vertical`, `slats_horizontal`, `slats_vswing`, `slats_hswing`, `erv_mode`.
- Sensores binarios: `battery_low`, `antifreeze`.
- Switches ACS/DHW: `acs_power`, `acs_powerful`.
- Traducciones en español e inglés para las nuevas entidades.

### Cambiado

- Los datos de sistema se pueblan ahora en el coordinator y se exponen mediante `get_system()`.
- La detección de versión usa ahora `POST /version`.
- Se intenta registrar el driver mediante `/integration` de forma prudente cuando el equipo lo soporta.
- Las nuevas entidades se crean dinámicamente solo cuando el hardware expone los campos necesarios.

## 1.6.2 - 2025-12-31

### Añadido

- Descarga de diagnósticos desde la página del dispositivo.
- Atributos de depuración `systemID`, `zoneID` y `group_id` cuando aplica.
- Más información de dispositivo cuando la API la proporciona, incluyendo número de serie y versión de firmware.
- Descripciones de error legibles.
- Restaurados los metadatos de estadísticas a largo plazo para sensores normales e IAQ.

### Corregido

- El termostato maestro muestra ON cuando al menos una zona está encendida.
- Cambiar la consigna del maestro ya no enciende zonas.
- Los botones Hotel son más fiables.
- Se evitan errores del bucle de actualización cuando una entidad no tiene `zone_id`.

## 1.6.1 - 2025-12-21

### Corregido

- Modo Global alineado con el comportamiento de la app Airzone.
- Stop/Apagado aplica el modo Stop global y fuerza todas las zonas a apagado.
- Calor/Frío/Ventilación/Seco/Auto cambia solo el modo global sin encender zonas.
- La UI de zona muestra solo opciones válidas cuando el Modo Global está en Stop.

## 1.6.0

- Añadidos termostatos por zona, termostato maestro, termostatos de grupo y entidades extra según instalación.

## 1.5.1

- Actualización de internacionalización y nuevos idiomas.

## 1.5.0

- Añadidos selects por zona, selector de Modo Global, sensores del Webserver y botones Hotel.
