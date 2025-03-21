"""Plataforma de sensores para Airzone Control."""

import logging
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, PERCENTAGE

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Mapeo de thermos_type a modelos de termostatos
THERMOS_TYPE_MAPPING = {
    2: "Lite Wired Thermostat",
    3: "Lite Wireless Thermostat",
    # Agrega otros tipos si los conoces
}

async def async_setup_entry(hass, entry, async_add_entities):
    """Configura la plataforma de sensores para Airzone Control."""
    coordinator = hass.data[DOMAIN]["coordinator"]
    sensors = []

    # -------------------------------------------------------------------------
    # SENSORES DE ZONA
    # -------------------------------------------------------------------------
    zones = coordinator.data.get("hvac_zone", {}).get("data", [])
    for zone_data in zones:
        # Filtrar solo si hay roomTemp, humidity... o si no deseas filtrar, déjalo así
        if zone_data.get("roomTemp") is not None:
            sensors.append(AirzoneZoneTemperatureSensor(coordinator, zone_data))
        if zone_data.get("humidity") is not None:
            sensors.append(AirzoneZoneHumiditySensor(coordinator, zone_data))

        # Si no tienes un valor de batería en porcentaje, podrías condicionar.
        # Si battery es un número 0..100:
        if zone_data.get("battery") is not None:
            sensors.append(AirzoneZoneBatterySensor(coordinator, zone_data))

        if zone_data.get("thermos_firmware") is not None:
            sensors.append(AirzoneZoneFirmwareSensor(coordinator, zone_data))

        if zone_data.get("heat_demand") is not None:
            sensors.append(AirzoneZoneHeatDemandSensor(coordinator, zone_data))
        if zone_data.get("cold_demand") is not None:
            sensors.append(AirzoneZoneColdDemandSensor(coordinator, zone_data))
        if zone_data.get("air_demand") is not None:
            sensors.append(AirzoneZoneAirDemandSensor(coordinator, zone_data))
        if zone_data.get("open_window") is not None:
            sensors.append(AirzoneZoneOpenWindowSensor(coordinator, zone_data))

        # Doble consigna
        if zone_data.get("double_sp") == 1:
            if zone_data.get("coolsetpoint") is not None:
                sensors.append(AirzoneZoneCoolSetpointSensor(coordinator, zone_data))
            if zone_data.get("heatsetpoint") is not None:
                sensors.append(AirzoneZoneHeatSetpointSensor(coordinator, zone_data))

    # -------------------------------------------------------------------------
    # SENSORES IAQ (globales)
    # -------------------------------------------------------------------------
    sensors.append(AirzoneIAQCO2Sensor(coordinator))
    sensors.append(AirzoneIAQPM25Sensor(coordinator))
    sensors.append(AirzoneIAQPM10Sensor(coordinator))
    sensors.append(AirzoneIAQTVOCSensor(coordinator))
    sensors.append(AirzoneIAQPressureSensor(coordinator))
    sensors.append(AirzoneIAQIndexSensor(coordinator))
    sensors.append(AirzoneIAQScoreSensor(coordinator))
    sensors.append(AirzoneIAQVentModeSensor(coordinator))

    # -------------------------------------------------------------------------
    # SENSORES DEL SISTEMA GLOBAL (Airzone Flex A4)
    # -------------------------------------------------------------------------
    sensors.append(AirzoneSystemModeSensor(coordinator))
    sensors.append(AirzoneSystemFanSpeedSensor(coordinator))
    sensors.append(AirzoneSystemSleepSensor(coordinator))
    hvac_system = coordinator.data.get("hvac_system", {})
    if hvac_system.get("systemID") is not None:
        sensors.append(AirzoneSystemIDSensor(coordinator))
    if hvac_system.get("firmware"):
        sensors.append(AirzoneSystemFirmwareSensor(coordinator))
    if "errors" in hvac_system:
        sensors.append(AirzoneSystemErrorsSensor(coordinator))
    if "units" in hvac_system:
        sensors.append(AirzoneSystemUnitsSensor(coordinator))
    if any(z.get("battery") is not None for z in zones):
        sensors.append(AirzoneLowBatterySensor(coordinator))

    async_add_entities(sensors)

# =============================================================================
#                           SENSORES DE ZONA
# =============================================================================

class AirzoneZoneBaseSensor(SensorEntity):
    """Clase base para los sensores de una zona."""

    def __init__(self, coordinator, zone_data):
        self.coordinator = coordinator
        self.zone_data = zone_data
        self._attr_should_poll = False
        self.system_id = zone_data.get("systemID", 1)
        self.zone_id = zone_data.get("zoneID", 0)
        self._zone_name = zone_data.get("name", f"Zona {self.zone_id}")
        self._attr_unique_id = None

        # Determinar el modelo del termostato
        thermos_type = zone_data.get("thermos_type")
        self._model = THERMOS_TYPE_MAPPING.get(thermos_type, "Local API Thermostat")

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        self.coordinator.async_add_listener(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self):
        self.coordinator.async_remove_listener(self._handle_coordinator_update)

    def _handle_coordinator_update(self):
        all_zones = self.coordinator.data.get("hvac_zone", {}).get("data", [])
        for zinfo in all_zones:
            if zinfo.get("systemID") == self.system_id and zinfo.get("zoneID") == self.zone_id:
                self.zone_data = zinfo
                break
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"airzone_{self.system_id}_{self.zone_id}")},
            "via_device": (DOMAIN, f"airzone_{self.system_id}_{self.zone_id}"),
            "manufacturer": "Airzone",
            "model": self._model,
            "name": f"Airzone Zone {self._zone_name}",
        }

class AirzoneZoneTemperatureSensor(AirzoneZoneBaseSensor):
    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_temp_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Temperature"

    @property
    def native_unit_of_measurement(self):
        return UnitOfTemperature.CELSIUS

    @property
    def native_value(self):
        return self.zone_data.get("roomTemp")

class AirzoneZoneHumiditySensor(AirzoneZoneBaseSensor):
    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_humidity_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Humidity"

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def native_value(self):
        return self.zone_data.get("humidity")

class AirzoneZoneBatterySensor(AirzoneZoneBaseSensor):
    """Muestra la batería como porcentaje. Ajustar si tu sistema no usa 0-100."""
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_battery_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Battery"

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def native_value(self):
        # Si el sistema usa 0..100, devolvemos ese valor.
        # Si no lo hace, ajusta la lógica.
        battery_raw = self.zone_data.get("battery", None)
        if battery_raw is None:
            return None

        # Si el firmware reporta 'battery' como un entero de 0..100:
        # De lo contrario, si es "Ok"/"Low", no se mostrará como porcentaje.
        try:
            battery_val = int(battery_raw)
            if battery_val < 0:
                battery_val = 0
            if battery_val > 100:
                battery_val = 100
            return battery_val
        except ValueError:
            # Si no es un entero, podrías devolver None o un valor por defecto
            return None

class AirzoneZoneFirmwareSensor(AirzoneZoneBaseSensor):
    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_firmware_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Firmware"

    @property
    def native_value(self):
        return self.zone_data.get("thermos_firmware")

# Nuevos sensores opcionales de zona

class AirzoneZoneHeatDemandSensor(AirzoneZoneBaseSensor):
    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_heat_demand_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Heat Demand"

    @property
    def native_value(self):
        return self.zone_data.get("heat_demand")

class AirzoneZoneColdDemandSensor(AirzoneZoneBaseSensor):
    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_cold_demand_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Cold Demand"

    @property
    def native_value(self):
        return self.zone_data.get("cold_demand")

class AirzoneZoneAirDemandSensor(AirzoneZoneBaseSensor):
    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_air_demand_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Air Demand"

    @property
    def native_value(self):
        return self.zone_data.get("air_demand")

class AirzoneZoneOpenWindowSensor(AirzoneZoneBaseSensor):
    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_open_window_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Open Window"

    @property
    def native_value(self):
        value = self.zone_data.get("open_window")
        if value is None:
            return None
        return "Open" if value == 1 else "Closed"

class AirzoneZoneCoolSetpointSensor(AirzoneZoneBaseSensor):
    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_cool_setpoint_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Cool Setpoint"

    @property
    def native_value(self):
        return self.zone_data.get("coolsetpoint")

class AirzoneZoneHeatSetpointSensor(AirzoneZoneBaseSensor):
    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_heat_setpoint_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Heat Setpoint"

    @property
    def native_value(self):
        return self.zone_data.get("heatsetpoint")

# =============================================================================
# SENSORES IAQ (globales)
# =============================================================================

class AirzoneIAQBaseSensor(SensorEntity):
    """Base para los sensores IAQ globales."""
    _attr_should_poll = False

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_unique_id = None

    @property
    def available(self):
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        self.coordinator.async_add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        self.coordinator.async_remove_listener(self.async_write_ha_state)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "airzone_iaq")},
            "name": "Airzone IAQ Sensor",
            "manufacturer": "Airzone",
            "model": "Local API IAQ",
        }

    @property
    def _iaq_data(self):
        iaq = self.coordinator.data.get("iaq_data", {})
        if "data" in iaq and isinstance(iaq["data"], list) and iaq["data"]:
            return iaq["data"][0]
        return {}

class AirzoneIAQCO2Sensor(AirzoneIAQBaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "airzone_iaq_co2"

    @property
    def name(self):
        return "Airzone IAQ CO₂"

    @property
    def native_unit_of_measurement(self):
        return "ppm"

    @property
    def native_value(self):
        return self._iaq_data.get("co2_value")

class AirzoneIAQPM25Sensor(AirzoneIAQBaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "airzone_iaq_pm25"

    @property
    def name(self):
        return "Airzone IAQ PM2.5"

    @property
    def native_unit_of_measurement(self):
        return "µg/m³"

    @property
    def native_value(self):
        return self._iaq_data.get("pm2_5_value")

class AirzoneIAQPM10Sensor(AirzoneIAQBaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "airzone_iaq_pm10"

    @property
    def name(self):
        return "Airzone IAQ PM10"

    @property
    def native_unit_of_measurement(self):
        return "µg/m³"

    @property
    def native_value(self):
        return self._iaq_data.get("pm10_value")

class AirzoneIAQTVOCSensor(AirzoneIAQBaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "airzone_iaq_tvoc"

    @property
    def name(self):
        return "Airzone IAQ TVOC"

    @property
    def native_unit_of_measurement(self):
        return "ppb"

    @property
    def native_value(self):
        return self._iaq_data.get("tvoc_value")

class AirzoneIAQPressureSensor(AirzoneIAQBaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "airzone_iaq_pressure"

    @property
    def name(self):
        return "Airzone IAQ Pressure"

    @property
    def native_unit_of_measurement(self):
        return "hPa"

    @property
    def native_value(self):
        return self._iaq_data.get("pressure_value")

class AirzoneIAQIndexSensor(AirzoneIAQBaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "airzone_iaq_index"

    @property
    def name(self):
        return "Airzone IAQ Index"

    @property
    def native_value(self):
        return self._iaq_data.get("iaq_index")

class AirzoneIAQScoreSensor(AirzoneIAQBaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "airzone_iaq_score"

    @property
    def name(self):
        return "Airzone IAQ Score"

    @property
    def native_value(self):
        return self._iaq_data.get("iaq_score")

class AirzoneIAQVentModeSensor(AirzoneIAQBaseSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "airzone_iaq_ventmode"

    @property
    def name(self):
        return "Airzone IAQ Vent Mode"

    @property
    def native_value(self):
        raw = self._iaq_data.get("iaq_mode_vent")
        if raw == 0:
            return "Off"
        elif raw == 1:
            return "On"
        elif raw == 2:
            return "Auto"
        return None

# =============================================================================
# SENSORES DEL SISTEMA GLOBAL (Airzone Flex A4)
# =============================================================================

class AirzoneSystemModeSensor(SensorEntity):
    """Sensor que muestra el modo global del sistema."""
    _attr_name = "Airzone System Mode"
    _attr_unique_id = "airzone_system_mode"
    _attr_native_unit_of_measurement = None

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False

    @property
    def native_value(self):
        hvac_system = self.coordinator.data.get("hvac_system", {})
        mode = hvac_system.get("mode")
        if mode is None:
            return None
        mode_mapping = {0: "Stop", 3: "Heat", 1: "Ventilación", 2: "Auto"}
        return mode_mapping.get(mode, mode)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone Flex A4",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

class AirzoneSystemFanSpeedSensor(SensorEntity):
    """Sensor que muestra la velocidad del ventilador del sistema."""
    _attr_name = "Airzone Fan Speed"
    _attr_unique_id = "airzone_system_fan_speed"
    _attr_native_unit_of_measurement = None

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False

    @property
    def native_value(self):
        hvac_system = self.coordinator.data.get("hvac_system", {})
        return hvac_system.get("speed")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone Flex A4",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

class AirzoneSystemSleepSensor(SensorEntity):
    """Sensor que indica si el modo dormir está activado."""
    _attr_name = "Airzone Sleep Mode"
    _attr_unique_id = "airzone_system_sleep"
    _attr_native_unit_of_measurement = None

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False

    @property
    def native_value(self):
        hvac_system = self.coordinator.data.get("hvac_system", {})
        sleep_value = hvac_system.get("sleep")
        if sleep_value is None:
            return None
        return "On" if sleep_value == 1 else "Off"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone Flex A4",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

class AirzoneSystemIDSensor(SensorEntity):
    """Muestra el systemID del sistema global."""
    _attr_name = "Airzone System ID"
    _attr_unique_id = "airzone_system_id"

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False

    @property
    def native_value(self):
        hvac_system = self.coordinator.data.get("hvac_system", {})
        return hvac_system.get("systemID")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone Flex A4",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

class AirzoneSystemFirmwareSensor(SensorEntity):
    """Muestra la versión de firmware del sistema."""
    _attr_name = "Airzone System Firmware"
    _attr_unique_id = "airzone_system_firmware"

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False

    @property
    def native_value(self):
        hvac_system = self.coordinator.data.get("hvac_system", {})
        return hvac_system.get("firmware")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone Flex A4",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

class AirzoneSystemErrorsSensor(SensorEntity):
    """Muestra los errores globales del sistema."""
    _attr_name = "Airzone System Errors"
    _attr_unique_id = "airzone_system_errors"

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False

    @property
    def native_value(self):
        hvac_system = self.coordinator.data.get("hvac_system", {})
        errors = hvac_system.get("errors", [])
        if not errors:
            return "No errors"
        return ", ".join(str(e) for e in errors)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone Flex A4",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

class AirzoneSystemUnitsSensor(SensorEntity):
    """Muestra las unidades globales del sistema (0=Celsius, 1=Fahrenheit)."""
    _attr_name = "Airzone System Units"
    _attr_unique_id = "airzone_system_units"

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False

    @property
    def native_value(self):
        hvac_system = self.coordinator.data.get("hvac_system", {})
        units = hvac_system.get("units")
        if units is None:
            return None
        units_map = {0: "Celsius", 1: "Fahrenheit"}
        return units_map.get(units, f"Unknown ({units})")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone Flex A4",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

# =============================================================================
# SENSOR AGREGADO: BATERÍAS BAJAS
# =============================================================================

class AirzoneLowBatterySensor(SensorEntity):
    """Sensor que agrega las zonas con batería baja."""
    _attr_name = "Zones amb Bateria Baixa"
    _attr_unique_id = "airzone_low_battery"

    def __init__(self, coordinator):
        self.coordinator = coordinator
        self._attr_should_poll = False
        self._attr_native_value = "Ninguna"

    async def async_added_to_hass(self):
        self.coordinator.async_add_listener(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self):
        self.coordinator.async_remove_listener(self._handle_coordinator_update)

    def _handle_coordinator_update(self):
        zones = self.coordinator.data.get("hvac_zone", {}).get("data", [])
        low_battery_zones = []
        for z in zones:
            name = z.get("name", f"Zona {z.get('zoneID')}")
            battery_level = z.get("battery")
            # Si tu battery es un número, podrías chequear < 20, etc.
            # O si es un "Ok"/"Low", etc. Ajusta la lógica a tu caso real.
            if battery_level is not None:
                try:
                    level_int = int(battery_level)
                    if level_int < 20:
                        low_battery_zones.append(name)
                except ValueError:
                    # Si no es un número, por ejemplo "Low", "Ok"
                    if battery_level.lower() == "low":
                        low_battery_zones.append(name)

            errors = z.get("errors", [])
            for err in errors:
                if "Error 8" in err.values():
                    if name not in low_battery_zones:
                        low_battery_zones.append(name)
                    break

        self._attr_native_value = ", ".join(low_battery_zones) if low_battery_zones else "Ninguna"
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone Flex A4",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }
