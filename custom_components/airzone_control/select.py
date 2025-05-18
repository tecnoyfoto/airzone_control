import logging
from homeassistant.components.select import SelectEntity
from homeassistant.const import ATTR_ENTITY_ID
from .const import DOMAIN

import homeassistant.helpers.translation as translation

_LOGGER = logging.getLogger(__name__)

# Mapeo de códigos de modo de la API a claves de traducción y a iconos
MODE_API_MAP = {
    0: ("Stop", "mdi:alert-octagon"),            # Parado
    1: ("Ventilación", "mdi:fan"),               # Solo ventilación
    2: ("Auto", "mdi:autorenew"),                # Automático
    3: ("Calor", "mdi:fire"),                    # Calor
    4: ("Frío", "mdi:snowflake"),                # Frío
    5: ("Seco", "mdi:weather-sunny-alert"),      # Deshumidificar/Seco
    # Puedes añadir más si tu hardware los soporta
}

# Inverso para enviar el código correcto a la API
MODE_NAME_TO_API = {v[0]: k for k, v in MODE_API_MAP.items()}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([AirzoneManualModeSelect(coordinator, hass)])

class AirzoneManualModeSelect(SelectEntity):
    _attr_name = "Airzone Manual Mode"
    _attr_unique_id = "airzone_manual_mode"
    _attr_should_poll = False

    def __init__(self, coordinator, hass):
        self.coordinator = coordinator
        self.hass = hass
        self._attr_options = []
        self._attr_current_option = None
        self._icon = "mdi:thermostat"

        # Inicializar las opciones en el primer arranque
        self._update_modes_from_api()

    def _update_modes_from_api(self):
        """Lee los modos globales disponibles desde la API y los traduce."""
        hvac_system = self.coordinator.data.get("hvac_system", {})
        data = hvac_system.get("data")
        mode_options = []

        # Puede ser un dict o una lista (dependiendo del JSON recibido)
        if isinstance(data, dict):
            modes_api = data.get("modes", [])
            current_mode_code = data.get("mode")
        elif isinstance(data, list) and data:
            modes_api = data[0].get("modes", [])
            current_mode_code = data[0].get("mode")
        else:
            modes_api = []
            current_mode_code = None

        for code in modes_api:
            mode_name = MODE_API_MAP.get(code, (f"Desconocido ({code})", "mdi:help"))[0]
            if mode_name not in mode_options:
                mode_options.append(mode_name)

        # Asegura que haya al menos una opción
        if not mode_options:
            mode_options = [MODE_API_MAP.get(3, ("Calor", "mdi:fire"))[0], MODE_API_MAP.get(0, ("Stop", "mdi:alert-octagon"))[0]]

        self._attr_options = mode_options

        # Poner el modo actual al arrancar
        if current_mode_code in MODE_API_MAP:
            self._attr_current_option = MODE_API_MAP[current_mode_code][0]
        else:
            self._attr_current_option = self._attr_options[0] if self._attr_options else None

    @property
    def icon(self):
        """Devuelve un icono representativo según el modo actual."""
        mode = self.current_option
        for code, (name, icon) in MODE_API_MAP.items():
            if name == mode:
                return icon
        return "mdi:thermostat"

    @property
    def current_option(self):
        # Sincroniza opciones si hay cambio por actualización
        self._update_modes_from_api()
        return self._attr_current_option

    async def async_select_option(self, option: str) -> None:
        """Cambia el modo global enviando un PUT a la API local de Airzone."""
        if option not in self.options:
            _LOGGER.warning("Opción '%s' no está en las opciones permitidas.", option)
            return

        # Obtener código de la API para el modo seleccionado
        api_mode_code = MODE_NAME_TO_API.get(option)
        if api_mode_code is None:
            _LOGGER.error("No se encuentra código API para el modo: %s", option)
            return

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
        self._attr_current_option = option
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Asocia este selector al dispositivo 'System'."""
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

    async def async_update(self):
        self._update_modes_from_api()
        self.async_write_ha_state()
