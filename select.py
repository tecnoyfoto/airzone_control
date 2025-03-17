"""Plataforma Select para forzar manualmente el modo del termostato maestro en Airzone Control."""

import logging
from homeassistant.components.select import SelectEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Opciones solo "Stop" y "Cool" según lo acordado
OPTIONS = ["Stop", "Heat"]

async def async_setup_entry(hass, entry, async_add_entities):
    """Configura la plataforma Select para Airzone Control."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([AirzoneManualModeSelect(coordinator)])

class AirzoneManualModeSelect(SelectEntity):
    """Entidad select para forzar manualmente el modo del termostato maestro."""
    _attr_name = "Airzone Manual Mode"
    _attr_unique_id = "airzone_manual_mode"
    _attr_options = OPTIONS
    _attr_icon = "mdi:format-list-bulleted"

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False
        # Al iniciarse, leer el modo actual desde la API
        hvac_system = self.coordinator.data.get("hvac_system", {})
        mode = hvac_system.get("mode")
        if mode == 0:
            self._attr_current_option = "Stop"
        elif mode == 3:
            self._attr_current_option = "Heat"
        else:
            self._attr_current_option = "Heat"  # Valor por defecto si no coincide

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

    async def async_select_option(self, option: str) -> None:
        """Envía el comando para forzar el modo manualmente."""
        self._attr_current_option = option

        # Obtener la zona maestra desde la API usando 'master_zoneID' (por defecto 1)
        hvac_system = self.coordinator.data.get("hvac_system", {})
        master_zone = hvac_system.get("master_zoneID", 1)
        system_id = hvac_system.get("systemID", 1)

        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {"systemID": system_id, "zoneID": master_zone}
        if option == "Stop":
            payload["mode"] = 0
        elif option == "Heat":
            payload["mode"] = 3

        try:
            async with self.coordinator.session.put(url, json=payload) as response:
                if response.status != 200:
                    _LOGGER.error("Error al forzar el modo %s: %s", option, response.status)
        except Exception as err:
            _LOGGER.error("Excepción al forzar el modo %s: %s", option, err)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def current_option(self) -> str:
        return self._attr_current_option
