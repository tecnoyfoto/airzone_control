import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, DEFAULT_PORT
from .coordinator import AirzoneDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Inicializa la integración Airzone Control."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    base_url = f"http://{host}:{port}"

    session = async_get_clientsession(hass)

    # Reducimos el intervalo de actualización a 10 segundos para mejorar la sincronización
    coordinator = AirzoneDataUpdateCoordinator(
        hass,
        session,
        base_url,
        10,  # refresco cada 10s en lugar de 60s
        entry
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN]["coordinator"] = coordinator
    hass.data[DOMAIN]["entry"] = entry

    # Cargar plataformas: climate, sensor, switch y select (para el modo manual global)
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(
            entry,
            ["climate", "sensor", "switch", "select"]
        )
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Desactiva la integración."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        ["climate", "sensor", "switch", "select"]
    )
    if unload_ok:
        hass.data[DOMAIN].pop("coordinator", None)
        hass.data[DOMAIN].pop("entry", None)
    return unload_ok
#fin
