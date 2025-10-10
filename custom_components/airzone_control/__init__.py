from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL
from .coordinator import AirzoneCoordinator

_LOGGER = logging.getLogger(__name__)

# Importante: incluir TODAS las plataformas que tenemos implementadas
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,     # <- faltaba
    Platform.SELECT,
    Platform.SWITCH,      # <- faltaba
    Platform.BUTTON,      # <- faltaba
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Cargar integración Airzone Control desde una config entry."""
    host = entry.data.get("host", DEFAULT_HOST)
    port = entry.data.get("port", DEFAULT_PORT)
    scan = entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    api_prefix = entry.data.get("api_prefix")  # opcional

    coordinator = AirzoneCoordinator(
        hass,
        host=host,
        port=port,
        scan_interval=scan,
        api_prefix=api_prefix,
    )

    # Primer refresco antes de crear entidades
    await coordinator.async_config_entry_first_refresh()

    # Guardamos el coordinator para que las plataformas lo lean
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descargar una config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Cerrar sesión HTTP y limpiar
    bundle = hass.data.get(DOMAIN, {}).pop(entry.entry_id, {})
    coord: AirzoneCoordinator | None = bundle.get("coordinator")
    if coord:
        await coord.async_close()

    return unload_ok
