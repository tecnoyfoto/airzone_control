from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
from .coordinator import AirzoneCoordinator

PLATFORMS = ["climate", "select", "sensor", "binary_sensor", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    scan = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    api_prefix = entry.data.get("api_prefix")  # puede venir del config_flow

    coord = AirzoneCoordinator(
        hass,
        host=host,
        port=port,
        scan_interval=scan,
        api_prefix=api_prefix,
    )
    # Primer refresco para tener datos antes de crear entidades
    await coord.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    # Guardado en forma dict porque varias plataformas lo esperan así
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coord}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    stored = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    coord: AirzoneCoordinator | None = None
    if isinstance(stored, dict):
        coord = stored.get("coordinator")
    if coord:
        await coord.async_close()

    return unload_ok
