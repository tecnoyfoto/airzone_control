import logging
from homeassistant.components.select import SelectEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Solo Stop y Heat
MODE_API_MAP = {
    0: "Stop",
    3: "Heat",
}
MODE_NAME_TO_API = {v: k for k, v in MODE_API_MAP.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([AirzoneManualModeSelect(coordinator)])


class AirzoneManualModeSelect(SelectEntity):
    _attr_name = "Airzone Manual Mode"
    _attr_unique_id = "airzone_manual_mode"
    _attr_should_poll = False

    def __init__(self, coordinator):
        self.coordinator = coordinator
        # Solo mostramos Stop y Heat
        self._attr_options = list(MODE_NAME_TO_API.keys())  # ["Stop", "Heat"]
        self._attr_current_option = "Stop"  # Valor inicial por defecto

        # Intentamos leer el modo actual del sistema desde la API
        hvac_system = self.coordinator.data.get("hvac_system", {})
        data = hvac_system.get("data")

        if isinstance(data, dict):
            current_mode = data.get("mode")
            if current_mode in MODE_API_MAP:
                self._attr_current_option = MODE_API_MAP[current_mode]
        elif isinstance(data, list) and data:
            system_obj = data[0]
            current_mode = system_obj.get("mode")
            if current_mode in MODE_API_MAP:
                self._attr_current_option = MODE_API_MAP[current_mode]

    @property
    def icon(self):
        """Devuelve un icono distinto según el modo actual."""
        if self.current_option == "Stop":
            return "mdi:alert-octagon"
        elif self.current_option == "Heat":
            return "mdi:thermometer"
        return "mdi:thermostat"

    @property
    def current_option(self):
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Cambia el modo maestro enviando un PUT a la API local de Airzone."""
        if option not in self.options:
            _LOGGER.warning("Opción '%s' no está en las opciones permitidas.", option)
            return

        self._attr_current_option = option

        hvac_system = self.coordinator.data.get("hvac_system", {})
        system_id = 1
        master_zone_id = 1

        if isinstance(hvac_system.get("data"), dict):
            system_id = hvac_system["data"].get("systemID", 1)
            master_zone_id = hvac_system["data"].get("master_zoneID", 1)
        elif isinstance(hvac_system.get("data"), list) and hvac_system["data"]:
            first_sys = hvac_system["data"][0]
            system_id = first_sys.get("systemID", 1)
            master_zone_id = first_sys.get("master_zoneID", 1)

        # Convierte "Stop" o "Heat" en el código API (0 o 3)
        api_mode_code = MODE_NAME_TO_API[option]

        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {
            "systemID": system_id,
            "zoneID": master_zone_id,
            "mode": api_mode_code
        }
        _LOGGER.debug("Cambiando modo maestro a %s (código=%s)", option, api_mode_code)

        try:
            async with self.coordinator.session.put(url, json=payload) as response:
                if response.status != 200:
                    _LOGGER.error("Error al forzar modo '%s': HTTP %s", option, response.status)
        except Exception as err:
            _LOGGER.error("Excepción al enviar modo '%s': %s", option, err)

        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Asocia este selector al dispositivo 'System'."""
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "System",
            "manufacturer": "Airzone",
            "model": "System",
        }
