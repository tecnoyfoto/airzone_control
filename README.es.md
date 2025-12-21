[🇬🇧 Read this in English](README.md)

# Integración Airzone Control (API Local) – Home Assistant

Integración **no oficial** para controlar y supervisar sistemas Airzone mediante su **API Local** (puerto 3000). Funciona **sin nube** y está pensada para instalaciones con varias zonas y/o varios equipos Airzone en la misma red.

A diferencia de la integración oficial, **Airzone Control**:
- Soporta **varios dispositivos** (Airzone Webserver / Aidoo Pro / Aidoo Pro Fancoil), cada uno con sus zonas y sensores.
- Expone más entidades: temperatura de zona, errores, datos del webserver (firmware, señal Wi‑Fi, canal), **IAQ** (CO₂, PM, TVOC, presión, score), perfiles/diagnóstico, etc.
- Agrupa entidades por **dispositivo** y **zona**, facilitando paneles y automatizaciones.
- Ofrece selector de **“Modo maestro”** (parada/calefacción) cuando el equipo lo permite.

> **Importante:** la API Local vive en **Airzone Webserver** o **Aidoo Pro**. Controladoras como **Flexa 3** por sí solas **no exponen** la API REST. Necesitas tener Webserver/Aidoo en la instalación.

---

## ✨ Novedades (v1.6.1)

### ✅ Modo Global: comportamiento idéntico a la app de Airzone
A partir de esta versión, el **Modo Global** replica al 100% el comportamiento real de la app:

- El estado del **Modo Global** se basa en el campo `mode` (modo global), **no** en si las zonas están encendidas/apagadas (`on`).
  - Ejemplo: si el sistema está en **Calor** pero todas las zonas están `on=0`, el Modo Global debe seguir mostrando **Calor** (porque el modo permitido es Calor).

- Al seleccionar **Apagado/Stop** (modo global):
  - se aplica el `mode` de Stop a nivel global **y**
  - se fuerzan **todas las zonas a `on=0`** (apagadas).
  - Resultado: nadie puede encender zonas hasta que el administrador quite el stop.

- Al seleccionar **Calor / Frío / Ventilación / Seco / Auto** (según lo que exponga tu API):
  - se cambia **solo** el `mode` global (broadcast),
  - **sin encender zonas automáticamente** (las zonas mantienen su `on` actual).
  - Resultado: se “permite” el modo, pero cada zona sigue siendo independiente.

### 🧠 UI más coherente
Cuando el Modo Global está en **Stop/Apagado**, es normal que en los termostatos/selects individuales **solo aparezcan opciones válidas** (por ejemplo, solo “Apagado”). Esto evita seleccionar modos que el sistema no aceptará mientras el bloqueo global esté activo.

---

## ✨ Novedades (v1.6.0)

### Qué añade
- Termostatos por zona (un `climate` por cada zona).
- Termostato maestro (por sistema Airzone).
- **Termostatos de grupo** (un `climate` por grupo):
  - Cambiar temperatura, modo y **encender/apagar**.
  - Aplica la acción a todas las zonas del grupo.
- Entidades extra (sensores/selects/switches/botones) según tu instalación.

---

## 📦 Instalación

1. Copia esta carpeta en:
   `config/custom_components/airzone_control/`
2. Reinicia Home Assistant.
3. Añade la integración desde:
   **Configuración → Dispositivos y servicios → Añadir integración → Airzone Control**

---

## ⚙️ Configuración

### Configuración básica
- **Host**: IP del webserver de Airzone
- **Puerto**: puerto del webserver
- La integración autodetecta el prefijo de API (y permite seleccionarlo manualmente si hace falta).

### Opciones
Abre:
**Configuración → Dispositivos y servicios → Airzone Control → (rueda dentada) Opciones**

Aquí puedes configurar:
- **Intervalo de sondeo**
- **Grupos (UI fácil)**
- **Grupos (JSON avanzado)**

---

## 👥 Termostatos de grupo

### UI fácil (recomendado)
En **Opciones** verás varios “slots” de grupo (por defecto: 8):
- **Grupo X – Nombre**
- **Grupo X – Zonas** (lista de checks)

Deja vacío `Grupos (JSON avanzado)`, guarda, y aparecerán los `climate.*` nuevos para tus grupos.

> Nota: al guardar opciones, la integración se recarga automáticamente y aparecen los grupos sin reiniciar Home Assistant.

### JSON avanzado (sin límite real)
Si rellenas `Grupos (JSON avanzado)`, tiene prioridad y se ignoran los grupos creados en la UI.
Formato:

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

---

## ✨ Novedades (v1.5.1)

### 🌐 Internacionalización (i18n)
- Traducciones completamente actualizadas para:
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
- Estructura unificada de `translation_key` para todas las entidades (`sensor`, `select`, `button`, etc.)
- Correcciones menores en los nombres de entidades.
- Sin cambios funcionales en la lógica de la integración.

---

## ✨ Novedades (v1.5.0)

- Nuevos `select` por zona: **Modo**, **Velocidad**, y **Ventilación IAQ**.
- Selector de **Modo Global** para cambiar todas las zonas a la vez.
- Nuevos sensores del **Webserver**: conexión nube, firmware, tipo, calidad Wi‑Fi y más.
- **Botones Hotel** rediseñados con soporte completo: encender, apagar, copiar consigna.
- Todas las nuevas entidades incluyen traducciones y `unique_id` estables.
- Soporte extendido y probado para la API Local **v1.76 y v1.77**.
- Mejora general de estructura de entidades, soporte multi‑dispositivo y robustez.
- **Multi‑dispositivo:** añade **varios Airzone** en la misma red (un *config entry* por equipo).
- **Autodescubrimiento (mDNS) + alta manual:** si tu red lo permite, verás los equipos en *Descubierto*; si no, añádelos por IP.
- **Mejoras de robustez** leyendo capacidades y distintos firmwares de la Local API.

> 🧨 **Breaking change:** para evitar colisiones entre sistemas/zonas, algunos `unique_id` internos han cambiado. Home Assistant podría cambiar ciertos `entity_id` existentes (consulta **Migración**).

---

## ✅ Requisitos

- **Airzone Webserver** o **Aidoo Pro/Fancoil** con **Local API v1** (puerto **3000**).
- Acceso de Home Assistant a la IP del dispositivo (misma LAN o con rutas/firewall configurados).

**Comprobación rápida de API:**
- En el navegador:
  - `http://<IP>:3000/api/v1/webserver` → JSON con datos del equipo
  - `http://<IP>:3000/api/v1/version` → `{"schema":"1.xx"}`
- Si no responden, ese equipo no expone la API Local (o hay problema de red/firmware).

---

## 📦 Instalación (detallada)

### Vía HACS (recomendada)
1. **HACS → Integrations →** ⋮ **Custom repositories**.
2. Añade `https://github.com/tecnoyfoto/airzone_control` (*Integration*).
3. Instala **Airzone Control** y **reinicia** Home Assistant.

### Manual
1. Copia `custom_components/airzone_control` a tu carpeta de configuración:

```
custom_components/
  └── airzone_control/
      ├── __init__.py
      ├── manifest.json
      ├── config_flow.py
      ├── const.py
      ├── coordinator.py
      ├── api_modes.py
      ├── climate.py
      ├── i18n.py
      ├── sensor.py
      ├── binary_sensor.py
      ├── select.py
      ├── switch.py
      ├── button.py
      └── translations/
          ├── en.json
          ├── es.json
          ├── ca.json
          ├── fr.json
          ├── it.json
          ├── pt.json
          ├── de.json
          ├── gl.json
          ├── nl.json
          └── eu.json
```

2. **Reinicia** Home Assistant.

---

## ⚙️ Configuración (detallada)

### Autodescubrimiento (mDNS)
- Ve a **Ajustes → Dispositivos y servicios → Descubierto** y pulsa **Configurar** en cada Airzone que aparezca.
- Si tu red no permite mDNS (VLAN, aislamiento Wi‑Fi, etc.), usa el alta manual.

### Alta manual (IP)
1. **Ajustes → Dispositivos y servicios → + Añadir integración → Airzone Control**
2. Host = **IP del Webserver/Aidoo**, Puerto = **3000**.

### Varias instalaciones
- Repite el alta (descubierto o manual) **una vez por cada equipo**.
- La integración creará un *entry* por equipo, con sus **zonas** y **sensores**.

---

## 🗂️ Entidades

### Clima (por zona)
- Encendido/apagado, consigna, modos disponibles según API (Heat/Cool/Dry/Fan/Auto/Stop).
- Próxima versión: **velocidades de ventilador dinámicas** (mapear `speed/speeds/speed_values/speed_type`).

### Sensores
- **Zona:** Temperatura, errores, (otros si la API los expone).
- **Sistema:** Errores, perfil/diagnóstico, número de zonas, etc.
- **Webserver:** Firmware, calidad Wi‑Fi, RSSI, canal, interfaz, MAC, tipo.
- **IAQ:** CO₂, PM2.5, PM10, TVOC, presión, score/índice (si hay sensores Airzone IAQ).

---

## 🔁 Migración (Breaking change)

Para permitir **varios equipos** sin colisiones, algunos `unique_id` ahora son **únicos por sistema/zona**. Home Assistant ata los `entity_id` a esos `unique_id`, así que **pueden cambiar** ciertos `entity_id` tras actualizar.

**Qué hacer si ves “Entidad no encontrada”:**
1. **Ajustes → Entidades**, filtra por **Integración: Airzone Control**, localiza la nueva entidad.
2. Si quieres conservar el nombre anterior, edita la entidad y cambia su **ID de entidad**.
3. Actualiza automatizaciones/dashboards que muestren avisos.

> Consejo: haz un **backup** antes de actualizar.

---

## 🛠️ Solución de problemas

- **No conecta:** usa la **IP del Webserver/Aidoo** (no la de la controladora), comprueba `/webserver` y `/version`, revisa firewall/VLAN.
- **Faltan modos:** dependen de lo que la API exponga para esa zona. Revisa el perfil en la app Airzone o comparte el JSON de `/hvac`.
- **No aparece en Descubierto:** añade por IP (mDNS puede estar bloqueado en tu red).

---

## 🧭 Compatibilidad rápida

- **Sí:** Airzone **Webserver** (Hub/5G/Wi‑Fi), **Aidoo Pro**, **Aidoo Pro Fancoil** con Local API v1.
- **No:** **Flexa 3** sola (sin Webserver/Aidoo) — no expone la API REST.
- **Puerto:** 3000. Endpoints principales: `/api/v1/webserver`, `/api/v1/version`, `/api/v1/hvac`, `/api/v1/iaq`.

---

## 🌐 Traducciones disponibles

Esta integración está traducida a los siguientes idiomas:
- Español 🇪🇸
- Inglés 🇬🇧
- Catalán 🇨🇦
- Francés 🇫🇷
- Italiano 🇮🇹
- Portugués 🇵🇹
- Alemán 🇩🇪
- Gallego 🇬🇷
- Neerlandés 🇳🇱
- Euskera 🇪🇺

---

## 🤝 Contribuir

Sugerencias, issues y PRs:
**Repo:** https://github.com/tecnoyfoto/airzone_control

---

### 📄 Historial de cambios

Consulta el historial completo de versiones en [`CHANGELOG.md`](./CHANGELOG.md)

## 📜 Licencia
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
