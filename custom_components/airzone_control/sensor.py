from __future__ import annotations

import logging
from typing import Any, List, Tuple

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfPressure,
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import AirzoneCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities):
    data = hass.data.get(DOMAIN, {})
    coord: AirzoneCoordinator | None = None
    if isinstance(data, dict):
        coord = data.get(entry.entry_id, {}).get("coordinator")
    if not isinstance(coord, AirzoneCoordinator):
        return

    entities: list[SensorEntity] = []

    # Webserver
    entities.extend(_build_webserver_sensors(coord))

    # Systems (sensores + errores + PERFIL DETECTADO)
    for sid in sorted({sid for (sid, _) in (coord.data or {}).keys()}):
        entities.extend(_build_system_sensors(coord, sid))
        entities.append(SystemErrorsTextSensor(coord, sid))
        entities.append(SystemProfileSensor(coord, sid))     # <- NUEVO

    # Zones (sensores + PERFIL DE ZONA)
    for (sid, zid), _ in (coord.data or {}).items():
        entities.extend(_build_zone_sensors(coord, sid, zid))
        entities.append(ZoneProfileSensor(coord, sid, zid))  # <- NUEVO

    # IAQ real (o fallback)
    if coord.iaqs:
        entities.extend(_build_iaq_sensors(coord))
    elif coord.iaq_fallback:
        entities.extend(_build_iaq_fallback_sensors(coord))

    add_entities(entities)

# ---------------- builders ----------------

def _build_webserver_sensors(coord: AirzoneCoordinator) -> list[SensorEntity]:
    return [
        WebserverFirmwareSensor(coord),
        WebserverWifiQualitySensor(coord),
        WebserverRssiSensor(coord),
        WebserverWifiChannelSensor(coord),
        WebserverInterfaceSensor(coord),
        WebserverCloudSensor(coord),
        WebserverMacSensor(coord),
        WebserverTypeSensor(coord),
    ]

def _build_system_sensors(coord: AirzoneCoordinator, sid: int) -> list[SensorEntity]:
    fields: list[tuple[str, str, str | None]] = [
        ("ext_temp",    "Temperatura exterior", UnitOfTemperature.CELSIUS),
        ("temp_return", "Temperatura retorno",  UnitOfTemperature.CELSIUS),
        ("work_temp",   "Temperatura trabajo",  UnitOfTemperature.CELSIUS),
    ]
    out: list[SensorEntity] = []
    for key, name, unit in fields:
        out.append(SystemNumberSensor(coord, sid, key=key, name=name, unit=unit))
    return out

def _build_zone_sensors(coord: AirzoneCoordinator, sid: int, zid: int) -> list[SensorEntity]:
    return [
        ZoneTempSensor(coord, sid, zid),
        ZoneNumberSensor(coord, sid, zid, key="humidity",    name="Humedad", unit=PERCENTAGE),
        ZoneNumberSensor(coord, sid, zid, key="air_demand",  name="Demanda de aire"),
        ZoneNumberSensor(coord, sid, zid, key="heat_demand", name="Demanda de calor"),
        ZoneNumberSensor(coord, sid, zid, key="cold_demand", name="Demanda de frío"),
        ZoneNumberSensor(coord, sid, zid, key="open_window", name="Ventana abierta"),
        ZoneErrorsTextSensor(coord, sid, zid),
    ]

def _build_iaq_sensors(coord: AirzoneCoordinator) -> list[SensorEntity]:
    ents: list[SensorEntity] = []
    for (sid, iid), _ in (coord.iaqs or {}).items():
        ents.append(IAQScoreSensor(coord, sid, iid))
        ents.append(IAQCo2Sensor(coord, sid, iid))
        ents.append(IAQPM25Sensor(coord, sid, iid))
        ents.append(IAQPM10Sensor(coord, sid, iid))
        ents.append(IAQTVOCSensor(coord, sid, iid))
        ents.append(IAQPressureSensor(coord, sid, iid))
        ents.append(IAQHumiditySensor(coord, sid, iid))  # aparecerá si el firmware expone rh_*/humidity
    return ents

def _build_iaq_fallback_sensors(coord: AirzoneCoordinator) -> list[SensorEntity]:
    ents: list[SensorEntity] = []
    for sid in sorted((coord.iaq_fallback or {}).keys()):
        ents.append(IAQQualityFallbackSensor(coord, sid))
    return ents

# ---------------- base ----------------

class _BaseAZEntity(CoordinatorEntity[AirzoneCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: AirzoneCoordinator, name: str, unique: str, device: DeviceInfo) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = unique
        self._attr_device_info = device

# ---------------- webserver ----------------

def _webserver_device() -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, "webserver")},
        name="Airzone Webserver",
        manufacturer="Airzone",
        model="Webserver",
    )

class WebserverFirmwareSensor(_BaseAZEntity):
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "Firmware Webserver", f"{DOMAIN}_webserver_firmware", _webserver_device())

    @property
    def native_value(self) -> str | None:
        ws = self.coordinator.webserver or {}
        fw = ws.get("ws_firmware")
        lm = ws.get("lmachine_firmware")
        return f"{fw} / LM {lm}" if fw or lm else None

class WebserverWifiQualitySensor(_BaseAZEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:wifi"

    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "WiFi calidad", f"{DOMAIN}_webserver_wifi_quality", _webserver_device())

    @property
    def native_value(self) -> float | None:
        ws = self.coordinator.webserver or {}
        return ws.get("wifi_quality")

class WebserverRssiSensor(_BaseAZEntity):
    _attr_icon = "mdi:signal"

    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "WiFi RSSI", f"{DOMAIN}_webserver_wifi_rssi", _webserver_device())

    @property
    def native_value(self) -> float | None:
        ws = self.coordinator.webserver or {}
        return ws.get("wifi_rssi")

class WebserverWifiChannelSensor(_BaseAZEntity):
    _attr_icon = "mdi:access-point"

    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "WiFi canal", f"{DOMAIN}_webserver_wifi_channel", _webserver_device())

    @property
    def native_value(self) -> int | None:
        ws = self.coordinator.webserver or {}
        return ws.get("wifi_channel")

class WebserverInterfaceSensor(_BaseAZEntity):
    _attr_icon = "mdi:lan"

    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "Interfaz", f"{DOMAIN}_webserver_interface", _webserver_device())

    @property
    def native_value(self) -> str | None:
        ws = self.coordinator.webserver or {}
        return ws.get("interface")

class WebserverCloudSensor(_BaseAZEntity):
    _attr_icon = "mdi:cloud-check"

    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "Cloud conectado", f"{DOMAIN}_webserver_cloud", _webserver_device())

    @property
    def native_value(self) -> str | None:
        ws = self.coordinator.webserver or {}
        v = ws.get("cloud_connected")
        if v is None:
            return None
        return "Sí" if str(v).lower() in ("1", "true") else "No"

class WebserverMacSensor(_BaseAZEntity):
    _attr_icon = "mdi:identifier"

    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "MAC", f"{DOMAIN}_webserver_mac", _webserver_device())

    @property
    def native_value(self) -> str | None:
        ws = self.coordinator.webserver or {}
        return ws.get("mac")

class WebserverTypeSensor(_BaseAZEntity):
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "Tipo Webserver", f"{DOMAIN}_webserver_type", _webserver_device())

    @property
    def native_value(self) -> str | None:
        ws = self.coordinator.webserver or {}
        return ws.get("ws_type")

# ---------------- systems ----------------

class SystemNumberSensor(_BaseAZEntity):
    _attr_state_class = "measurement"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, *, key: str, name: str, unit: str | None = None) -> None:
        device = DeviceInfo(
            identifiers={(DOMAIN, f"system-{system_id}")},
            name=f"Sistema {system_id}",
            manufacturer="Airzone",
            model="HVAC System",
        )
        super().__init__(coordinator, name, f"{DOMAIN}_system_{system_id}_{key}", device)
        self._sid = int(system_id)
        self._key = key
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float | None:
        sys = self.coordinator.get_system(self._sid) or {}
        return sys.get(self._key)

class SystemErrorsTextSensor(_BaseAZEntity):
    """Errores agregados por sistema (todas sus zonas)."""
    _attr_icon = "mdi:alert-decagram"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        device = DeviceInfo(
            identifiers={(DOMAIN, f"system-{system_id}")},
            name=f"Sistema {system_id}",
            manufacturer="Airzone",
            model="HVAC System",
        )
        super().__init__(coordinator, "Errores del sistema", f"{DOMAIN}_system_{system_id}_errors_text", device)
        self._sid = int(system_id)

    @property
    def native_value(self) -> str:
        labels: list[str] = []
        for (sid, _zid), z in (self.coordinator.data or {}).items():
            if sid != self._sid:
                continue
            errs = z.get("errors") or []
            for item in errs:
                if isinstance(item, dict):
                    v = next(iter(item.values()), None)
                    if isinstance(v, str) and v.strip():
                        labels.append(v.strip())
        seen = set()
        dedup = [x for x in labels if not (x in seen or seen.add(x))]
        return ", ".join(dedup) if dedup else "Sin errores"

class SystemProfileSensor(_BaseAZEntity):
    """Perfil detectado del Sistema (diagnóstico)."""
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        device = DeviceInfo(
            identifiers={(DOMAIN, f"system-{system_id}")},
            name=f"Sistema {system_id}",
            manufacturer="Airzone",
            model="HVAC System",
        )
        super().__init__(coordinator, "Perfil detectado", f"{DOMAIN}_system_{system_id}_profile", device)
        self._sid = int(system_id)

    @property
    def native_value(self) -> str:
        prof = (self.coordinator.system_profiles or {}).get(self._sid, {})
        return prof.get("profile") or "Desconocido"

    @property
    def extra_state_attributes(self) -> dict:
        prof = (self.coordinator.system_profiles or {}).get(self._sid, {}) or {}
        return {
            "api_version": self.coordinator.version,
            "transporte_hvac": self.coordinator.transport_hvac,
            "transporte_iaq": self.coordinator.transport_iaq,
            "capabilities": prof.get("capabilities"),
            "zone_count": prof.get("zone_count"),
            "iaq_count": prof.get("iaq_count"),
        }

# ---------------- zones ----------------

class _ZoneBase(_BaseAZEntity):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int, name: str, unique: str) -> None:
        device = DeviceInfo(
            identifiers={(DOMAIN, f"{system_id}-{zone_id}")},
            name=(coordinator.get_zone(system_id, zone_id) or {}).get("name") or f"Zone {system_id}/{zone_id}",
            manufacturer="Airzone",
            model="Local API zone",
        )
        super().__init__(coordinator, name, unique, device)
        self._sid = int(system_id)
        self._zid = int(zone_id)

    def _zone(self) -> dict:
        return self.coordinator.get_zone(self._sid, self._zid) or {}

class ZoneNumberSensor(_ZoneBase):
    _attr_state_class = "measurement"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int, *, key: str, name: str, unit: str | None = None) -> None:
        super().__init__(coordinator, system_id, zone_id, name, f"{DOMAIN}_zone_{system_id}_{zone_id}_{key}")
        self._key = key
        self._attr_native_unit_of_measurement = unit

    @property
    def native_value(self) -> float | int | None:
        return self._zone().get(self._key)

class ZoneTempSensor(_ZoneBase):
    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int) -> None:
        super().__init__(coordinator, system_id, zone_id, "Temperatura", f"{DOMAIN}_zone_{system_id}_{zone_id}_roomtemp")

    @property
    def native_value(self) -> float | None:
        return self._zone().get("roomTemp")

class ZoneErrorsTextSensor(_ZoneBase):
    _attr_icon = "mdi:alert-circle-outline"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int) -> None:
        super().__init__(coordinator, system_id, zone_id, "Errores de zona", f"{DOMAIN}_zone_{system_id}_{zone_id}_errors_text")

    @property
    def native_value(self) -> str:
        errs = (self._zone().get("errors") or [])
        labels: list[str] = []
        for item in errs:
            if isinstance(item, dict):
                v = next(iter(item.values()), None)
                if isinstance(v, str) and v.strip():
                    labels.append(v.strip())
        return ", ".join(labels) if labels else "Sin errores"

class ZoneProfileSensor(_ZoneBase):
    """Perfil de la zona (diagnóstico)."""
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int) -> None:
        super().__init__(coordinator, system_id, zone_id, "Perfil de zona", f"{DOMAIN}_zone_{system_id}_{zone_id}_profile")

    @property
    def native_value(self) -> str:
        prof = (self.coordinator.zone_profiles or {}).get((self._sid, self._zid), {})
        return prof.get("profile") or "Desconocido"

    @property
    def extra_state_attributes(self) -> dict:
        prof = (self.coordinator.zone_profiles or {}).get((self._sid, self._zid), {}) or {}
        return {
            "capabilities": prof.get("capabilities"),
        }

# ---------------- IAQ (real) ----------------

class _IAQBase(_BaseAZEntity):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int, name: str, unique: str) -> None:
        device = DeviceInfo(
            identifiers={(DOMAIN, f"iaq-{system_id}-{iaq_id}")},
            name=(coordinator.get_iaq(system_id, iaq_id) or {}).get("name") or f"IAQ {system_id}/{iaq_id}",
            manufacturer="Airzone",
            model="IAQ sensor",
        )
        super().__init__(coordinator, name, unique, device)
        self._sid = int(system_id)
        self._iid = int(iaq_id)

    def _iaq(self) -> dict:
        return self.coordinator.get_iaq(self._sid, self._iid) or {}

class IAQScoreSensor(_IAQBase):
    _attr_state_class = "measurement"
    _attr_icon = "mdi:gauge"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int) -> None:
        super().__init__(coordinator, system_id, iaq_id, "IAQ score", f"{DOMAIN}_iaq_{system_id}_{iaq_id}_score")

    @property
    def native_value(self) -> float | None:
        return self._iaq().get("iaq_score")

class IAQCo2Sensor(_IAQBase):
    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_icon = "mdi:molecule-co2"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int) -> None:
        super().__init__(coordinator, system_id, iaq_id, "CO₂", f"{DOMAIN}_iaq_{system_id}_{iaq_id}_co2")

    @property
    def native_value(self) -> float | None:
        v = self._iaq().get("co2_value")
        return v if v is not None else self._iaq().get("co2")

class IAQPM25Sensor(_IAQBase):
    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    _attr_icon = "mdi:weather-hazy"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int) -> None:
        super().__init__(coordinator, system_id, iaq_id, "PM2.5", f"{DOMAIN}_iaq_{system_id}_{iaq_id}_pm25")

    @property
    def native_value(self) -> float | None:
        v = self._iaq().get("pm2_5_value")
        return v if v is not None else self._iaq().get("pm2_5")

class IAQPM10Sensor(_IAQBase):
    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    _attr_icon = "mdi:weather-hazy"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int) -> None:
        super().__init__(coordinator, system_id, iaq_id, "PM10", f"{DOMAIN}_iaq_{system_id}_{iaq_id}_pm10")

    @property
    def native_value(self) -> float | None:
        v = self._iaq().get("pm10_value")
        return v if v is not None else self._iaq().get("pm10")

class IAQTVOCSensor(_IAQBase):
    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_BILLION
    _attr_icon = "mdi:chemical-weapon"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int) -> None:
        super().__init__(coordinator, system_id, iaq_id, "TVOC", f"{DOMAIN}_iaq_{system_id}_{iaq_id}_tvoc")

    @property
    def native_value(self) -> float | None:
        v = self._iaq().get("tvoc_value")
        return v if v is not None else self._iaq().get("tvoc")

class IAQPressureSensor(_IAQBase):
    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = UnitOfPressure.HPA
    _attr_icon = "mdi:gauge-low"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int) -> None:
        super().__init__(coordinator, system_id, iaq_id, "Presión", f"{DOMAIN}_iaq_{system_id}_{iaq_id}_pressure")

    @property
    def native_value(self) -> float | None:
        v = self._iaq().get("pressure_value")
        return v if v is not None else self._iaq().get("pressure")

class IAQHumiditySensor(_IAQBase):
    """Humedad relativa reportada por el IAQ si el firmware la expone."""
    _attr_state_class = "measurement"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_icon = "mdi:water-percent"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int) -> None:
        super().__init__(coordinator, system_id, iaq_id, "Humedad", f"{DOMAIN}_iaq_{system_id}_{iaq_id}_humidity")

    @property
    def native_value(self) -> float | None:
        d = self._iaq()
        for k in ("rh_value", "rh", "humidity"):
            v = d.get(k)
            if v is not None:
                return v
        return None

# ---------------- IAQ fallback (si /iaq no existe) ----------------

class IAQQualityFallbackSensor(CoordinatorEntity[AirzoneCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:air-filter"
    _attr_name = "Calidad IAQ"
    _attr_unique_id = None

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._attr_unique_id = f"{DOMAIN}_iaq_fallback_{self._sid}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"system-{self._sid}")},
            name=f"Sistema {self._sid}",
            manufacturer="Airzone",
            model="HVAC System",
        )

    @property
    def native_value(self) -> str | int | None:
        d = (self.coordinator.iaq_fallback or {}).get(self._sid) or {}
        val = d.get("aq_quality")
        mapping = {0: "Buena", 1: "Regular", 2: "Mala"}
        if isinstance(val, int) and val in mapping:
            return mapping[val]
        return val
