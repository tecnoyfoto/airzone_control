import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    UnitOfTemperature,
    ATTR_TEMPERATURE,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Mapeos de la API a modos HVAC
API_TO_HVAC_MODE = {
    0: HVACMode.OFF,
    1: HVACMode.FAN_ONLY,
    2: HVACMode.AUTO,
    3: HVACMode.HEAT,
    4: HVACMode.COOL,
    5: HVACMode.DRY,
}

HVAC_MODE_TO_API = {
    HVACMode.OFF: 0,
    HVACMode.FAN_ONLY: 1,
    HVACMode.AUTO: 2,
    HVACMode.HEAT: 3,
    HVACMode.COOL: 4,
    HVACMode.DRY: 5,
}

# Mapeo de termostatos
THERMOS_TYPE_MAPPING = {
    2: "Lite Wired Thermostat",
    3: "Lite Wireless Thermostat",
    # ...
}


async def async_setup_entry(hass, entry, async_add_entities):
    """
    Configura la plataforma 'climate' para la integración Airzone Control.
    """
    coordinator = hass.data[DOMAIN]["coordinator"]
    await coordinator.async_request_refresh()
    zones = coordinator.data.get("hvac_zone", {}).get("data", [])

    _LOGGER.debug("Configurar Climate. Zonas encontradas: %s", zones)

    entities = []
    for zone_data in zones:
        entities.append(AirzoneClimate(coordinator, zone_data))

    async_add_entities(entities)


class AirzoneClimate(ClimateEntity):
    """
    Entidad Climate para cada zona de Airzone, con fan_mode y swing_mode.
    """

    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, zone_data):
        self.coordinator = coordinator
        self.zone_data = zone_data

        zone_id = zone_data.get("zoneID", 0)
        system_id = zone_data.get("systemID", 1)
        zone_name = zone_data.get("name", f"Zone {zone_id}")

        self._attr_name = f"Airzone Climate - {zone_name}"
        self._attr_unique_id = f"airzone_{system_id}_{zone_id}_climate"

        thermos_type = zone_data.get("thermos_type")
        self._model = THERMOS_TYPE_MAPPING.get(thermos_type, "Local API Thermostat")

    @property
    def device_info(self):
        system_id = self.zone_data.get("systemID", 1)
        zone_id = self.zone_data.get("zoneID", 0)
        zone_name = self.zone_data.get("name", f"Zone {zone_id}")
        return {
            "identifiers": {(DOMAIN, f"airzone_{system_id}_{zone_id}")},
            "name": f"Airzone Zone {zone_name}",
            "manufacturer": "Airzone",
            "model": self._model,
        }

    @property
    def available(self):
        return self.coordinator.last_update_success and bool(self.zone_data)

    @property
    def supported_features(self):
        """
        Determina qué características soporta esta zona:
        - TARGET_TEMPERATURE, ON/OFF siempre.
        - FAN_MODE si existen speed_values.
        - SWING_MODE si existen slats/horizontal/vertical.
        """
        base = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        # Fan
        if self.zone_data.get("speed_values"):
            base |= ClimateEntityFeature.FAN_MODE
        # Slats
        if "slats_vswing" in self.zone_data or "slats_hswing" in self.zone_data:
            base |= ClimateEntityFeature.SWING_MODE
        return base

    @property
    def hvac_modes(self):
        """Lee la lista 'modes' de la zona y la convierte a HVACMode."""
        zone_modes = self.zone_data.get("modes", [])
        if not zone_modes:
            return [HVACMode.OFF, HVACMode.HEAT]  # Fallback
        results = []
        for code in zone_modes:
            ha_mode = API_TO_HVAC_MODE.get(code)
            if ha_mode and ha_mode not in results:
                results.append(ha_mode)
        # Asegurar OFF
        if HVACMode.OFF not in results:
            results.insert(0, HVACMode.OFF)
        return results

    @property
    def hvac_mode(self):
        if int(self.zone_data.get("on", 0)) == 0:
            return HVACMode.OFF
        mode_code = self.zone_data.get("mode", 3)
        return API_TO_HVAC_MODE.get(mode_code, HVACMode.HEAT)

    @property
    def current_temperature(self):
        return self.zone_data.get("roomTemp")

    @property
    def current_humidity(self):
        return self.zone_data.get("humidity")

    @property
    def target_temperature(self):
        return self.zone_data.get("setpoint")

    async def async_set_temperature(self, **kwargs):
        if not self.coordinator.last_update_success:
            _LOGGER.error("Coordinator no disponible para set_temperature.")
            return
        new_temp = kwargs.get(ATTR_TEMPERATURE)
        if new_temp is None:
            return
        _LOGGER.debug("Setpoint -> %s, zona %s", new_temp, self.zone_data.get("zoneID"))
        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {
            "systemID": self.zone_data.get("systemID", 1),
            "zoneID": self.zone_data.get("zoneID", 0),
            "on": self.zone_data.get("on", 0),
            "mode": self.zone_data.get("mode", 3),
            "setpoint": new_temp
        }
        async with self.coordinator.session.put(url, json=payload) as resp:
            if resp.status != 200:
                _LOGGER.error("Error set_temperature. HTTP %s", resp.status)
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on(hvac_mode)

    async def async_turn_on(self, hvac_mode=HVACMode.HEAT):
        mode_code = HVAC_MODE_TO_API.get(hvac_mode, 3)
        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {
            "systemID": self.zone_data.get("systemID", 1),
            "zoneID": self.zone_data.get("zoneID", 0),
            "on": 1,
            "mode": mode_code
        }
        async with self.coordinator.session.put(url, json=payload) as resp:
            if resp.status != 200:
                _LOGGER.error("Error turn_on. HTTP %s", resp.status)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self):
        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {
            "systemID": self.zone_data.get("systemID", 1),
            "zoneID": self.zone_data.get("zoneID", 0),
            "on": 0,
            "mode": 0
        }
        async with self.coordinator.session.put(url, json=payload) as resp:
            if resp.status != 200:
                _LOGGER.error("Error turn_off. HTTP %s", resp.status)
        await self.coordinator.async_request_refresh()

    #
    # --------------- FAN MODE ---------------
    #
    @property
    def fan_modes(self):
        """
        Lee speed_values de la API y mapea a strings de fan mode.
        Ej: [0,1,2,3] => ["Off","Low","Med","High"]
        Ajusta a tu gusto.
        """
        raw_speeds = self.zone_data.get("speed_values")
        if not raw_speeds:
            return None
        result = []
        for val in raw_speeds:
            if val == 0:
                result.append("Off")
            elif val == 1:
                result.append("Low")
            elif val == 2:
                result.append("Medium")
            elif val == 3:
                result.append("High")
            # etc. Ajusta a tu API
        return result

    @property
    def fan_mode(self):
        """
        Mapea self.zone_data["speed"] a un string de la lista anterior.
        """
        current_speed = self.zone_data.get("speed")
        if current_speed == 0:
            return "Off"
        elif current_speed == 1:
            return "Low"
        elif current_speed == 2:
            return "Medium"
        elif current_speed == 3:
            return "High"
        return None

    async def async_set_fan_mode(self, fan_mode):
        """
        Convierte un string ("Low","Medium","High") al número que exige la API y hace PUT.
        """
        speed_val = None
        if fan_mode == "Off":
            speed_val = 0
        elif fan_mode == "Low":
            speed_val = 1
        elif fan_mode == "Medium":
            speed_val = 2
        elif fan_mode == "High":
            speed_val = 3

        if speed_val is None:
            return
        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {
            "systemID": self.zone_data.get("systemID", 1),
            "zoneID": self.zone_data.get("zoneID", 0),
            "on": 1,  # encendido
            "mode": self.zone_data.get("mode", 3),
            "speed": speed_val
        }
        async with self.coordinator.session.put(url, json=payload) as resp:
            if resp.status != 200:
                _LOGGER.error("Error set_fan_mode => %s. HTTP %s", fan_mode, resp.status)
        await self.coordinator.async_request_refresh()

    #
    # --------------- SWING MODE (SLATS) ---------------
    #
    @property
    def swing_modes(self):
        """
        Lista de modos de oscilación. Ajusta a tus valores reales.
        """
        if "slats_vswing" not in self.zone_data and "slats_hswing" not in self.zone_data:
            return None
        return ["Off", "Vertical", "Horizontal", "Both"]

    @property
    def swing_mode(self):
        if "slats_vswing" not in self.zone_data and "slats_hswing" not in self.zone_data:
            return None
        vswing = self.zone_data.get("slats_vswing", 0)
        hswing = self.zone_data.get("slats_hswing", 0)
        if vswing == 1 and hswing == 1:
            return "Both"
        elif vswing == 1:
            return "Vertical"
        elif hswing == 1:
            return "Horizontal"
        else:
            return "Off"

    async def async_set_swing_mode(self, swing_mode):
        if "slats_vswing" not in self.zone_data and "slats_hswing" not in self.zone_data:
            return
        vswing = 0
        hswing = 0
        if swing_mode == "Vertical":
            vswing = 1
        elif swing_mode == "Horizontal":
            hswing = 1
        elif swing_mode == "Both":
            vswing = 1
            hswing = 1

        url = f"{self.coordinator.base_url}/api/v1/hvac"
        payload = {
            "systemID": self.zone_data.get("systemID", 1),
            "zoneID": self.zone_data.get("zoneID", 0),
            "on": 1,
            "mode": self.zone_data.get("mode", 3),
            "slats_vswing": vswing,
            "slats_hswing": hswing
        }
        async with self.coordinator.session.put(url, json=payload) as resp:
            if resp.status != 200:
                _LOGGER.error("Error set_swing_mode => %s. HTTP %s", swing_mode, resp.status)
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        self.coordinator.async_add_listener(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self):
        self.coordinator.async_remove_listener(self._handle_coordinator_update)

    def _handle_coordinator_update(self):
        all_zones = self.coordinator.data.get("hvac_zone", {}).get("data", [])
        my_zone_id = self.zone_data.get("zoneID", 0)
        my_system_id = self.zone_data.get("systemID", 1)
        for z in all_zones:
            if z.get("zoneID") == my_zone_id and z.get("systemID") == my_system_id:
                self.zone_data = z
                break
        self.async_write_ha_state()

    @property
    def icon(self):
        return "mdi:thermostat"
