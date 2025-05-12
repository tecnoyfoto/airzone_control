import logging
from datetime import timedelta

import aiohttp
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AirzoneDataUpdateCoordinator(DataUpdateCoordinator):
    """
    Coordinador encargado de obtener, combinar y actualizar los datos
    de la API local de Airzone para posteriormente pasarlos
    a las distintas plataformas (climate, select, etc.).
    """

    def __init__(self, hass, session: aiohttp.ClientSession, base_url: str, update_interval: int, config_entry):
        """
        :param hass: Referencia a HomeAssistant
        :param session: Sesión aiohttp para peticiones
        :param base_url: URL base (por ejemplo 'http://192.168.86.77:3000')
        :param update_interval: Frecuencia de actualización en segundos
        :param config_entry: ConfigEntry
        """
        super().__init__(
            hass,
            _LOGGER,
            name="Airzone Data",
            update_interval=timedelta(seconds=update_interval),
        )
        self.session = session
        self.base_url = base_url
        self.config_entry = config_entry

    async def _async_update_data(self):
        """
        Lógica principal que se ejecuta en cada refresco.
        Hace las peticiones necesarias a la API local de Airzone,
        y devuelve un diccionario con toda la info.
        """
        data = {}

        # 1) Petición global del sistema (ej: systemid=1)
        try:
            system_url = f"{self.base_url}/api/v1/hvac?systemid=1"
            async with self.session.get(system_url) as response:
                if response.status == 200:
                    # Forzamos a parsear como JSON, ignorando content-type si hace falta
                    data["hvac_system"] = await response.json(content_type=None)
                else:
                    _LOGGER.error("Error al obtener datos del sistema HVAC: %s", response.status)
                    data["hvac_system"] = {}
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error al conectar con la API de Airzone: {err}") from err

        # 2) Leer datos de zonas 1..8 (o más si tu instalación puede tener más)
        #    Ajusta el rango si sabes cuántas zonas esperas.
        all_zones = []
        for zone_id in range(1, 9):
            zone_url = f"{self.base_url}/api/v1/hvac?systemid=1&zoneid={zone_id}"
            try:
                async with self.session.get(zone_url) as response:
                    if response.status == 200:
                        z_json = await response.json(content_type=None)
                        # Normalmente, la API devuelve un dict con "data": [...]
                        if "data" in z_json and isinstance(z_json["data"], list) and z_json["data"]:
                            # Agregamos todas las zonas que vengan (puede ser una o varias)
                            all_zones.extend(z_json["data"])
                    else:
                        # 404 o 500 indica que esa zona no existe o no está configurada
                        _LOGGER.debug("Zona %s no disponible (HTTP %s)", zone_id, response.status)
            except aiohttp.ClientError as z_err:
                _LOGGER.debug("Error al obtener datos de la zona %s: %s", zone_id, z_err)

        data["hvac_zone"] = {"data": all_zones}

        # 3) (Opcional) IAQ: si tu instalación soporta sensores de calidad de aire
        try:
            iaq_url = f"{self.base_url}/api/v1/iaq?systemid=1&iaqsensorid=1"
            async with self.session.get(iaq_url) as response:
                if response.status == 200:
                    data["iaq_data"] = await response.json(content_type=None)
                else:
                    _LOGGER.debug("IAQ no disponible (HTTP %s)", response.status)
                    data["iaq_data"] = {}
        except aiohttp.ClientError:
            # Si no existe IAQ, no hacemos nada
            pass

        return data
