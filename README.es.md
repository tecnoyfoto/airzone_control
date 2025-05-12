# Integración Airzone Control

[🇬🇧 Read this document in English](README.md)

Esta integración personalizada permite controlar y supervisar sistemas Airzone HVAC mediante su API local (puerto 3000). A diferencia de la integración oficial de Home Assistant, **Airzone Control**:

- Soporta instalaciones con varias zonas.  
- Expone más sensores (temperatura, humedad, batería, firmware, IAQ, diagnóstico, consumo).  
- Agrupa entidades por dispositivo.  
- Ofrece un selector “Modo Maestro” para anular el termostato central.

---

## 📦 Instalación

### Vía HACS (recomendado)

1. En Home Assistant, ve a **HACS → Integraciones**.  
2. Pulsa ⋮ (arriba a la derecha) → **Repositorios personalizados**.  
3. Añade:
   - **Repositorio**: `https://github.com/tecnoyfoto/airzone_control`
   - **Categoría**: **Integración**  
4. Haz clic en **Add/Añadir**.  
5. En **HACS → Integraciones**, busca **Airzone Control**, instala y reinicia Home Assistant.

### Manual

> Solo si no usas HACS.  

1. Clona o descarga en `<config_dir>/custom_components/airzone_control` con esta estructura:

   ```
   custom_components/
   └── airzone_control/
       ├── __init__.py
       ├── manifest.json
       ├── config_flow.py
       ├── const.py
       ├── coordinator.py
       ├── climate.py
       ├── sensor.py
       ├── switch.py
       ├── select.py
       └── translations/
           ├── es.json
           ├── en.json
           └── ca.json
   ```
2. Reinicia Home Assistant.  
3. Ve a **Ajustes → Dispositivos y Servicios → + Añadir integración**, busca **Airzone Control**, introduce IP y puerto (`3000`), y acepta.

---

## ⚙️ Configuración

- Detecta automáticamente zonas 1–8 (ajustable).  
- Dispositivo “Airzone System” agrupa sensores y switches globales.  
- Selector “Airzone Manual Mode” para forzar **Parado** ⛔ o **Calor** 🔥.

---

## 🗂️ Entidades

### Clima
- Una entidad `climate` por zona: encendido, modo, consigna, ventilador y oscilación.

### Sensores
- **Zonas**: temperatura, humedad, batería, firmware, demandas, ventana abierta, doble consigna, consumo.  
- **IAQ**: CO₂, PM2.5, PM10, TVOC, presión, índice, puntuación, modo ventilación.  
- **Sistema**: modo, velocidad de ventilador, modo dormir, ID, firmware, errores, unidades.  
- **Agregado**: “Zones amb Bateria Baixa”.

### Switches
- **Airzone System On/Off**  
- **Airzone ECO Mode** (si lo soporta tu API)

### Selector
- **Airzone Manual Mode** (Stop/Heat)

---

## 📝 Changelog

### v1.1.1 – Compliant con HACS
- Estructura en `custom_components/airzone_control/`  
- `version` actualizado a **1.1.1**  

### v1.1.0 – Soporte HACS
- Añadido `hacs.json` (`"content_in_root": false`).  
- Campo `authors` con **Tecnoyfoto**.  

Consulta todos los cambios en [Releases][release-link].

---

## 💡 Preguntas frecuentes

- **¿Solo algunas zonas muestran humedad?**  
  Algunos termostatos inalámbricos no reportan humedad o lo hacen intermitentemente.  
- **¿Qué es “Error 8”?**  
  Problema de comunicación del termostato Lite, suele indicar batería baja.

---

## 🤝 Contribuciones

¡Se aceptan PRs e issues en [GitHub][repo-link]!

---

## 📜 Licencia

Licencia [Creative Commons Atribución-NoComercial-CompartirIgual 4.0][license-link].

---

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-orange  
[hacs-link]: https://github.com/hacs/integration  
[release-badge]: https://img.shields.io/github/v/release/tecnoyfoto/airzone_control?label=versión  
[release-link]: https://github.com/tecnoyfoto/airzone_control/releases  
[repo-link]: https://github.com/tecnoyfoto/airzone_control  
[license-link]: https://creativecommons.org/licenses/by-nc-sa/4.0/
