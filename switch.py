from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Configura la plataforma de switches para Airzone Control."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    entities = [
        AirzoneSystemOnOffSwitch(coordinator),
        AirzoneSystemEcoSwitch(coordinator),
    ]
    async_add_entities(entities)

class AirzoneSystemOnOffSwitch(SwitchEntity):
    """Switch para encender o apagar el sistema globalmente."""
    _attr_name = "Airzone System On/Off"
    _attr_unique_id = "airzone_system_on_off"

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False

    @property
    def is_on(self):
        hvac_system = self.coordinator.data.get("hvac_system", {})
        return hvac_system.get("on", 0) == 1

    async def async_turn_on(self, **kwargs):
        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {"systemID": self.coordinator.data.get("hvac_system", {}).get("systemID", 1), "on": 1}
        async with self.coordinator.session.put(url, json=payload) as response:
            if response.status != 200:
                _LOGGER.error("Error al encender el sistema: %s", response.status)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {"systemID": self.coordinator.data.get("hvac_system", {}).get("systemID", 1), "on": 0}
        async with self.coordinator.session.put(url, json=payload) as response:
            if response.status != 200:
                _LOGGER.error("Error al apagar el sistema: %s", response.status)
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

class AirzoneSystemEcoSwitch(SwitchEntity):
    """Switch para activar o desactivar el modo ECO."""
    _attr_name = "Airzone ECO Mode"
    _attr_unique_id = "airzone_system_eco"

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False

    @property
    def is_on(self):
        hvac_system = self.coordinator.data.get("hvac_system", {})
        return hvac_system.get("eco", 0) == 1

    async def async_turn_on(self, **kwargs):
        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {"systemID": self.coordinator.data.get("hvac_system", {}).get("systemID", 1), "eco": 1}
        async with self.coordinator.session.put(url, json=payload) as response:
            if response.status != 200:
                _LOGGER.error("Error al activar ECO mode: %s", response.status)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {"systemID": self.coordinator.data.get("hvac_system", {}).get("systemID", 1), "eco": 0}
        async with self.coordinator.session.put(url, json=payload) as response:
            if response.status != 200:
                _LOGGER.error("Error al desactivar ECO mode: %s", response.status)
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }
