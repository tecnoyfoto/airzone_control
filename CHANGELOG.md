[🇪🇸 Leer en español](CHANGELOG.es.md) • [🇬🇧 Read this in English](CHANGELOG.md)

# Changelog

## [1.5.1] - 2025-10-11

### 🌐 Internationalization (i18n)
- Fully updated translations for:
  - 🇪🇸 Spanish
  - 🇬🇧 English
  - 🇨🇦 Catalan
  - 🇫🇷 French
  - 🇮🇹 Italian
  - 🇵🇹 Portuguese
  - 🇩🇪 German
- Added support for new languages:
  - 🇬🇷 Galician (`gl`)
  - 🇳🇱 Dutch (`nl`)
  - 🇪🇺 Basque (`eu`)
- Unified `translation_key` structure for all entities (`sensor`, `select`, `button`, etc.).
- Minor corrections in entity names.
- No functional changes to the integration logic.

---

## [1.5.0] - 2025-10-10

- Added per-zone mode selection via `select`: allows changing the mode of an individual zone without affecting the global mode.
- New sensors: `zone_profile`, `system_profile`, `transport`, `errors`, and more.
- New hotel buttons: `turn all on`, `turn all off`, `copy setpoint`.
- Global error sensor and per-zone error sensors with translated text messages.
- Dynamic support for available modes pulled directly from the API.
