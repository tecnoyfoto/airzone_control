[🇪🇸 Leer en español](CHANGELOG.es.md) • [🇬🇧 Read this in English](CHANGELOG.md)

# Registro de cambios

## [1.5.1] - 2025-10-11

### 🌐 Internacionalización (i18n)
- Revisión completa de traducciones en:
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
- Unificación del formato de claves `translation_key` en todas las entidades (`sensor`, `select`, `button`, etc.).
- Correcciones menores en nombres de entidades traducidas.
- Sin cambios funcionales en la lógica de la integración.

---

## [1.5.0] - 2025-10-10

- Control por zona mediante `select`: permite cambiar el modo de funcionamiento individual sin afectar al modo global.
- Nuevos sensores añadidos: `zone_profile`, `system_profile`, `transport`, `errors`, etc.
- Nuevos botones de control hotel: `encender todo`, `apagar todo`, `copiar consigna`.
- Sensor global de errores y sensor de errores por zona, con textos traducidos.
- Se añade soporte para mostrar los modos disponibles dinámicamente desde la API.
