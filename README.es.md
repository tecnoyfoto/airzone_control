# Integración Airzone Control (API Local) – Home Assistant

[🇬🇧 Read this in English](README.md)

Integración **no oficial** para controlar y supervisar sistemas Airzone mediante su **API Local** (puerto 3000). Funciona **sin nube** y está pensada para instalaciones con varias zonas y/o varios equipos Airzone en la misma red.

A diferencia de la integración oficial, **Airzone Control**:
- Soporta **varios dispositivos** (Airzone Webserver / Aidoo Pro / Aidoo Pro Fancoil), cada uno con sus zonas y sensores.
- Expone más entidades: temperatura de zona, errores, datos del webserver (firmware, señal Wi-Fi, canal), **IAQ** (CO₂, PM, TVOC, presión, score), perfiles/diagnóstico, etc.
- Agrupa entidades por **dispositivo** y **zona**, facilitando paneles y automatizaciones.
- Ofrece selector de **“Modo maestro”** (parada/calefacción) cuando el equipo lo permite.

> **Importante:** la API Local vive en **Airzone Webserver** o **Aidoo Pro**. Controladoras como **Flexa 3** por sí solas **no exponen** la API REST. Necesitas tener Webserver/Aidoo en la instalación.

---

## ✨ Novedades (v1.5.0)

- Nuevos `select` por zona: **Modo**, **Velocidad**, y **Ventilación IAQ**.
- Selector de **Modo Global** para cambiar todas las zonas a la vez.
- Nuevos sensores del **Webserver**: conexión nube, firmware, tipo, calidad Wi-Fi y más.
- **Botones Hotel** rediseñados con soporte completo: encender, apagar, copiar consigna.
- Todas las nuevas entidades incluyen traducciones y `unique_id` estables.
- Soporte extendido y probado para la API Local **v1.76 y v1.77**.
- Mejora general de estructura de entidades, soporte multi-dispositivo y robustez.

- **Multi-dispositivo:** añade **varios Airzone** en la misma red (un *config entry* por equipo).
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

## 📦 Instalación

### Vía HACS (recomendada)
1. **HACS → Integrations →** ⋮ **Custom repositories**.  
2. Añade `https://github.com/tecnoyfoto/airzone_control` (*Integration*).  
3. Instala **Airzone Control** y **reinicia** Home Assistant.

### Manual
1. Copia `custom_components/airzone_control` a tu carpeta de configuración:

custom_components/
  └── airzone_control/
    ├── init.py
    ├── manifest.json
    ├── config_flow.py
    ├── const.py
    ├── coordinator.py
    ├── api_modes.py
    ├── climate.py
    ├── sensor.py
    ├── binary_sensor.py
    ├── select.py
    ├── switch.py
    ├── button.py
    └── translations/
      ├── en.json
      ├── es.json
      └── ca.json
      
2. **Reinicia** Home Assistant.

---

## ⚙️ Configuración

### Autodescubrimiento (mDNS)
- Ve a **Ajustes → Dispositivos y servicios → Descubierto** y pulsa **Configurar** en cada Airzone que aparezca.
- Si tu red no permite mDNS (VLAN, aislamiento Wi-Fi, etc.), usa el alta manual.

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
- **Webserver:** Firmware, calidad Wi-Fi, RSSI, canal, interfaz, MAC, tipo.  
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

- **Sí:** Airzone **Webserver** (Hub/5G/Wi-Fi), **Aidoo Pro**, **Aidoo Pro Fancoil** con Local API v1.  
- **No:** **Flexa 3** sola (sin Webserver/Aidoo) — no expone la API REST.  
- **Puerto:** 3000. Endpoints principales: `/api/v1/webserver`, `/api/v1/version`, `/api/v1/hvac`, `/api/v1/iaq`.

---

## 📈 Roadmap (1.5.0)

- **Velocidad de ventilador dinámica** (select por zona + sincronía con `fan_mode`).  
- **Actualizar firmware desde Home Assistant** (si el equipo/API lo soporta).  
- Mejoras de diagnósticos.

---

## 🤝 Contribuir

Sugerencias, issues y PRs:  
**Repo:** https://github.com/tecnoyfoto/airzone_control

---


---

### 📄 Historial de cambios

Consulta el historial completo de versiones en [`CHANGELOG.md`](./CHANGELOG.md)


## 📜 Licencia
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)
