from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirzoneCoordinator
from . import i18n

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Crea sensores por sistema, por zona, IAQ y Webserver (con nombres traducibles)."""
    data = hass.data.get(DOMAIN, {})
    coord: AirzoneCoordinator | None = None
    if isinstance(data, dict):
        bundle = data.get(entry.entry_id)
        if isinstance(bundle, dict):
            coord = bundle.get("coordinator")
    if not isinstance(coord, AirzoneCoordinator):
        if isinstance(data, AirzoneCoordinator):
            coord = data
    if not isinstance(coord, AirzoneCoordinator):
        _LOGGER.warning("AirzoneCoordinator not found; aborting sensor setup.")
        return

    # Guardamos el entry en el coordinator si no lo trae (para Options)
    if not hasattr(coord, "config_entry"):
        try:
            coord.config_entry = entry  # type: ignore[attr-defined]
        except Exception:
            pass

    entities: List[SensorEntity] = []

    # ---- Sensores por sistema ----
    system_ids = sorted({sid for (sid, _zid) in (coord.data or {}).keys()})
    for sid in system_ids:
        entities.extend(_build_system_sensors(coord, sid))

    # ---- Sensores por zona ----
    for (sid, zid), _ in (coord.data or {}).items():
        entities.extend(_build_zone_sensors(coord, sid, zid))

    # ---- Sensores del Webserver ----
    entities.extend(_build_webserver_sensors(coord))

    # ---- Sensores IAQ ----
    if isinstance(getattr(coord, "iaqs", None), dict):
        for (sid, iid), _ in coord.iaqs.items():
            entities.extend(_build_iaq_sensors(coord, sid, iid))

    async_add_entities(entities)


# ===================================================================
# Bases con translation_key (nombres traducibles por usuario/servidor)
# ===================================================================

class _BaseSystemSensor(CoordinatorEntity[AirzoneCoordinator], SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True  # el nombre viene de translations/*.json

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, tkey: str, uid_suffix: str) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._attr_translation_key = tkey
        self._attr_unique_id = f"{DOMAIN}_system_{self._sid}_{uid_suffix}"

    @property
    def available(self) -> bool:
        return any(1 for (sid, _z) in (self.coordinator.data or {}).keys() if sid == self._sid)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"system-{self._sid}")},
            name=f"Sistema {self._sid}",
            manufacturer="Airzone",
            model="HVAC System",
        )


class _BaseZoneSensor(CoordinatorEntity[AirzoneCoordinator], SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int, tkey: str, uid_suffix: str) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._zid = int(zone_id)
        self._attr_translation_key = tkey
        self._attr_unique_id = f"{DOMAIN}_zone_{self._sid}_{self._zid}_{uid_suffix}"

    def _zone(self) -> dict:
        return self.coordinator.get_zone(self._sid, self._zid) or {}

    @property
    def available(self) -> bool:
        return bool(self._zone())

    @property
    def device_info(self) -> DeviceInfo:
        z = self._zone()
        name = z.get("name") or f"Zona {self._sid}/{self._zid}"
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._sid}-{self._zid}")},
            name=name,
            manufacturer="Airzone",
            model="Local API zone",
        )


class _BaseIAQSensor(CoordinatorEntity[AirzoneCoordinator], SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int, tkey: str, uid_suffix: str) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._iid = int(iaq_id)
        self._attr_translation_key = tkey
        self._attr_unique_id = f"{DOMAIN}_iaq_{self._sid}_{self._iid}_{uid_suffix}"

    def _iaq(self) -> dict:
        return self.coordinator.get_iaq(self._sid, self._iid) or {}

    @property
    def available(self) -> bool:
        return bool(self._iaq())

    @property
    def device_info(self) -> DeviceInfo:
        iaq = self._iaq()
        return DeviceInfo(
            identifiers={(DOMAIN, f"iaq-{self._sid}-{self._iid}")},
            name=iaq.get("name") or f"IAQ {self._sid}/{self._iid}",
            manufacturer="Airzone",
            model="IAQ Sensor",
        )


# ===================================================================
# Sensores de SISTEMA
# ===================================================================

def _system_dict(coord: AirzoneCoordinator, sid: int) -> dict:
    """Obtiene el dict de sistema de forma compatible con varias estructuras."""
    d = {}
    systems = getattr(coord, "systems", None)
    if isinstance(systems, dict):
        d = systems.get(sid) or {}
        if d:
            return d
    get_system = getattr(coord, "get_system", None)
    if callable(get_system):
        try:
            d = get_system(sid) or {}
            if d:
                return d
        except Exception:
            pass
    system_info = getattr(coord, "system_info", None)
    if callable(system_info):
        try:
            d = system_info(sid) or {}
            if d:
                return d
        except Exception:
            pass
    return d or {}


def _build_system_sensors(coord: AirzoneCoordinator, sid: int) -> List[SensorEntity]:
    """Crea solo los sensores de sistema con dato real en tu firmware."""
    sysd = _system_dict(coord, sid)
    entities: List[SensorEntity] = []

    # Perfil (propio de tu integración)
    entities.append(SystemProfileSensor(coord, sid))

    # Conectado MC
    if "mc_connected" in sysd:
        entities.append(SystemMCConnectedSensor(coord, sid))

    # Firmware / tipo / tecnología / fabricante / num IAQ (solo si existen)
    if "system_firmware" in sysd:
        entities.append(SystemFirmwareSensor(coord, sid))
    if "system_type" in sysd:
        entities.append(SystemTypeSensor(coord, sid))
    if "system_technology" in sysd:
        entities.append(SystemTechnologySensor(coord, sid))
    if "manufacturer" in sysd:
        entities.append(SystemManufacturerSensor(coord, sid))
    if "num_airqsensors" in sysd:
        entities.append(SystemNumIAQSensor(coord, sid))

    # Temperaturas (vienen por zona)
    entities.extend([
        SystemOutdoorTempSensor(coord, sid),
        SystemReturnTempSensor(coord, sid),
        SystemWorkTempSensor(coord, sid),
    ])

    # Placeholder de riesgo de condensación
    entities.append(SystemCondRiskMasterSensor(coord, sid))

    return entities


class SystemProfileSensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "system_profile", "sys_profile")

    @property
    def native_value(self) -> Optional[str]:
        prof = self.coordinator.system_profiles.get(self._sid) or {}
        return prof.get("profile")


class SystemMCConnectedSensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "mc_connected", "mc_connected")

    @property
    def native_value(self) -> Optional[str]:
        d = _system_dict(self.coordinator, self._sid)
        v = d.get("mc_connected")
        if v is None:
            return None
        try:
            return i18n.label(self.coordinator.hass, "yes") if int(v) else i18n.label(self.coordinator.hass, "no")
        except Exception:
            return str(v)


class SystemFirmwareSensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "system_firmware", "system_firmware")

    @property
    def native_value(self) -> Optional[str]:
        d = _system_dict(self.coordinator, self._sid)
        return d.get("system_firmware")


class SystemTypeSensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "system_type", "system_type")

    @property
    def native_value(self) -> Optional[int]:
        d = _system_dict(self.coordinator, self._sid)
        v = d.get("system_type")
        try:
            return int(v)
        except Exception:
            return None


class SystemTechnologySensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "system_technology", "system_technology")

    @property
    def native_value(self) -> Optional[int]:
        d = _system_dict(self.coordinator, self._sid)
        v = d.get("system_technology")
        try:
            return int(v)
        except Exception:
            return None


class SystemManufacturerSensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "manufacturer", "manufacturer")

    @property
    def native_value(self) -> Optional[str]:
        d = _system_dict(self.coordinator, self._sid)
        return d.get("manufacturer")


class SystemNumIAQSensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "num_airqsensors", "num_airqsensors")

    @property
    def native_value(self) -> Optional[int]:
        d = _system_dict(self.coordinator, self._sid)
        v = d.get("num_airqsensors")
        try:
            return int(v)
        except Exception:
            return None


# ===================================================================
# Temperatura exterior con override por entidad de HA
# ===================================================================

class SystemOutdoorTempSensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "outdoor_temp", "outdoor_temp")
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = "temperature"
        self._ha_entity_listener_remove = None

    # -------------------- utilidades internas --------------------

    def _options(self) -> dict:
        entry = getattr(self.coordinator, "config_entry", None) or getattr(self.coordinator, "entry", None)
        return dict(getattr(entry, "options", {}) or {})

    def _override_entity_id(self) -> str | None:
        opts = self._options()
        ext_map = opts.get("external_temp_map") or {}
        return ext_map.get(str(self._sid)) or ext_map.get(self._sid)

    def _ha_temperature_c(self) -> float | None:
        """Lee el estado del sensor de HA elegido y lo devuelve en °C."""
        entity_id = self._override_entity_id()
        if not entity_id:
            return None

        st = self.hass.states.get(entity_id)
        if not st or st.state in ("unknown", "unavailable", ""):
            return None

        # Valor numérico
        try:
            value = float(st.state)
        except Exception:
            return None

        # Unidad (si viene en ºF/K convertimos)
        unit = (st.attributes.get("unit_of_measurement") or "").strip()
        if unit in ("°F", "F", "ºF"):
            return (value - 32.0) * 5.0 / 9.0
        if unit == "K":
            return value - 273.15

        # Asumimos °C u otra unidad métrica equivalente
        return value

    def _airzone_temperature_c(self) -> float | None:
        """Fallback a la API de Airzone."""
        for z in self.coordinator.zones_of_system(self._sid):
            v = z.get("ext_temp") or z.get("temp_outdoor") or z.get("outdoorTemp")
            if v is not None:
                try:
                    return float(v)
                except Exception:
                    continue
        return None

    # -------------------- ciclo de vida / listeners --------------------

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        entity_id = self._override_entity_id()
        if entity_id:
            @callback
            def _ext_sensor_changed(event):
                self.async_write_ha_state()

            self._ha_entity_listener_remove = async_track_state_change_event(
                self.hass, [entity_id], _ext_sensor_changed
            )

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        if self._ha_entity_listener_remove:
            self._ha_entity_listener_remove()
            self._ha_entity_listener_remove = None

    # -------------------- valor y atributos --------------------

    @property
    def native_value(self) -> Optional[float]:
        ha_temp = self._ha_temperature_c()
        if ha_temp is not None:
            return round(ha_temp, 1)

        az_temp = self._airzone_temperature_c()
        if az_temp is not None:
            return round(az_temp, 1)

        return None

    @property
    def extra_state_attributes(self) -> dict | None:
        src = "ha" if self._ha_temperature_c() is not None else ("airzone" if self._airzone_temperature_c() is not None else None)
        attrs = {"source": src}
        eid = self._override_entity_id()
        if eid:
            attrs["override_entity"] = eid
        return attrs


class SystemReturnTempSensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "return_temp", "return_temp")
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = "temperature"

    @property
    def native_value(self) -> Optional[float]:
        for z in self.coordinator.zones_of_system(self._sid):
            v = z.get("temp_return") or z.get("return_temp") or z.get("returnTemp")
            if v is not None:
                try:
                    return float(v)
                except Exception:
                    continue
        return None


class SystemWorkTempSensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "work_temp", "work_temp")
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = "temperature"

    @property
    def native_value(self) -> Optional[float]:
        for z in self.coordinator.zones_of_system(self._sid):
            v = z.get("work_temp") or z.get("workTemp")
            if v is not None:
                try:
                    return float(v)
                except Exception:
                    continue
        return None


class SystemCondRiskMasterSensor(_BaseSystemSensor):
    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id, "cond_risk_master", "cond_risk_master")

    @property
    def native_value(self) -> Optional[str]:
        # No hay una clave oficial clara a nivel sistema; lo dejamos como placeholder
        return None


# ===================================================================
# Sensores de ZONA (solo se crean si hay dato real)
# ===================================================================

def _build_zone_sensors(coord: AirzoneCoordinator, sid: int, zid: int) -> List[SensorEntity]:
    """Crea entidades de zona únicamente para claves presentes."""
    z = coord.get_zone(sid, zid) or {}
    entities: List[SensorEntity] = []

    def has(*keys: str) -> bool:
        for k in keys:
            v = z.get(k)
            if v is None:
                continue
            if isinstance(v, str) and v.strip().lower() in ("", "nan", "none"):
                continue
            # 0 es un valor válido para muchas claves (demands, on/off, etc.)
            return True
        return False

    # Demandas
    if has("air_demand"):
        entities.append(ZoneAirDemandSensor(coord, sid, zid))
    if has("heat_demand"):
        entities.append(ZoneHeatDemandSensor(coord, sid, zid))
    if has("cold_demand"):
        entities.append(ZoneColdDemandSensor(coord, sid, zid))
    if has("floor_demand"):
        entities.append(ZoneFloorDemandSensor(coord, sid, zid))

    # Errores (solo si lista no vacía)
    if isinstance(z.get("errors"), list) and z.get("errors"):
        entities.append(ZoneErrorsSensor(coord, sid, zid))

    # Humedad / Temperatura ambiente
    if has("humidity"):
        entities.append(ZoneHumiditySensor(coord, sid, zid))
    if has("roomTemp", "room_temp"):
        entities.append(ZoneTemperatureSensor(coord, sid, zid))

    # Ventana abierta (sea propia o externa)
    if has("open_window", "window_external_source"):
        entities.append(ZoneOpenWindowSensor(coord, sid, zid))

    # Eco adapt (texto off/on)
    if has("eco_adapt"):
        entities.append(ZoneEcoAdaptSensor(coord, sid, zid))

    # Unidades (0=°C, 1=°F)
    if has("units"):
        entities.append(ZoneUnitsSensor(coord, sid, zid))

    # Perfil (derivado): solo si el coordinador detecta alguno
    try:
        prof = (coord._determine_zone_profile(z) or {}).get("profile")
    except Exception:
        prof = None
    if prof:
        entities.append(ZoneProfileSensor(coord, sid, zid))

    return entities


class ZoneAirDemandSensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "air_demand", "air_demand")

    @property
    def native_value(self) -> Optional[int]:
        v = self._zone().get("air_demand")
        try:
            return int(v)
        except Exception:
            return None


class ZoneHeatDemandSensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "heat_demand", "heat_demand")

    @property
    def native_value(self) -> Optional[int]:
        v = self._zone().get("heat_demand")
        try:
            return int(v)
        except Exception:
            return None


class ZoneColdDemandSensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "cold_demand", "cold_demand")

    @property
    def native_value(self) -> Optional[int]:
        v = self._zone().get("cold_demand")
        try:
            return int(v)
        except Exception:
            return None


class ZoneFloorDemandSensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "floor_demand", "floor_demand")

    @property
    def native_value(self) -> Optional[int]:
        v = self._zone().get("floor_demand")
        try:
            return int(v)
        except Exception:
            return None


class ZoneErrorsSensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "errors", "errors")

    @property
    def native_value(self) -> Optional[str]:
        errs = self._zone().get("errors")
        if isinstance(errs, list):
            return ", ".join(str(e) for e in errs) if errs else None
        return None


class ZoneHumiditySensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "humidity", "humidity")
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = "humidity"

    @property
    def native_value(self) -> Optional[float]:
        v = self._zone().get("humidity")
        try:
            return float(v)
        except Exception:
            return None


class ZoneTemperatureSensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "temperature", "temperature")
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = "temperature"

    @property
    def native_value(self) -> Optional[float]:
        v = self._zone().get("roomTemp") or self._zone().get("room_temp")
        try:
            return float(v)
        except Exception:
            return None


class ZoneOpenWindowSensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "open_window", "open_window")

    @property
    def native_value(self) -> Optional[int]:
        z = self._zone()
        v = z.get("open_window", z.get("window_external_source"))
        try:
            return int(v)
        except Exception:
            return None


class ZoneEcoAdaptSensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "eco_adapt", "eco_adapt")

    @property
    def native_value(self) -> Optional[str]:
        v = self._zone().get("eco_adapt")
        return str(v) if v is not None else None


class ZoneUnitsSensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "units", "units")

    @property
    def native_value(self) -> Optional[str]:
        v = self._zone().get("units")
        if v is None:
            return None
        try:
            u = int(v)
            return "°C" if u == 0 else "°F"
        except Exception:
            return None


class ZoneProfileSensor(_BaseZoneSensor):
    def __init__(self, coordinator, sid, zid) -> None:
        super().__init__(coordinator, sid, zid, "zone_profile", "zone_profile")

    @property
    def native_value(self) -> Optional[str]:
        z = self._zone()
        return (self.coordinator._determine_zone_profile(z) or {}).get("profile")


# ===================================================================
# Sensores del WEBSERVER
# ===================================================================

def _build_webserver_sensors(coord: AirzoneCoordinator) -> List[SensorEntity]:
    """Crea sensores del Webserver solo si hay dato real."""
    ws = getattr(coord, "webserver", {}) or {}
    ents: List[SensorEntity] = []

    def has(*keys: str) -> bool:
        for k in keys:
            v = ws.get(k)
            if v is None:
                continue
            if isinstance(v, str) and v.strip().lower() in ("", "nan", "none"):
                continue
            return True
        return False

    # Transporte (siempre)
    ents.append(WSTransportSensor(coord))

    if has("cloud_connected", "cloud", "ws_cloud", "az_cloud"):
        ents.append(WSCloudConnectedSensor(coord))
    if has("api_ver", "version", "ws_firmware"):
        ents.append(WSVersionSensor(coord))
    if has("mac"):
        ents.append(WSMacSensor(coord))
    if has("wifi_channel"):
        ents.append(WSWifiChannelSensor(coord))
    if has("wifi_quality"):
        ents.append(WSWifiQualitySensor(coord))
        ents.append(WSWifiQualityTextSensor(coord))
    if has("wifi_rssi"):
        ents.append(WSWifiRSSISensor(coord))
    if has("interface"):
        ents.append(WSInterfaceSensor(coord))
    if has("ws_type"):
        ents.append(WSTypeSensor(coord))
    if has("lmachine_firmware"):
        ents.append(WSLMachineFirmwareSensor(coord))

    return ents


class _BaseWSSensor(CoordinatorEntity[AirzoneCoordinator], SensorEntity):
    """Base para sensores del Webserver (ws.az)."""
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: AirzoneCoordinator, tkey: str, uid_suffix: str) -> None:
        super().__init__(coordinator)
        self._attr_translation_key = tkey
        self._attr_unique_id = f"{DOMAIN}_ws_{uid_suffix}"

    def _ws(self) -> dict:
        return getattr(self.coordinator, "webserver", {}) or {}

    @property
    def available(self) -> bool:
        return bool(self._ws())

    @property
    def device_info(self) -> DeviceInfo:
        ws = self._ws()
        return DeviceInfo(
            identifiers={(DOMAIN, "webserver")},
            name="Webserver",
            manufacturer="Airzone",
            model=ws.get("ws_type") or "ws_az",
            sw_version=ws.get("ws_firmware") or ws.get("version"),
        )


class WSCloudConnectedSensor(_BaseWSSensor):
    """Conectado a la nube Airzone Cloud (sí/no)."""
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "cloud_connected", "cloud_connected")

    @property
    def native_value(self) -> Optional[str]:
        d = self._ws()
        val = d.get("cloud_connected") or d.get("cloud") or d.get("ws_cloud") or d.get("az_cloud")
        if val is None:
            return None
        try:
            return i18n.label(self.coordinator.hass, "yes") if int(val) else i18n.label(self.coordinator.hass, "no")
        except Exception:
            return str(val)


class WSVersionSensor(_BaseWSSensor):
    """Versión del Webserver / firmware / API."""
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "ws_version", "ws_version")

    @property
    def native_value(self) -> Optional[str]:
        d = self._ws()
        return d.get("ws_firmware") or d.get("api_ver") or d.get("version") or getattr(self.coordinator, "version", None)


class WSTransportSensor(_BaseWSSensor):
    """Transporte (http/https) detectado por la integración."""
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "transport", "transport")

    @property
    def native_value(self) -> Optional[str]:
        val = getattr(self.coordinator, "transport_scheme", None)
        if val:
            return str(val)
        d = self._ws()
        return d.get("transport") or None


class WSMacSensor(_BaseWSSensor):
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "ws_mac", "ws_mac")

    @property
    def native_value(self) -> Optional[str]:
        return self._ws().get("mac")


class WSWifiChannelSensor(_BaseWSSensor):
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "ws_wifi_channel", "ws_wifi_channel")

    @property
    def native_value(self) -> Optional[int]:
        v = self._ws().get("wifi_channel")
        try:
            return int(v)
        except Exception:
            return None


class WSWifiQualitySensor(_BaseWSSensor):
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "ws_wifi_quality", "ws_wifi_quality")

    @property
    def native_value(self) -> Optional[int]:
        v = self._ws().get("wifi_quality")
        try:
            return int(v)
        except Exception:
            return None


class WSWifiQualityTextSensor(_BaseWSSensor):
    """Calidad Wi-Fi como texto: Muy mala, Baja, Media, Buena, Excelente."""
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "ws_wifi_quality_text", "ws_wifi_quality_text")

    @property
    def native_value(self) -> Optional[str]:
        v = self._ws().get("wifi_quality")
        if v is None:
            return None
        try:
            q = int(v)
        except Exception:
            return None
        mapping = {0: "very_bad", 1: "bad", 2: "medium", 3: "good", 4: "excellent"}
        return i18n.label(self.coordinator.hass, mapping.get(q, "unknown"))


class WSWifiRSSISensor(_BaseWSSensor):
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "ws_wifi_rssi", "ws_wifi_rssi")
        self._attr_device_class = "signal_strength"
        self._attr_native_unit_of_measurement = "dBm"

    @property
    def native_value(self) -> Optional[int]:
        v = self._ws().get("wifi_rssi")
        try:
            return int(v)
        except Exception:
            return None


class WSInterfaceSensor(_BaseWSSensor):
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "ws_interface", "ws_interface")

    @property
    def native_value(self) -> Optional[str]:
        return self._ws().get("interface")


class WSTypeSensor(_BaseWSSensor):
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "ws_type", "ws_type")

    @property
    def native_value(self) -> Optional[str]:
        return self._ws().get("ws_type")


class WSLMachineFirmwareSensor(_BaseWSSensor):
    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator, "ws_lmachine_firmware", "ws_lmachine_firmware")

    @property
    def native_value(self) -> Optional[str]:
        return self._ws().get("lmachine_firmware")


# ===================================================================
# Sensores IAQ  (solo se crean los que tienen dato real)
# ===================================================================

def _build_iaq_sensors(coord: AirzoneCoordinator, sid: int, iid: int) -> List[SensorEntity]:
    """Crea entidades IAQ únicamente para las claves presentes con valor."""
    data = coord.get_iaq(sid, iid) or {}
    entities: List[SensorEntity] = []

    def has(key: str) -> bool:
        v = data.get(key)
        if v is None:
            return False
        if isinstance(v, str) and v.strip().lower() in ("", "nan", "none"):
            return False
        return True

    if has("iaq_index"):
        entities.append(IAQIndexSensor(coord, sid, iid))
    if has("iaq_index_text") or has("iaq_text"):
        entities.append(IAQIndexTextSensor(coord, sid, iid))
    if has("iaq_score"):
        entities.append(IAQScoreSensor(coord, sid, iid))

    if has("aqi_pm_category") or has("aqi_pm_cat"):
        entities.append(IAQPMCategorySensor(coord, sid, iid))
    if has("aqi_pm_partial"):
        entities.append(IAQPMPartialSensor(coord, sid, iid))
    if has("air_quality_text") or has("iaq_quality_text"):
        entities.append(IAQAirQualityTextSensor(coord, sid, iid))

    if has("co2_value"):
        entities.append(IAQCO2Sensor(coord, sid, iid))
    if has("tvoc_value"):
        entities.append(IAQTVOCSensor(coord, sid, iid))
    if has("pm2_5_value") or has("pm25_value"):
        entities.append(IAQPM25Sensor(coord, sid, iid))
    if has("pm10_value"):
        entities.append(IAQPM10Sensor(coord, sid, iid))
    if has("pressure_value"):
        entities.append(IAQPressureSensor(coord, sid, iid))

    if has("abs_humidity_gm3") or has("humidity_abs_gm3"):
        entities.append(IAQAbsHumiditySensor(coord, sid, iid))
    if has("humidex_master"):
        entities.append(IAQHumidexMasterSensor(coord, sid, iid))
    if has("humidex_master_pct"):
        entities.append(IAQHumidexMasterPctSensor(coord, sid, iid))
    if has("iaq_home") or has("iaq_domestic"):
        entities.append(IAQHomeIndexSensor(coord, sid, iid))
    if has("iaq_home_text") or has("iaq_domestic_text"):
        entities.append(IAQHomeIndexTextSensor(coord, sid, iid))
    if has("needs_ventilation") or has("need_ventilation"):
        entities.append(IAQNeedsVentSensor(coord, sid, iid))

    return entities


class IAQIndexSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "iaq_index", "iaq_index")

    @property
    def native_value(self) -> Optional[int]:
        v = self._iaq().get("iaq_index")
        try:
            return int(v)
        except Exception:
            return None


class IAQIndexTextSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "iaq_index_text", "iaq_index_text")

    @property
    def native_value(self) -> Optional[str]:
        return self._iaq().get("iaq_index_text") or self._iaq().get("iaq_text")


class IAQScoreSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "iaq_score", "iaq_score")

    @property
    def native_value(self) -> Optional[int]:
        v = self._iaq().get("iaq_score")
        try:
            return int(v)
        except Exception:
            return None


class IAQPMCategorySensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "aqi_pm_category", "aqi_pm_cat")

    @property
    def native_value(self) -> Optional[str]:
        return self._iaq().get("aqi_pm_category") or self._iaq().get("aqi_pm_cat")


class IAQPMPartialSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "aqi_pm_partial", "aqi_pm_partial")

    @property
    def native_value(self) -> Optional[float]:
        v = self._iaq().get("aqi_pm_partial")
        try:
            return float(v)
        except Exception:
            return None


class IAQAirQualityTextSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "air_quality_text", "air_quality_text")

    @property
    def native_value(self) -> Optional[str]:
        return self._iaq().get("air_quality_text") or self._iaq().get("iaq_quality_text")


class IAQCO2Sensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "co2", "co2")
        self._attr_native_unit_of_measurement = "ppm"

    @property
    def native_value(self) -> Optional[int]:
        v = self._iaq().get("co2_value")
        try:
            return int(v)
        except Exception:
            return None


class IAQTVOCSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "tvoc", "tvoc")
        self._attr_native_unit_of_measurement = "ppb"

    @property
    def native_value(self) -> Optional[int]:
        v = self._iaq().get("tvoc_value")
        try:
            return int(v)
        except Exception:
            return None


class IAQPM25Sensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "pm25", "pm25")
        self._attr_native_unit_of_measurement = "µg/m³"

    @property
    def native_value(self) -> Optional[float]:
        v = self._iaq().get("pm2_5_value") or self._iaq().get("pm25_value")
        try:
            return float(v)
        except Exception:
            return None


class IAQPM10Sensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "pm10", "pm10")
        self._attr_native_unit_of_measurement = "µg/m³"

    @property
    def native_value(self) -> Optional[float]:
        v = self._iaq().get("pm10_value")
        try:
            return float(v)
        except Exception:
            return None


class IAQPressureSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "pressure", "pressure")
        self._attr_native_unit_of_measurement = "hPa"

    @property
    def native_value(self) -> Optional[float]:
        v = self._iaq().get("pressure_value")
        try:
            return float(v)
        except Exception:
            return None


class IAQAbsHumiditySensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "abs_humidity_gm3", "abs_humidity_gm3")
        self._attr_native_unit_of_measurement = "g/m³"

    @property
    def native_value(self) -> Optional[float]:
        v = self._iaq().get("abs_humidity_gm3") or self._iaq().get("humidity_abs_gm3")
        try:
            return float(v)
        except Exception:
            return None


class IAQHumidexMasterSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "humidex_master", "humidex_master")

    @property
    def native_value(self) -> Optional[float]:
        v = self._iaq().get("humidex_master")
        try:
            return float(v)
        except Exception:
            return None


class IAQHumidexMasterPctSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "humidex_master_pct", "humidex_master_pct")
        self._attr_native_unit_of_measurement = "%"

    @property
    def native_value(self) -> Optional[float]:
        v = self._iaq().get("humidex_master_pct")
        try:
            return float(v)
        except Exception:
            return None


class IAQHomeIndexSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "iaq_home", "iaq_home")

    @property
    def native_value(self) -> Optional[int]:
        v = self._iaq().get("iaq_home") or self._iaq().get("iaq_domestic")
        try:
            return int(v)
        except Exception:
            return None


class IAQHomeIndexTextSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "iaq_home_text", "iaq_home_text")

    @property
    def native_value(self) -> Optional[str]:
        return self._iaq().get("iaq_home_text") or self._iaq().get("iaq_domestic_text")


class IAQNeedsVentSensor(_BaseIAQSensor):
    def __init__(self, coordinator, sid, iid) -> None:
        super().__init__(coordinator, sid, iid, "needs_ventilation", "needs_ventilation")

    @property
    def native_value(self) -> Optional[str]:
        v = self._iaq().get("needs_ventilation") or self._iaq().get("need_ventilation")
        if v is None:
            return None
        try:
            return i18n.label(self.coordinator.hass, "yes") if int(v) else i18n.label(self.coordinator.hass, "no")
        except Exception:
            return None
