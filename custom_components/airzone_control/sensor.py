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
        # Solo creamos sensores si el dato existe en la API:
        if zone_data.get("roomTemp") is not None:
            sensors.append(AirzoneZoneTemperatureSensor(coordinator, zone_data))
        if zone_data.get("humidity") is not None:
            sensors.append(AirzoneZoneHumiditySensor(coordinator, zone_data))

        # Batería (si la API reporta algo aprovechable)
        if zone_data.get("battery") is not None:
            sensors.append(AirzoneZoneBatterySensor(coordinator, zone_data))

        # Firmware del termostato
        if zone_data.get("thermos_firmware") is not None:
            sensors.append(AirzoneZoneFirmwareSensor(coordinator, zone_data))

        # Demandas de calor, frío y aire
        if zone_data.get("heat_demand") is not None:
            sensors.append(AirzoneZoneHeatDemandSensor(coordinator, zone_data))
        if zone_data.get("cold_demand") is not None:
            sensors.append(AirzoneZoneColdDemandSensor(coordinator, zone_data))
        if zone_data.get("air_demand") is not None:
            sensors.append(AirzoneZoneAirDemandSensor(coordinator, zone_data))

        # Ventana abierta (open_window)
        if zone_data.get("open_window") is not None:
            sensors.append(AirzoneZoneOpenWindowSensor(coordinator, zone_data))

        # Doble consigna
        if zone_data.get("double_sp") == 1:
            if zone_data.get("coolsetpoint") is not None:
                sensors.append(AirzoneZoneCoolSetpointSensor(coordinator, zone_data))
            if zone_data.get("heatsetpoint") is not None:
                sensors.append(AirzoneZoneHeatSetpointSensor(coordinator, zone_data))

        # NUEVO: sensor de consumo (potencia/energía) - ajusta "consumption_ue" si tu firmware usa otro campo
        if zone_data.get("consumption_ue") is not None:
            sensors.append(AirzoneZoneConsumptionSensor(coordinator, zone_data))

    # -------------------------------------------------------------------------
    # SENSORES IAQ (globales)
    # -------------------------------------------------------------------------
    iaq_data = coordinator.data.get("iaq_data", {})
    if isinstance(iaq_data, dict) and "data" in iaq_data and iaq_data["data"]:
        sensors.append(AirzoneIAQCO2Sensor(coordinator))
        sensors.append(AirzoneIAQPM25Sensor(coordinator))
        sensors.append(AirzoneIAQPM10Sensor(coordinator))
        sensors.append(AirzoneIAQTVOCSensor(coordinator))
        sensors.append(AirzoneIAQPressureSensor(coordinator))
        sensors.append(AirzoneIAQIndexSensor(coordinator))
        sensors.append(AirzoneIAQScoreSensor(coordinator))
        sensors.append(AirzoneIAQVentModeSensor(coordinator))

    # -------------------------------------------------------------------------
    # SENSORES DEL SISTEMA GLOBAL (Airzone System)
    # -------------------------------------------------------------------------
    hvac_system = coordinator.data.get("hvac_system", {})
    # Sensor del modo global
    sensors.append(AirzoneSystemModeSensor(coordinator))

    # Sensor de la velocidad del ventilador
    sensors.append(AirzoneSystemFanSpeedSensor(coordinator))

    # Sensor del modo "dormir"
    sensors.append(AirzoneSystemSleepSensor(coordinator))

    # ID del sistema
    if hvac_system.get("systemID") is not None:
        sensors.append(AirzoneSystemIDSensor(coordinator))

    # Firmware del sistema
    if hvac_system.get("firmware") is not None:
        sensors.append(AirzoneSystemFirmwareSensor(coordinator))

    # Errores del sistema
    if "errors" in hvac_system:
        sensors.append(AirzoneSystemErrorsSensor(coordinator))

    # Unidades del sistema (Celsius / Fahrenheit)
    if "units" in hvac_system:
        sensors.append(AirzoneSystemUnitsSensor(coordinator))

    # Sensor agregado que muestra las zonas con batería baja
    if any(z.get("battery") is not None for z in zones):
        sensors.append(AirzoneLowBatterySensor(coordinator))

    async_add_entities(sensors)

# =============================================================================
#                           CLASE BASE ZONA
# =============================================================================

class AirzoneZoneBaseSensor(SensorEntity):
    """Clase base para los sensores de una zona Airzone."""

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
        """Devuelve True si la última actualización del coordinador fue exitosa."""
        return self.coordinator.last_update_success

    async def async_added_to_hass(self):
        """Se llama cuando la entidad se añade a Home Assistant."""
        self.coordinator.async_add_listener(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self):
        """Se llama cuando la entidad se elimina de Home Assistant."""
        self.coordinator.async_remove_listener(self._handle_coordinator_update)

    def _handle_coordinator_update(self):
        """Actualiza los datos de la zona cuando el coordinador se refresca."""
        all_zones = self.coordinator.data.get("hvac_zone", {}).get("data", [])
        for zinfo in all_zones:
            if zinfo.get("systemID") == self.system_id and zinfo.get("zoneID") == self.zone_id:
                self.zone_data = zinfo
                break
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Devuelve información del dispositivo para agrupar entidades por zona."""
        return {
            "identifiers": {(DOMAIN, f"airzone_{self.system_id}_{self.zone_id}")},
            "via_device": (DOMAIN, f"airzone_{self.system_id}_{self.zone_id}"),
            "manufacturer": "Airzone",
            "model": self._model,
            "name": f"Airzone Zone {self._zone_name}",
        }

# =============================================================================
#                           SENSORES DE ZONA
# =============================================================================

class AirzoneZoneTemperatureSensor(AirzoneZoneBaseSensor):
    """Sensor de temperatura de la zona."""

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

    @property
    def icon(self):
        return "mdi:thermometer"


class AirzoneZoneHumiditySensor(AirzoneZoneBaseSensor):
    """Sensor de humedad de la zona."""

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

    @property
    def icon(self):
        return "mdi:water-percent"


class AirzoneZoneBatterySensor(AirzoneZoneBaseSensor):
    """Muestra la batería de la zona. Ajusta si tu sistema no usa 0-100."""
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
        battery_raw = self.zone_data.get("battery", None)
        if battery_raw is None:
            return None
        # Si se reporta un entero 0..100:
        try:
            battery_val = int(battery_raw)
            if battery_val < 0:
                battery_val = 0
            if battery_val > 100:
                battery_val = 100
            return battery_val
        except ValueError:
            # Si no es un entero, podría ser "Ok"/"Low", etc.
            return None

    @property
    def icon(self):
        # Ícono genérico para batería; se podría personalizar por nivel.
        return "mdi:battery"


class AirzoneZoneFirmwareSensor(AirzoneZoneBaseSensor):
    """Firmware reportado por el termostato de la zona."""

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_firmware_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Firmware"

    @property
    def native_value(self):
        return self.zone_data.get("thermos_firmware")

    @property
    def icon(self):
        return "mdi:chip"


class AirzoneZoneHeatDemandSensor(AirzoneZoneBaseSensor):
    """Sensor que muestra la demanda de calor en la zona."""

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_heat_demand_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Heat Demand"

    @property
    def native_value(self):
        return self.zone_data.get("heat_demand")

    @property
    def icon(self):
        return "mdi:fire"


class AirzoneZoneColdDemandSensor(AirzoneZoneBaseSensor):
    """Sensor que muestra la demanda de frío en la zona."""

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_cold_demand_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Cold Demand"

    @property
    def native_value(self):
        return self.zone_data.get("cold_demand")

    @property
    def icon(self):
        return "mdi:snowflake"


class AirzoneZoneAirDemandSensor(AirzoneZoneBaseSensor):
    """Sensor que muestra la demanda de aire/ventilación en la zona."""

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_air_demand_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Air Demand"

    @property
    def native_value(self):
        return self.zone_data.get("air_demand")

    @property
    def icon(self):
        return "mdi:fan"


class AirzoneZoneOpenWindowSensor(AirzoneZoneBaseSensor):
    """Sensor para el estado de ventana abierta en la zona."""

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

    @property
    def icon(self):
        # Podríamos devolver un ícono distinto según open/closed
        if self.native_value == "Open":
            return "mdi:window-open"
        else:
            return "mdi:window-closed"


class AirzoneZoneCoolSetpointSensor(AirzoneZoneBaseSensor):
    """Sensor que muestra la consigna de frío en modo doble consigna."""

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_cool_setpoint_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Cool Setpoint"

    @property
    def native_value(self):
        return self.zone_data.get("coolsetpoint")

    @property
    def icon(self):
        return "mdi:snowflake-thermometer"


class AirzoneZoneHeatSetpointSensor(AirzoneZoneBaseSensor):
    """Sensor que muestra la consigna de calor en modo doble consigna."""

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_heat_setpoint_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Heat Setpoint"

    @property
    def native_value(self):
        return self.zone_data.get("heatsetpoint")

    @property
    def icon(self):
        return "mdi:fire"


# ===================== NUEVO: SENSOR DE CONSUMO =====================
class AirzoneZoneConsumptionSensor(AirzoneZoneBaseSensor):
    """
    Muestra el valor de consumo/energía/potencia reportado por la API.
    Ajusta el nombre 'consumption_ue' si tu firmware usa otro campo,
    y la unidad si es kWh en vez de W, etc.
    """
    _attr_device_class = SensorDeviceClass.POWER  # o SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    # Si la API da W -> UnitOfPower.WATT
    # Si da kWh -> UnitOfEnergy.KILO_WATT_HOUR
    from homeassistant.const import UnitOfPower
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_unique_id = f"airzone_consumption_{self.system_id}_{self.zone_id}"

    @property
    def name(self):
        return f"{self._zone_name} Consumption"

    @property
    def native_value(self):
        # Ajusta el campo 'consumption_ue' al que use tu API
        return self.zone_data.get("consumption_ue")

    @property
    def icon(self):
        return "mdi:flash"

# =============================================================================
#                          SENSORES IAQ (globales)
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
            return iaq["data"][0]  # Tomamos solo el primer sensor IAQ
        return {}


class AirzoneIAQCO2Sensor(AirzoneIAQBaseSensor):
    """Sensor de CO2 IAQ."""

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

    @property
    def icon(self):
        return "mdi:molecule-co2"


class AirzoneIAQPM25Sensor(AirzoneIAQBaseSensor):
    """Sensor de PM2.5 IAQ."""

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

    @property
    def icon(self):
        return "mdi:air-filter"


class AirzoneIAQPM10Sensor(AirzoneIAQBaseSensor):
    """Sensor de PM10 IAQ."""

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

    @property
    def icon(self):
        return "mdi:air-filter"


class AirzoneIAQTVOCSensor(AirzoneIAQBaseSensor):
    """Sensor de TVOC IAQ."""

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

    @property
    def icon(self):
        return "mdi:air-filter"


class AirzoneIAQPressureSensor(AirzoneIAQBaseSensor):
    """Sensor de presión IAQ."""

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

    @property
    def icon(self):
        return "mdi:gauge"


class AirzoneIAQIndexSensor(AirzoneIAQBaseSensor):
    """Sensor de índice IAQ."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "airzone_iaq_index"

    @property
    def name(self):
        return "Airzone IAQ Index"

    @property
    def native_value(self):
        return self._iaq_data.get("iaq_index")

    @property
    def icon(self):
        return "mdi:gauge"


class AirzoneIAQScoreSensor(AirzoneIAQBaseSensor):
    """Sensor de puntuación IAQ."""

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = "airzone_iaq_score"

    @property
    def name(self):
        return "Airzone IAQ Score"

    @property
    def native_value(self):
        return self._iaq_data.get("iaq_score")

    @property
    def icon(self):
        return "mdi:gauge"


class AirzoneIAQVentModeSensor(AirzoneIAQBaseSensor):
    """Sensor del modo de ventilación IAQ."""

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

    @property
    def icon(self):
        return "mdi:fan"


# =============================================================================
#                SENSORES DEL SISTEMA GLOBAL (Airzone System)
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
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

    @property
    def icon(self):
        return "mdi:information-outline"


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
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

    @property
    def icon(self):
        return "mdi:fan"


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
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

    @property
    def icon(self):
        return "mdi:sleep"


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
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

    @property
    def icon(self):
        return "mdi:numeric"


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
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

    @property
    def icon(self):
        return "mdi:chip"


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
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

    @property
    def icon(self):
        return "mdi:alert-circle"


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
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }

    @property
    def icon(self):
        return "mdi:thermometer"


# =============================================================================
#          SENSOR AGREGADO: DETECTAR BATERÍAS BAJAS EN TODAS LAS ZONAS
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
        """Revisa qué zonas reportan batería baja."""
        zones = self.coordinator.data.get("hvac_zone", {}).get("data", [])
        low_battery_zones = []
        for z in zones:
            name = z.get("name", f"Zona {z.get('zoneID')}")
            battery_level = z.get("battery")
            # Si battery es un número, podrías chequear <20 como ejemplo de "batería baja"
            if battery_level is not None:
                try:
                    level_int = int(battery_level)
                    if level_int < 20:
                        low_battery_zones.append(name)
                except ValueError:
                    # Si no es un número y, por ejemplo, es "Low"
                    if str(battery_level).lower() == "low":
                        low_battery_zones.append(name)

            # Algunas instalaciones devuelven 'Error 8' si la batería está baja
            # o el termostato Lite no se comunica bien.
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
        hvac_system = self.coordinator.data.get("hvac_system", {})
        model_name = hvac_system.get("model", "Airzone System")
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": f"Airzone System {model_name}",
            "manufacturer": "Airzone",
            "model": model_name,
        }

    @property
    def icon(self):
        return "mdi:battery-alert"
