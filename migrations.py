async def async_migrate_entry(hass, config_entry):
    """Ejemplo de migración."""
    config_entry.version = 1
    return True
