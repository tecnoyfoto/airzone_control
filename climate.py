import logging
import asyncio

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Opcional: mapeo de thermos_type a modelos
THERMOS_TYPE_MAPPING = {
    2: "Lite Wired Thermostat",
    3: "Lite Wireless Thermostat",
    # Agrega otros tipos si los conoces
}

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinator"]
    await coordinator.async_request_refresh()
    zones = coordinator.data.get("hvac_zone", {}).get("data", [])
    _LOGGER.debug("Setting up climate entities. Found zones: %s", zones)
    entities = [AirzoneClimate(coordinator, zone) for zone in zones]
    async_add_entities(entities)

class AirzoneClimate(ClimateEntity):

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE |
        ClimateEntityFeature.TURN_ON |
        ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, zone_data):
        self.coordinator = coordinator
        self.zone_data = zone_data
        zone_name = zone_data.get("name", f"Zone {zone_data.get('zoneID', '?')}")
        self._attr_name = f"Airzone Climate - {zone_name}"
        self.system_id = zone_data.get("systemID") or zone_data.get("systemid") or 1
        self.zone_id = zone_data.get("zoneID") or zone_data.get("zoneid") or 0
        self._attr_unique_id = f"airzone_{self.system_id}_{self.zone_id}_climate"
        self._master_task = None

        # Determinar el modelo a partir de thermos_type
        thermos_type = zone_data.get("thermos_type")
        self._model = THERMOS_TYPE_MAPPING.get(thermos_type, "Local API Thermostat")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"airzone_{self.system_id}_{self.zone_id}")},
            "name": f"Airzone Zone {self.zone_data.get('name', self.zone_id)}",
            "manufacturer": "Airzone",
            "model": self._model,
        }

    @property
    def available(self):
        if not self.coordinator.last_update_success:
            _LOGGER.debug("Zone %s (system %s) - coordinator update failed", self.zone_id, self.system_id)
            return False
        if not self.zone_data:
            _LOGGER.debug("Zone %s (system %s) - zone_data is empty", self.zone_id, self.system_id)
            return False
        return True

    @property
    def hvac_modes(self):
        return [HVACMode.OFF, HVACMode.HEAT]

    @property
    def hvac_mode(self):
        on_val = int(self.zone_data.get("on", 0))
        return HVACMode.OFF if on_val == 0 else HVACMode.HEAT

    @property
    def current_temperature(self):
        return self.zone_data.get("roomTemp")

    @property
    def current_humidity(self):
        return self.zone_data.get("humidity")

    @property
    def target_temperature(self):
        return self.zone_data.get("setpoint") or self.zone_data.get("thermos_setpoint")

    def _desired_mode(self) -> int:
        return 3

    async def async_set_temperature(self, **kwargs):
        if not self.coordinator.last_update_success:
            _LOGGER.error("Coordinator no disponible durante async_set_temperature")
            return

        new_temp = kwargs.get(ATTR_TEMPERATURE)
        if new_temp is None:
            return

        _LOGGER.debug("Datos actuales de zona al establecer temperatura: %s", self.zone_data)

        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {
            "systemID": self.system_id,
            "zoneID": self.zone_id,
            "on": self.zone_data.get("on", 0),
            "mode": self._desired_mode(),
            "setpoint": new_temp
        }
        _LOGGER.debug("Estableciendo temperatura para zona %s con payload: %s", self.zone_id, payload)

        async with self.coordinator.session.put(url, json=payload) as response:
            if response.status != 200:
                _LOGGER.error("Error al establecer temperatura para zona %s: %s", self.zone_id, response.status)

        if self.zone_id != 1:
            await self._force_master_on()

        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        elif hvac_mode == HVACMode.HEAT:
            await self.async_turn_on()

    async def async_turn_on(self):
        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {"systemID": self.system_id, "zoneID": self.zone_id, "on": 1, "mode": self._desired_mode()}
        async with self.coordinator.session.put(url, json=payload) as response:
            if response.status != 200:
                _LOGGER.error("Error al encender la zona %s: %s", self.zone_id, response.status)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {
            "systemID": self.system_id,
            "zoneID": self.zone_id,
            "on": 0,
            "mode": self._desired_mode()
        }
        async with self.coordinator.session.put(url, json=payload) as response:
            if response.status != 200:
                _LOGGER.error("Error al apagar la zona %s: %s", self.zone_id, response.status)
        await self.coordinator.async_request_refresh()

    async def _force_master_on(self):
        # Método vacío para mantener compatibilidad y evitar error.
        return

    @property
    def icon(self) -> str:
        """
        Devuelve un icono dinámico para la zona maestra en función del modo.
        Si esta zona es la maestra (según el campo "master_zoneID" en hvac_system),
        se muestra un icono basado en el valor de 'mode'. De lo contrario se utiliza
        un icono por defecto.
        """
        hvac_system = self.coordinator.data.get("hvac_system", {})
        master_zone = hvac_system.get("master_zoneID", 1)
        if self.zone_id == master_zone:
            mode = self.zone_data.get("mode")
            ICON_MAPPING = {
                0: "mdi:stop-circle",      # Stop
                3: "mdi:weather-sunny",    # Heat (valor 3 se utiliza para Heat)
                1: "mdi:fan",              # Ventilación (si se llegara a utilizar)
                2: "mdi:thermostat-auto"   # Auto u otro modo
            }
            return ICON_MAPPING.get(mode, "mdi:thermostat")
        else:
            return "mdi:thermostat"

    async def async_added_to_hass(self):
        self.coordinator.async_add_listener(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self):
        self.coordinator.async_remove_listener(self._handle_coordinator_update)

    def _handle_coordinator_update(self):
        zones = self.coordinator.data.get("hvac_zone", {}).get("data", [])
        for z in zones:
            if ((z.get("systemID") or z.get("systemid")) == self.system_id and
                (z.get("zoneID") or z.get("zoneid")) == self.zone_id):
                self.zone_data = z
                break
        self.async_write_ha_state()
