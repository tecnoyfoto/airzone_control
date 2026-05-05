# Airzone Control - estado y estrategia pendiente

Actualizado: 26/04/2026

Este archivo resume el punto real del proyecto para poder retomar sin volver a empezar.

## Auditoria de publicacion 04/05/2026

Revision hecha sobre Home Assistant `2026.5.0b0` en esta instalacion.

Cambios aplicados:

- `manifest.json` subido a `1.8.0`.
- `diagnostics.py` redacta tambien `email`, `user_id`, `installation_id`, `device_id`, `ws_id` y variantes `cloud_*`.
- Cloud usa `DEFAULT_CLOUD_SCAN_INTERVAL = 30` tambien para entradas antiguas/incompletas sin `scan_interval`.
- En perfiles cloud `complement_local` y `custom`, si el usuario ha pasado por selector de dispositivos y deja la seleccion vacia, no se publican dispositivos por accidente.
- El selector de dispositivos Cloud ya no preselecciona todo por defecto.
- `binary_sensor.py` vuelve a crear el binario de ventana abierta cuando existe `open_window`.
- El binario IAQ de ventilacion usa primero `needs_ventilation` / `need_ventilation` y solo cae a CO2 >= 1200 como heuristica.
- Zonas/sistemas cloud ya no aparecen como modelo `Local API zone/system` cuando vienen de Cloud.
- Traducciones `ca/de/eu/fr/gl/it/nl/pt` completadas estructuralmente con fallback ingles para las claves Cloud nuevas.

Checks ejecutados:

- `python -m compileall -q custom_components/airzone_control`
- Validacion JSON de todas las traducciones.
- Comparacion de claves de traduccion contra `en.json`: 0 claves faltantes en todos los idiomas.

Pendiente antes de publicar en GitHub/HACS:

- Crear/actualizar `README.md` en la raiz del repo con instalacion, Local API, Cloud API read-only y perfil complementario.
- Crear/actualizar `hacs.json` en la raiz del repo.
- Anadir assets de marca para HACS/brands si se quiere optar a inclusion publica amplia.
- Publicar release/tag `1.8.0` y changelog.
- Ejecutar validacion real en Home Assistant despues de reiniciar la integracion.
- Confirmar estabilidad de Cloud con el intervalo real usado por Albert.


## Resumen corto para retomar

Estado al pausar el 26/04/2026:

- La integracion debe ser publica/generica para fabricante y clientes, no personalizada para Albert.
- `Local API` sigue siendo la fuente principal de termostatos e IAQ local.
- `Cloud API` funciona en modo solo lectura.
- La entrada cloud de Albert esta configurada como complemento:
  - `cloud_profile: complement_local`
  - `cloud_include_categories: energy, iaq`
  - `cloud_include_bound_iaqs: true`
  - `cloud_include_device_ids`: medidor `az_energy_clamp` + sonda wifi `Sensor`
  - `cloud_exclude_iaq_names`: vacio
  - `scan_interval: 15`
- El default publico para nuevas entradas Cloud queda conservador:
  - `cloud_profile: full`
  - todas las categorias cloud soportadas
  - `DEFAULT_CLOUD_SCAN_INTERVAL = 30`
- Validado visualmente en Home Assistant:
  - dispositivo `Airzone Energy Meter`
  - dispositivo `Sensor`
  - `Sensor` entra como `az_airqsensor`
  - `Sensor` crea 8 entidades
  - `Comedor` no se duplica desde Cloud cuando no esta seleccionado en `cloud_include_device_ids`
- Importante descubierto:
  - Tanto `Comedor` como la sonda wifi nueva `Sensor` son `az_airqsensor`
  - Ambas pueden venir con `system_number=1` y `zone_number=1`
  - Por tanto, no sirve filtrar IAQ cloud solo por "vinculada/no vinculada"
  - La solucion publicable es seleccionar dispositivos por `cloud_device_id`
- Disponibilidad:
  - Se vio parpadeo a `No disponible` en IAQ cloud
  - Se corrigio conservando ultimo estado valido cuando falla una lectura puntual Cloud
  - Se bajo la presion de Cloud: Albert queda en 15s; default publico Cloud queda en 30s
  - Queda en observacion durante unos dias; si vuelve a fallar, subir a 20s, luego 25s, luego 30s

Proximos pasos recomendados al volver:

1. Revisar si `Sensor` y medidor han estado estables con `scan_interval: 15`.
2. Probar bien el options flow con perfiles:
   - `full`
   - `complement_local`
   - `custom`
3. Pulir nombres/modelos de dispositivos Cloud.
4. Revisar diagnosticos/privacidad.
5. Completar traducciones.
6. Subir version y changelog cuando la fase read-only este cerrada.


## Situacion actual

- La integracion ya soporta dos caminos de entrada:
  - `Local API`
  - `Cloud API`
- `Local API` esta estable y sigue siendo el camino principal para la instalacion actual.
- `Cloud API` no hay que rehacerla desde cero:
  - el config flow cloud existe
  - el login cloud funciona
  - el refresh token existe
  - se leen instalaciones
  - se leen webservers
  - se leen estados de dispositivos cloud
  - se normaliza parte del payload cloud hacia la forma interna usada por local
  - puede crear termostatos cloud en solo lectura
- El 26/04/2026 se anadio el primer bloque de la estrategia cloud complementaria:
  - opcion `cloud_include_categories`
  - categorias cloud filtrables
  - paso de opciones al `AirzoneCloudCoordinator`
  - filtrado de dispositivos cloud antes de publicar datos hacia Home Assistant
  - soporte para que Cloud API pueda cargar sin zonas/termostatos
- El 26/04/2026 se anadio tambien el primer soporte de medidor cloud como dispositivo propio:
  - `coordinator_cloud.py` guarda `az_energy_clamp` en `cloud_energy_meters`
  - `sensor.py` crea sensores desde `cloud_energy_meters`
  - esos sensores no dependen de `coord.data` ni de zonas
- Correccion posterior del 26/04/2026:
  - al probar Cloud API con solo `energy` + `iaq`, Home Assistant seguia mostrando el Webserver del Flexa 4 duplicado
  - causa: `sensor.py` y `binary_sensor.py` creaban entidades de webserver siempre
  - solucion: `AirzoneCloudCoordinator` expone `expose_webserver_entities` solo cuando `climate_zones` esta activado
  - en modo cloud complementario (`energy` + `iaq`) ya no deberian crearse entidades/dispositivo del webserver
- Avance posterior del 26/04/2026:
  - `az_airqsensor` se ha anadido como tipo cloud IAQ soportado
  - `coordinator_cloud.py` normaliza payload IAQ cloud hacia `coord.iaqs`
  - se mapean campos cloud como `aq_score`, `aq_co2`, `aq_tvoc`, `aq_pressure`, `aqpm2_5`, `aqpm10` y `aq_quality`
  - el comportamiento por defecto se ha corregido para producto publico: Cloud API incluye todas las categorias soportadas
- las IAQ cloud vinculadas a sistemas/zonas se incluyen por defecto
- se anade la opcion `cloud_include_bound_iaqs` para que instalaciones complementarias puedan ocultar esas IAQ vinculadas y evitar duplicados con Local API
- se anade `cloud_include_device_ids` para seleccionar dispositivos Cloud concretos por `cloud_device_id`; la UI muestra nombres legibles, pero la configuracion no depende del nombre
- `cloud_exclude_iaq_names` queda como herramienta secundaria, pero no debe ser el mecanismo principal para instalaciones publicas
- se anade `cloud_profile` para orientar la configuracion:
  - `full`: usar todo Cloud API
  - `complement_local`: complementar Local API
  - `custom`: seleccion personalizada
- en entradas nuevas:
  - `full` publica todo lo soportado sin filtro por dispositivo
  - `complement_local` usa categorias `energy` + `iaq` y muestra selector de dispositivos Cloud
  - `custom` permite categorias y selector de dispositivos Cloud
- compatibilidad: entradas cloud ya existentes sin esta opcion y sin `climate_zones` mantienen comportamiento complementario, es decir, no incluyen IAQ vinculadas por defecto
- Validacion real posterior:
  - La nueva sonda wifi aparece en Airzone Cloud con nombre `Sensor`
  - Su `device_type` tambien es `az_airqsensor`
  - Viene con `system_number=1` y `zone_number=1`, igual que una IAQ vinculada
  - Por eso el filtro global `cloud_include_bound_iaqs: false` la ocultaba junto con `Comedor`
  - La entrada Cloud actual queda con `cloud_profile: complement_local`, `energy` + `iaq`, `cloud_include_bound_iaqs: true` y `cloud_include_device_ids` con el medidor + la sonda `Sensor`
- Ajuste posterior por disponibilidad intermitente:
  - Se observo que las entidades IAQ cloud pasaban a `No disponible` de forma intermitente
  - Causa probable de integracion/Cloud, no necesariamente de la sonda fisica: si una lectura puntual de `/devices/{id}/status` falla o viene incompleta, antes se vaciaba `self.iaqs`
  - `coordinator_cloud.py` ahora conserva el ultimo estado valido de IAQ y medidores cloud cuando una lectura puntual falla o viene incompleta
  - Las entradas cloud nuevas usan `DEFAULT_CLOUD_SCAN_INTERVAL = 30`
  - La entrada cloud actual se ajusto de `scan_interval: 5` a `scan_interval: 30` para evitar golpear la API Cloud con demasiada frecuencia
- Validacion real posterior del 26/04/2026:
  - Cloud API con `energy` + `iaq` autentica correctamente
  - no crea termostatos duplicados
  - no crea el Webserver/Flexa 4 duplicado
  - crea el dispositivo `Airzone Energy Meter`
  - el dispositivo aparece como `az_energy_clamp`
  - se crean 20 entidades/sensores del medidor
  - se ven sensores reales de corriente, energia importada/devuelta y potencia
- La version en `manifest.json` es `1.8.0` desde la auditoria del 04/05/2026.
- La entrada cloud volvio a crearse en Home Assistant en modo complementario `energy` + `iaq`.


## Estado funcional confirmado

### Local API

- Los termostatos funcionan bien por Local API.
- La IAQ conectada al Flexa 4 funciona bien por Local API.
- La IAQ local existente aparece en Home Assistant como dispositivo `Comedor`, con entidades como:
  - CO2
  - TVOC
  - PM2.5
  - PM10
  - IAQ score
  - presion
- No hay que perseguir por Local API el medidor nuevo ni la IAQ wifi/cloud nueva.

### Cloud API

- Cloud autentica y lee.
- Cloud ya puede sacar termostatos si se activa `climate_zones`, pero para la instalacion de Albert se deja desactivado para no duplicar Local API.
- Cloud en modo complementario `energy` + `iaq` ya saca el medidor `az_energy_clamp`.
- Cloud en modo complementario ya saca la sonda IAQ wifi `Sensor`.
- La sonda `Sensor` se ha validado en Home Assistant como dispositivo `az_airqsensor` con 8 entidades.
- La IAQ local `Comedor` no se duplica si no se selecciona en `cloud_include_device_ids`.
- Cloud sigue en modo solo lectura:
  - `read_only = True`
  - `select.py`, `switch.py` y `button.py` no crean entidades cloud
  - `climate.py` crea entidades cloud sin escritura real
- La escritura cloud no esta validada y no debe activarse todavia.
- La estabilidad de `Sensor` con `scan_interval: 15` queda en observacion.


## Problema real a resolver ahora

Albert quiere usar:

- Local API para lo que ya funciona bien:
  - termostatos
  - IAQ local conectada al Flexa 4
- Cloud API solo para dispositivos que no salen por local:
  - medidor de consumo wifi/cloud
  - nueva sonda IAQ wifi/cloud

Por tanto, el problema no es "hacer cloud", sino evitar que cloud duplique termostatos y permitir que cloud publique solo las familias de dispositivos que interesan.


## Decision de diseno

Cloud debe poder funcionar como entrada complementaria de Local API.

La entrada `Cloud API` no debe exponer obligatoriamente todo lo que devuelve Airzone Cloud. Ya existe un primer filtro de inclusion por categoria de dispositivo.

Categorias propuestas:

- `climate_zones`
  - Termostatos / zonas cloud.
  - Tipos conocidos: `az_zone`, `aidoo`, `aidoo_it`.
  - En la instalacion de Albert normalmente debe estar desactivado para no duplicar Local API.
- `iaq`
  - Sondas de calidad de aire cloud/wifi.
  - Hay que confirmar el `device_type` real de la nueva sonda cuando este instalada y visible en cloud.
- `energy`
  - Medidores cloud.
  - Tipo conocido: `az_energy_clamp`.
- `acs`
  - ACS u otros auxiliares si en el futuro interesa.
  - Tipos ya contemplados parcialmente: `az_acs`, `aidoo_acs`.
- `aux`
  - Otros auxiliares cloud.
  - Tipos actuales conocidos: `az_vmc`, `az_relay`, `az_dehumidifier`.

La opcion recomendada para esta instalacion:

- Local API activa para termostatos e IAQ local.
- Cloud API activa solo con:
  - `energy`
  - `iaq`
- Cloud API sin:
  - `climate_zones`

Estado validado:

- Esta configuracion ya se ha probado en Home Assistant real.
- Resultado correcto:
  - sin termostatos duplicados
  - sin webserver duplicado
  - medidor visible como `Airzone Energy Meter`

Estado implementado:

- Constantes nuevas en `const.py`.
- En config flow cloud se puede elegir `cloud_include_categories`.
- En options flow se puede cambiar `cloud_include_categories`.
- `__init__.py` pasa las categorias al coordinator cloud.
- `coordinator_cloud.py` clasifica y filtra los tipos conocidos.
- Si `climate_zones` esta desactivado, cloud ya no falla por no tener zonas y limpia `coord.data`.
- Si `climate_zones` esta desactivado, cloud tampoco debe exponer el webserver para no duplicar el Flexa 4 local.

Limitaciones actuales:

- La categoria `iaq` ya tiene tipo real confirmado: `az_airqsensor`.
- La normalizacion IAQ cloud hacia `coord.iaqs` ya existe y se ha validado con `Sensor`.
- La categoria `energy` ya procesa `az_energy_clamp` como dispositivo propio y crea sensores aunque no haya zonas.
- Falta observar estabilidad unos dias con `scan_interval: 15`.
- Falta pulir UX/options flow para que los perfiles Cloud sean claros para usuarios finales.
- Faltan traducciones completas y revision de privacidad/diagnosticos.


## UX/configuracion

Implementado por ahora:

- Campo multi-select `cloud_include_categories`.
- Valores:
  - `energy`
  - `iaq`
  - `climate_zones`
  - `acs`
  - `aux`

Valores por defecto:

- Para una entrada `Cloud API` publica/generica se incluyen todas las categorias conocidas:
  - `climate_zones`
  - `energy`
  - `iaq`
  - `acs`
  - `aux`

Valores recomendados para Albert:

- Perfil conservador orientado a complementar Local API:
  - `energy`
  - `iaq`
- Desactivar `climate_zones`.
- Desactivar `cloud_include_bound_iaqs` si la IAQ local `Comedor` se duplica desde Cloud.
- Mejor para Albert: mantener `cloud_include_bound_iaqs` activado y seleccionar por `cloud_include_device_ids` solo el medidor y la sonda wifi `Sensor`, porque la sonda wifi nueva tambien viene vinculada a sistema/zona.
- Mantener `cloud_include_bound_iaqs` activado en instalaciones que usan solo Cloud API o que quieran ver todas las sondas IAQ cloud.
- Nota de compatibilidad: si una entrada antigua no tiene todavia `cloud_include_bound_iaqs`, el valor implicito depende de sus categorias; con `climate_zones` activo se comporta como Cloud completo, sin `climate_zones` se comporta como complemento.

Posible mejora futura, si se quiere una UX mas clara:

- Primer selector:
  - `Complementar Local API`
  - `Usar todo Cloud API`
  - `Personalizado`
- `Complementar Local API` activa solo `energy` + `iaq`.
- `Usar todo Cloud API` activa `climate_zones` + `energy` + `iaq` + auxiliares relevantes.
- `Personalizado` muestra las categorias.

Estado actual:

- Ya existe el selector `cloud_profile`.
- `Complementar Local API` y `Personalizado` usan selector de dispositivos Cloud por `cloud_device_id`.
- El formulario de Home Assistant no permite esconder campos dinamicamente en el mismo paso; por eso categorias/dispositivos pueden aparecer juntos, pero el guardado respeta el perfil seleccionado.


## Punto tecnico donde filtrar

Implementado: el filtro se hace dentro de `coordinator_cloud.py`, durante la construccion de datos normalizados.

Motivo:

- El coordinator puede leer el inventario cloud completo.
- Pero solo debe publicar hacia Home Assistant las categorias habilitadas.
- Asi las plataformas (`sensor.py`, `climate.py`, etc.) ni siquiera ven datos de categorias desactivadas.
- Esto evita entidades duplicadas desde la raiz.

Implementacion actual:

- Las categorias se guardan en options.
- Se pasan al `AirzoneCloudCoordinator`.
- Helpers creados:
  - `_cloud_category_enabled("climate_zones")`
  - `_device_category(device_type)`
- Tambien existe `_device_enabled(device_type)`.
- En `_async_update_data`:
  - se lee el inventario cloud
  - solo se piden estados de los tipos soportados y habilitados
  - al normalizar, saltar dispositivos cuya categoria no este habilitada
- En modo cloud complementario, el webserver/cloud connectivity no se expone como entidad para evitar duplicar el Flexa 4 local.


## Puntos tecnicos pendientes detectados

### 1. Medidor cloud

Estado actual:

- `coordinator_cloud.py` conoce `az_energy_clamp`.
- Se mantiene compatibilidad antigua mezclando `energy_hour_latest` como `energy_consump` dentro de `systems`.
- Ademas, desde el 26/04/2026, `coordinator_cloud.py` normaliza `az_energy_clamp` como dispositivo propio en `cloud_energy_meters`.
- `sensor.py` ya crea sensores desde `cloud_energy_meters`, sin depender de zonas.
- Desde el 26/04/2026, si la categoria `energy` esta activada, `az_energy_clamp` pasa el filtro cloud aunque `climate_zones` este desactivado.

Campos contemplados inicialmente:

- Energia:
  - `energy_hour_latest`
  - `energy_day_latest`
  - `energy_day_current`
  - `energy_month_latest`
  - `energy_month_current`
  - `energy_year_latest`
  - `energy_year_current`
  - `energy_total`
  - `total_energy`
  - `energy_accumulated`
  - `energy_consumed`
  - `consumption`
- Potencia/electricos:
  - `power`
  - `active_power`
  - `power_latest`
  - `current`
  - `voltage`

Nota:

- `energy_hour_latest` se trata como kWh de medicion, no como acumulado total.
- Solo los campos claramente acumulados (`energy_total`, `total_energy`, `energy_accumulated`, `energy_consumed`) se marcan como `total_increasing`.

Validacion real:

- El payload real de Albert ya se inspecciono el 26/04/2026.
- El tipo real del medidor es `az_energy_clamp`.
- Los campos reales vistos no eran `energy_hour_latest`, sino:
  - `energy_acc`
  - `energy_ret`
  - `energy1_acc`
  - `energy1_ret`
  - `energy2_acc`
  - `energy2_ret`
  - `energy3_acc`
  - `energy3_ret`
  - `power_total`
  - `power_p1`
  - `power_p2`
  - `power_p3`
  - `current_total`
  - `current_p1`
  - `current_p2`
  - `current_p3`
  - `voltage_total`
  - `voltage_p1`
  - `voltage_p2`
  - `voltage_p3`
- Tambien aparecen fechas de fin de periodo:
  - `energy_period_end_dt`
  - `energy1_period_end_dt`
  - `energy2_period_end_dt`
  - `energy3_period_end_dt`
- Se actualizo el mapping para esos campos.
- Por prudencia, `energy_acc`/`energy_ret` y sus fases se marcan inicialmente como `measurement`, no como `total_increasing`, hasta confirmar si resetean al final de periodo.
- Tras actualizar el mapping, Home Assistant creo el dispositivo `Airzone Energy Meter`.
- El dispositivo muestra 20 entidades.
- La validacion visual confirma sensores de corriente, energia importada/devuelta y potencia.

Trabajo necesario:

- Revisar con calma si sobran sensores de fases P1/P2/P3 o si se quieren dejar todos.
- Si se quiere integrarlo en Energy Dashboard, decidir despues si algun campo debe pasar a `total_increasing`.
- Ajustar nombres/unidades si Airzone devuelve unidades distintas a las previstas.

Pendiente clave:

- El medidor ya aparece en UI. Siguiente trabajo principal: IAQ cloud.


### 2. IAQ cloud

Estado actual:

- La maquinaria de sensores IAQ existe y funciona para Local API.
- `az_airqsensor` ya esta registrado como tipo IAQ cloud.
- `coordinator_cloud.py` ya no limpia siempre `self.iaqs`; ahora publica IAQ cloud normalizadas cuando pasan el filtro.
- Por defecto, Cloud API expone tambien IAQ con `system_number` o `zone_number`, porque la integracion debe servir para usuarios que usan solo Cloud API.
- La opcion `cloud_include_bound_iaqs` permite ocultar esas IAQ asociadas a sistema/zona cuando Cloud API se usa como complemento de Local API.
- Si `climate_zones` esta activado, las IAQ asociadas a sistema/zona se exponen siempre para mantener una entrada Cloud completa.

Problemas conocidos:

- `aq_quality` en cloud puede venir como texto:
  - `good`
  - `regular`
  - `bad`
- El codigo cloud ahora conserva esos valores como texto en `air_quality_text` / `iaq_quality_text`.
- Si `aq_quality` viene numerico, se guarda como `iaq_index`.
- El criterio "standalone" para distinguir IAQ cloud nueva de IAQ local duplicada queda como herramienta opcional, no como comportamiento global.

Campos IAQ cloud que conviene contemplar segun investigacion previa:

- `aq_quality`
- `aq_score`
- `aq_co2`
- `aq_tvoc`
- `aq_pressure`
- `aqpm2_5`
- `aqpm10`
- posiblemente `aqpm1_0`

Trabajo necesario:

- Confirmar durante unos dias que la IAQ wifi/cloud nueva no vuelve a quedar `No disponible` con `scan_interval: 15`.
- Si vuelve a fallar, subir intervalo Cloud a 20s y observar; despues 25s/30s si hace falta.
- Confirmar que `Comedor` no se duplica en modo complementario cuando no esta seleccionado en `cloud_include_device_ids`.
- Probar el options flow con perfiles y selector de dispositivos Cloud.
- Ajustar unidades/nombres si el payload real devuelve variantes no contempladas.


### 3. Duplicados entre Local y Cloud

Estado actual:

- Ya existen helpers en `coordinator.py`:
  - `scoped_unique_id()`
  - `scoped_device_identifier()`
- Esto evita colisiones tecnicas de ids entre local y cloud.

Pero:

- Evitar colision no evita duplicacion visual/funcional.
- Si cloud crea termostatos y local tambien, Home Assistant mostrara dos juegos de entidades.

Trabajo necesario:

- Filtro por categorias cloud ya implementado.
- Para Albert: no crear `climate_zones` desde Cloud API. En la integracion publica ya no es el default global; se configura dejando solo `energy` + `iaq` en la entrada cloud complementaria.
- Tambien se oculto el webserver cloud cuando `climate_zones` no esta activado, porque duplicaba el Flexa 4 ya presente por Local API.


### 4. Device info y nombres

Hay restos de nomenclatura local en entidades/dispositivos cloud:

- `Local API zone`
- `Local API system`

Trabajo necesario:

- Ajustar `device_info` segun `connection_type`.
- En cloud usar modelos tipo:
  - `Cloud zone`
  - `Cloud IAQ sensor`
  - `Cloud energy meter`
  - o el `cloud_device_type` real si es mas util.


### 5. Diagnosticos y privacidad

Estado actual:

- `diagnostics.py` redacta:
  - `token`
  - `access_token`
  - `refresh_token`
  - `password`

Pendiente:

- Redactar tambien `email`.
- Revisar si conviene ocultar ids cloud sensibles:
  - `user_id`
  - `installation_id`
  - `device_id`
  - `ws_id`


### 6. Traducciones y versionado

Pendiente:

- Completar traducciones del config/options flow cloud en:
  - `ca`
  - `fr`
  - `de`
  - `it`
  - `pt`
  - `eu`
  - `gl`
  - `nl`
- Actualizar changelog cuando el soporte cloud complementario sea usable.
- Subir version cuando toque, probablemente `1.8.0` o similar.


## Orden recomendado de implementacion

1. No tocar Local API salvo regresion.
2. Opciones cloud de inclusion por categoria. Hecho el 26/04/2026.
3. Hacer que Cloud API pueda cargar sin `climate_zones`. Hecho el 26/04/2026.
4. Corregir alta de sensores cloud que no dependan de zonas, empezando por `az_energy_clamp`. Hecho y validado el 26/04/2026.
5. Implementar normalizacion IAQ cloud hacia `coord.iaqs`. Hecho y validado con `Sensor` el 26/04/2026.
6. Evitar duplicados entre IAQ local `Comedor` e IAQ cloud nueva. Hecho mediante `cloud_include_device_ids`.
7. Observar estabilidad Cloud con `scan_interval: 15`. Pendiente.
8. Probar/pulir UX de perfiles Cloud (`full`, `complement_local`, `custom`). Pendiente.
9. Ajustar nombres/modelos de dispositivos cloud si hace falta. Pendiente.
10. Revisar diagnosticos/privacidad. Pendiente.
11. Completar traducciones. Pendiente.
12. Version/changelog para publicar la fase read-only. Pendiente.
13. Solo despues estudiar escritura cloud.


## Ficheros clave

- `custom_components/airzone_control/config_flow.py`
  - opciones cloud de categorias ya anadidas.
- `custom_components/airzone_control/const.py`
  - constantes nuevas para categorias cloud ya anadidas.
- `custom_components/airzone_control/__init__.py`
  - ya pasa opciones cloud al coordinator.
- `custom_components/airzone_control/coordinator_cloud.py`
  - filtro de categorias ya anadido.
  - bandera `expose_webserver_entities` para no duplicar el webserver en modo complementario.
  - mapping medidor inicial ya anadido.
  - mapping IAQ cloud.
- `custom_components/airzone_control/sensor.py`
  - no crea sensores webserver si el coordinator cloud no debe exponerlos.
  - sensores cloud de medidor sin depender de zonas ya anadidos.
  - sensores IAQ cloud si hace falta adaptar nombres/casts.
- `custom_components/airzone_control/binary_sensor.py`
  - no crea binary sensor webserver si el coordinator cloud no debe exponerlo.
  - revisar IAQ/binary cloud si aparecen campos como necesidad de ventilacion.
- `custom_components/airzone_control/climate.py`
  - no deberia crear climas cloud si `climate_zones` esta desactivado.
- `custom_components/airzone_control/diagnostics.py`
  - redaccion de email e ids cloud.
- `custom_components/airzone_control/translations/*.json`
  - textos del selector cloud.


## Criterios de exito para la proxima fase

La fase cloud complementaria se considerara correcta cuando:

- Local API siga igual que ahora.
- Cloud API pueda estar activa sin crear termostatos ni webserver duplicados. Validado el 26/04/2026.
- La entrada cloud de Albert cree el medidor cloud. Validado el 26/04/2026.
- La entrada cloud de Albert cree la IAQ cloud cuando este instalada y visible en Airzone Cloud. Validado con `Sensor` el 26/04/2026.
- La IAQ local del Flexa 4 siga viniendo por Local API.
- La IAQ local `Comedor` no se duplique desde Cloud. Validado configurando `cloud_include_device_ids`.
- La IAQ cloud `Sensor` y el medidor mantengan disponibilidad estable con `scan_interval: 15`. En observacion.
- Los dispositivos cloud tengan nombres/modelos claros.
- No se active escritura cloud todavia.


## Punto exacto para retomar

Estado de pausa del 26/04/2026:

- Buen punto para pausar varios dias.
- No tocar Local API salvo regresion.
- Cloud API de Albert esta en modo complemento:
  - `cloud_profile: complement_local`
  - categorias `energy` + `iaq`
  - `cloud_include_device_ids`: medidor + `Sensor`
  - `scan_interval: 15`
- Validado:
  - medidor visible como `Airzone Energy Meter`
  - IAQ wifi visible como `Sensor`
  - `Comedor` no duplicado desde Cloud
  - webserver/Flexa 4 no duplicado desde Cloud
- En observacion:
  - estabilidad de `Sensor` y medidor con Cloud cada 15s
  - si hay nuevos `No disponible`, subir a 20s y observar
- Siguiente trabajo real:
  - probar options flow de perfiles Cloud y selector de dispositivos
  - pulir device_info/nombres cloud
  - privacidad/diagnosticos
  - traducciones
  - version/changelog


## Notas historicas utiles

- El 12/04/2026 se valido que Cloud API podia autenticar y cargar entidades reales.
- El mismo dia se dejo claro que el medidor nuevo no va por Local API.
- La IAQ nueva aun no estaba instalada entonces.
- La razon de usar Cloud API es precisamente sacar dispositivos wifi/cloud que no aparecen en Local API.
- La entrada Cloud API se elimino posteriormente de Home Assistant porque duplicaba entidades de termostatos ya presentes por Local API.


## Documentacion de referencia

- Web API: https://developers.airzonecloud.com/docs/web-api/
- OpenAPI: https://developers.airzonecloud.com/downloads/webapi.openapi.yml
- Websocket API: https://developers.airzonecloud.com/docs/websocket-api/
