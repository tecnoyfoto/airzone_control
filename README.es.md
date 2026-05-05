[Read this in English](README.md)

# Airzone Control para Home Assistant

Airzone Control es una integración personalizada **no oficial** para Home Assistant orientada a instalaciones Airzone.

Soporta dos modos de conexión:

- **Local API**: el camino recomendado para el control diario de climatización mediante un Airzone Webserver o Aidoo dentro de tu red local.
- **Cloud API**: soporte opcional **solo lectura** para dispositivos que solo aparecen en Airzone Cloud, como medidores de energía cloud y sondas IAQ Wi-Fi.

La integración está pensada para instalaciones con varias zonas, sensores IAQ y, si hace falta, varios equipos Airzone en la misma instancia de Home Assistant.

## Estado Actual

La versión `1.8.0` añade la primera fase pública de Cloud API. El soporte Cloud es conservador a propósito:

- Las entidades Cloud son de solo lectura.
- La escritura Cloud está desactivada.
- Las plataformas `select`, `switch` y `button` no se crean para entradas Cloud.
- Las entidades climate Cloud pueden exponerse, pero son de solo lectura.
- El intervalo de sondeo Cloud por defecto es de `30` segundos.

Configuración mixta recomendada:

- Usa **Local API** para termostatos y sondas IAQ conectadas localmente.
- Añade una entrada **Cloud API** solo para dispositivos que no salen por Local API.
- Usa el perfil Cloud **Complementar Local API** y selecciona exactamente los dispositivos Cloud que quieras publicar.

## Puntos Destacados

- Termostatos por zona local.
- Termostato maestro por sistema.
- Termostatos de grupo opcionales.
- Sensores, selects, switches y botones dinámicos según lo que exponga cada equipo.
- Sondas IAQ: CO2, TVOC, PM2.5, PM10, presión, score/índice y calidad textual cuando está disponible.
- Diagnóstico del webserver: firmware, calidad Wi-Fi, RSSI, canal y conectividad cuando está disponible.
- Medidores de energía Cloud.
- Sondas IAQ Wi-Fi Cloud.
- Varias entradas de configuración, para que Local API y Cloud API puedan convivir sin colisiones de identificadores.
- Descarga de diagnósticos con datos sensibles redactados.

## Requisitos

Para Local API:

- Airzone Webserver, Airzone Hub, Aidoo Pro o Aidoo Pro Fancoil con Local API v1.
- Home Assistant debe poder acceder a la IP del equipo.
- Puerto habitual de Local API: `3000`.

Para Cloud API:

- Cuenta de Airzone Cloud.
- Dispositivos Cloud visibles en esa cuenta.
- Acceso a internet desde Home Assistant hacia Airzone Cloud.

Importante: controladoras como Flexa 3 por sí solas pueden no exponer la API REST local. Normalmente necesitas un Webserver/Aidoo para usar Local API.

## Instalación

### HACS

1. Abre **HACS -> Integrations**.
2. Abre el menú de tres puntos y entra en **Custom repositories**.
3. Añade `https://github.com/tecnoyfoto/airzone_control` como **Integration**.
4. Instala **Airzone Control**.
5. Reinicia Home Assistant.

### Manual

Copia la carpeta de la integración en tu configuración de Home Assistant:

```text
config/
  custom_components/
    airzone_control/
      __init__.py
      manifest.json
      config_flow.py
      const.py
      coordinator.py
      coordinator_cloud.py
      climate.py
      sensor.py
      binary_sensor.py
      select.py
      switch.py
      button.py
      translations/
```

Después reinicia Home Assistant.

## Configuración

Añade la integración desde:

**Ajustes -> Dispositivos y servicios -> Añadir integración -> Airzone Control**

El flujo te pedirá elegir el tipo de conexión.

### Local API

Usa este modo para la instalación principal de climatización.

Campos:

- **Host**: IP del Airzone Webserver/Aidoo.
- **Puerto**: normalmente `3000`.

La integración intenta detectar automáticamente el prefijo correcto de la API. Si no puede detectarlo, permite elegirlo manualmente.

Comprobaciones rápidas:

```text
http://<IP>:3000/api/v1/webserver
http://<IP>:3000/api/v1/version
```

### Cloud API

Usa este modo cuando necesites dispositivos que no aparecen por Local API.

Campos:

- Email de Airzone Cloud.
- Contraseña de Airzone Cloud.
- Perfil Cloud.
- Categorías/dispositivos a publicar.

Perfiles Cloud:

- **Usar todos los dispositivos Cloud API**: publica todas las categorías Cloud soportadas.
- **Complementar Local API**: pensado para instalaciones mixtas Local + Cloud. Activa categorías de energía e IAQ y permite elegir dispositivos concretos.
- **Personalizado**: permite elegir categorías y dispositivos manualmente.

Para una instalación Local + Cloud, elige **Complementar Local API** y selecciona solo el medidor Cloud o las sondas IAQ Wi-Fi que realmente quieras. Si dejas vacía la selección de dispositivos, esa entrada complementaria no publicará dispositivos Cloud.

## Opciones

Abre:

**Ajustes -> Dispositivos y servicios -> Airzone Control -> Configurar**

Opciones habituales:

- Intervalo de sondeo.
- Grupos lógicos de zonas.
- Perfil Cloud y filtros de categoría/dispositivo en entradas Cloud.

Al guardar opciones, la integración se recarga automáticamente.

## Termostatos de Grupo

Los grupos permiten crear una entidad de termostato que controla varias zonas Local API.

UI sencilla:

- Define el nombre del grupo.
- Selecciona las zonas.
- Guarda opciones.

Ejemplo JSON avanzado:

```json
[
  {
    "id": "zona_dia",
    "name": "Zona día",
    "zones": ["1/3", "1/4", "1/5"]
  },
  {
    "id": "zona_noche",
    "name": "Zona noche",
    "zones": ["1/1", "1/2"]
  }
]
```

## Entidades

Local API puede exponer:

- Entidades climate por zona.
- Entidades climate maestras por sistema.
- Entidades climate de grupo.
- Temperatura, consigna, modo, velocidad, temporizador y lamas por zona cuando están disponibles.
- Sensores y switches de sistema.
- Sensores de webserver.
- Sensores IAQ y entidades de ventilación.
- Botones tipo Hotel para encender/apagar todas las zonas cuando están soportados.

Cloud API puede exponer:

- Zonas climate de solo lectura cuando se habilitan.
- Sondas IAQ Cloud.
- Sensores de medidor energético Cloud.
- Datos Cloud ACS/auxiliares cuando están soportados por la integración.

## Privacidad y Diagnósticos

Los diagnósticos redactan datos sensibles, incluyendo:

- Contraseñas y tokens.
- Email.
- Campos relacionados con host/IP.
- Identificadores Cloud de usuario, instalación, webserver y dispositivo.
- MAC, números de serie e identificadores únicos.

Los IDs de dispositivos Cloud pueden usarse internamente para filtros estables, pero se redactan en la exportación de diagnósticos.

## Limitaciones Conocidas

- Cloud API es solo lectura en esta versión.
- La escritura Cloud está desactivada hasta que pueda validarse con seguridad.
- El sondeo Cloud debe ser conservador. El valor público por defecto es `30` segundos.
- La clasificación de algunos campos del medidor para Energy Dashboard puede requerir confirmación, porque algunos contadores Airzone parecen reiniciarse por periodo.
- No todos los equipos Airzone exponen los mismos campos de Local API; las entidades se crean dinámicamente cuando existen datos.

## Solución de Problemas

- **Local API no conecta**: usa la IP del Webserver/Aidoo, no la de la controladora. Revisa puerto `3000`, firewall/VLAN y el endpoint `/webserver`.
- **No aparece descubierto**: añádelo manualmente por IP. La red puede bloquear mDNS.
- **Faltan entidades**: el equipo conectado puede no exponer esos campos.
- **Termostatos duplicados tras añadir Cloud**: usa el perfil Cloud **Complementar Local API** y filtra cuidadosamente los dispositivos Cloud.
- **IAQ o energía Cloud pasan a no disponible**: sube el intervalo de sondeo Cloud y revisa la disponibilidad de Airzone Cloud.

## Compatibilidad

Objetivos Local API conocidos:

- Airzone Webserver / Hub / 5G / Webserver Wi-Fi.
- Aidoo Pro.
- Aidoo Pro Fancoil.

Familias Cloud conocidas que maneja actualmente la integración:

- `az_zone`, `aidoo`, `aidoo_it`
- `az_airqsensor`
- `az_energy_clamp`
- `az_acs`, `aidoo_acs`
- `az_vmc`, `az_relay`, `az_dehumidifier`

## Traducciones

Idiomas incluidos:

- Inglés
- Español
- Catalán
- Francés
- Alemán
- Italiano
- Portugués
- Euskera
- Gallego
- Neerlandés

Algunas cadenas Cloud nuevas pueden aparecer en inglés en idiomas secundarios hasta que se revisen las traducciones nativas.

## Historial de Cambios

Consulta [CHANGELOG.es.md](CHANGELOG.es.md).

## Licencia

[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
