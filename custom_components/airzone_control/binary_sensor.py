"""
Plataforma de binary_sensors para Airzone Control
(punto 6). Muestra, por ejemplo, Batería baja y Ventana abierta.
"""
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN]["coordinator"]
    entities = []
    zones = coordinator.data.get("hvac_zone", {}).get("data", [])

    for zone_data in zones:
        # Batería baja
        if "battery" in zone_data:
            entities.append(AirzoneZoneBatteryLowBinarySensor(coordinator, zone_data))
        # Ventana abierta
        if "open_window" in zone_data:
            entities.append(AirzoneZoneWindowBinarySensor(coordinator, zone_data))

    async_add_entities(entities, True)


class AirzoneZoneBaseBinary(BinarySensorEntity):
    """Clase base para binary_sensors de zona."""
    def __init__(self, coordinator, zone_data):
        self.coordinator = coordinator
        self.zone_data = zone_data
        self._attr_should_poll = False

        self.system_id = zone_data.get("systemID", 1)
        self.zone_id = zone_data.get("zoneID", 0)
        self.zone_name = zone_data.get("name", f"Zone {self.zone_id}")

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        self.coordinator.async_add_listener(self._update)
    
    async def async_will_remove_from_hass(self):
        self.coordinator.async_remove_listener(self._update)
    
    def _update(self):
        # Actualiza zone_data
        zones = self.coordinator.data.get("hvac_zone", {}).get("data", [])
        for z in zones:
            if z.get("systemID") == self.system_id and z.get("zoneID") == self.zone_id:
                self.zone_data = z
                break
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"airzone_{self.system_id}_{self.zone_id}")},
            "name": f"Airzone Zone {self.zone_name}",
            "manufacturer": "Airzone",
            "model": "Local API Thermostat",
        }

class AirzoneZoneBatteryLowBinarySensor(AirzoneZoneBaseBinary):
    """
    Indica True si la batería está baja.
    """
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_name = f"{self.zone_name} Battery Low"
        self._attr_unique_id = f"airzone_battlow_{self.system_id}_{self.zone_id}"

    @property
    def is_on(self):
        battery_val = self.zone_data.get("battery")
        if battery_val is None:
            return False
        # En tu firmware, puede ser un número 0..100 o “Low”.
        try:
            val = int(battery_val)
            return val < 20
        except ValueError:
            return str(battery_val).lower() == "low"

class AirzoneZoneWindowBinarySensor(AirzoneZoneBaseBinary):
    """
    Indica True si la ventana está abierta en la zona.
    """
    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_name = f"{self.zone_name} Window Open"
        self._attr_unique_id = f"airzone_window_{self.system_id}_{self.zone_id}"

    @property
    def is_on(self):
        # “open_window” = 1 => abierta
        return self.zone_data.get("open_window") == 1
