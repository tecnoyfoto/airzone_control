from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
)
from .coordinator import AirzoneCoordinator

_LOGGER = logging.getLogger(__name__)

# Importante: incluir TODAS las plataformas que tenemos implementadas
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recargar la integración cuando cambian options/data (p. ej., grupos)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Cargar integración Airzone Control desde una config entry."""
    host = entry.data.get("host", DEFAULT_HOST)
    port = entry.data.get("port", DEFAULT_PORT)

    # El scan_interval se guarda en options; hacemos fallback a data por compatibilidad
    scan = entry.options.get(
        CONF_SCAN_INTERVAL, entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    )

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

    # Si el usuario cambia opciones (por ejemplo, crea/edita grupos), recargamos la entry
    # para que se creen/eliminar entidades automáticamente sin reiniciar Home Assistant.
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

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
