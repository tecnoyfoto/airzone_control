import logging
from datetime import timedelta

import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

class AirzoneDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinador para obtener datos de la API de Airzone."""

    def __init__(self, hass, session: aiohttp.ClientSession, base_url: str, update_interval: int, config_entry):
        self.session = session
        self.base_url = base_url
        self.config_entry = config_entry  # Guardamos la config_entry
        super().__init__(
            hass,
            _LOGGER,
            name="Airzone Data",
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self):
        """Realiza las peticiones a la API y devuelve los datos combinados."""
        data = {}

        # 1) Datos del sistema
        try:
            system_url = f"{self.base_url}/api/v1/hvac?systemid=1"
            async with self.session.get(system_url) as response:
                if response.status == 200:
                    data["hvac_system"] = await response.json(content_type=None)
                else:
                    _LOGGER.error("Error al obtener datos del sistema HVAC: %s", response.status)
                    data["hvac_system"] = {}
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error al obtener datos del sistema HVAC: {err}") from err

        # 2) Zonas 1..8
        all_zones = []
        for zone_id in range(1, 9):
            zone_url = f"{self.base_url}/api/v1/hvac?systemid=1&zoneid={zone_id}"
            try:
                async with self.session.get(zone_url) as response:
                    if response.status == 200:
                        json_data = await response.json(content_type=None)
                        if "data" in json_data and isinstance(json_data["data"], list) and json_data["data"]:
                            all_zones.extend(json_data["data"])
                    else:
                        _LOGGER.warning("Zona %s no devuelta correctamente (status %s)", zone_id, response.status)
            except aiohttp.ClientError as err:
                _LOGGER.warning("Error al obtener datos de la zona %s: %s", zone_id, err)

        data["hvac_zone"] = {"data": all_zones}

        # 3) IAQ
        try:
            iaq_url = f"{self.base_url}/api/v1/iaq?systemid=1&iaqsensorid=1"
            async with self.session.get(iaq_url) as response:
                if response.status == 200:
                    data["iaq_data"] = await response.json(content_type=None)
                else:
                    _LOGGER.error("Error al obtener datos IAQ: %s", response.status)
                    data["iaq_data"] = {}
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error al obtener datos IAQ: {err}") from err

        return data
