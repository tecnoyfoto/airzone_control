[🇬🇧 Read this in English](CHANGELOG.md)

# Changelog

## 1.6.1 - 2025-12-21

### Arreglado
- **Modo Global**: ahora replica el comportamiento de la app de Airzone.
  - El estado del modo global se basa en `mode` (no en `on`).
  - **Apagado/Stop**: aplica `mode=Stop` a nivel global y fuerza `on=0` en todas las zonas.
  - **Calor/Frío/Ventilación/Seco/Auto**: cambia solo el `mode` global (broadcast) sin encender zonas automáticamente.
- UI más coherente: cuando el modo global está en stop, las zonas muestran solo opciones válidas.

## 1.6.0
- Termostatos por zona, termostato maestro, termostatos de grupo y entidades extra según instalación.

## 1.5.1
- Internacionalización (i18n) y ampliación de idiomas.

## 1.5.0
- Selects por zona (Modo, Velocidad, Ventilación IAQ), selector de Modo Global, sensores del Webserver y botones “Hotel”.
