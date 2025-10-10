"""Binary sensors Airzone: por zona (batería/ventana), webserver cloud, MC por sistema y binarios IAQ extra."""
from __future__ import annotations

from typing import Any, Optional, List
import math

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
    # noqa
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import AirzoneCoordinator

# --- utils ---
def _as_bool(val: Any) -> Optional[bool]:
    try:
        if isinstance(val, (int, float)):
            return bool(int(val))
        s = str(val).strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off"):
            return False
    except Exception:
        pass
    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data.get(DOMAIN, {})
    coord: AirzoneCoordinator | None = None
    if isinstance(data, dict):
        coord = data.get(entry.entry_id, {}).get("coordinator")
    if not isinstance(coord, AirzoneCoordinator):
        return

    entities: list[BinarySensorEntity] = []

    # Webserver cloud
    entities.append(WebserverCloudConnectedBinary(coord))

    # MC connected por sistema (si lo reporta)
    for sid in sorted({sid for (sid, _) in (coord.data or {}).keys()}):
        entities.append(SystemMCConnectedBinary(coord, sid))

    # Necesidad de ventilación por IAQ
    for (sid, iid), _ in (coord.iaqs or {}).items():
        entities.append(IAQVentilationNeededBinary(coord, sid, iid))

    # Riesgo de condensación tomando zona máster
    for sid in sorted({sid for (sid, _) in (coord.data or {}).keys()}):
        entities.append(CondensationRiskBinary(coord, sid))

    async_add_entities(entities, True)


class _ZoneBase(CoordinatorEntity[AirzoneCoordinator], BinarySensorEntity):
    _attr_should_poll = False

    def __init__(self, coordinator: AirzoneCoordinator, sid: int, zid: int, *, name: str, unique: str) -> None:
        super().__init__(coordinator)
        self._sid = int(sid)
        self._zid = int(zid)
        self._attr_name = name
        self._attr_unique_id = unique

    def _zone(self) -> dict:
        return self.coordinator.get_zone(self._sid, self._zid) or {}

    @property
    def available(self) -> bool:
        return bool(self._zone())

    @property
    def device_info(self) -> DeviceInfo:
        z = self._zone()
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._sid}-{self._zid}")},
            name=z.get("name") or f"Zone {self._sid}/{self._zid}",
            manufacturer="Airzone",
            model="Local API zone",
        )

class ZoneBatteryBinary(_ZoneBase):
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator: AirzoneCoordinator, sid: int, zid: int) -> None:
        super().__init__(coordinator, sid, zid, name="Batería baja", unique=f"{DOMAIN}_zone_{sid}_{zid}_battery_low")

    @property
    def is_on(self) -> bool | None:
        v = self._zone().get("battery_low")
        return _as_bool(v)

class ZoneWindowBinary(_ZoneBase):
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, coordinator: AirzoneCoordinator, sid: int, zid: int) -> None:
        super().__init__(coordinator, sid, zid, name="Ventana abierta", unique=f"{DOMAIN}_zone_{sid}_{zid}_open_window")

    @property
    def is_on(self) -> bool | None:
        v = self._zone().get("open_window")
        return _as_bool(v)

# --- webserver ---

class WebserverCloudConnectedBinary(CoordinatorEntity[AirzoneCoordinator], BinarySensorEntity):
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Cloud conectado"
        self._attr_unique_id = f"{DOMAIN}_webserver_cloud_connected"

    @property
    def is_on(self) -> bool | None:
        ws = self.coordinator.webserver or {}
        v = ws.get("cloud")
        return _as_bool(v)

    @property
    def device_info(self) -> DeviceInfo:
        ws = self.coordinator.webserver or {}
        info = DeviceInfo(
            identifiers={(DOMAIN, "webserver")},
            name="Airzone Webserver",
            manufacturer="Airzone",
            model=ws.get("ws_type", "Webserver"),
        )
        return info


class SystemMCConnectedBinary(CoordinatorEntity[AirzoneCoordinator], BinarySensorEntity):
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._attr_name = "MC conectado"
        self._attr_unique_id = f"{DOMAIN}_system_{self._sid}_mc_connected"

    @property
    def is_on(self) -> bool | None:
        s = (self.coordinator.systems or {}).get(self._sid) or {}
        v = s.get("mc_connected")
        return _as_bool(v)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"system-{self._sid}")},
            name=f"Sistema {self._sid}",
            manufacturer="Airzone",
            model="HVAC System",
        )

# --- nuevos binarios ---

class IAQVentilationNeededBinary(CoordinatorEntity[AirzoneCoordinator], BinarySensorEntity):
    _attr_should_poll = False
    _attr_icon = "mdi:fan-alert"
    _attr_name = None

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._iid = int(iaq_id)
        self._attr_name = "Necesita ventilación"
        self._attr_unique_id = f"{DOMAIN}_iaq_{self._sid}_{self._iid}_vent_needed"

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
            model="IAQ sensor",
        )

    @property
    def is_on(self) -> bool | None:
        d = self._iaq()
        co2 = d.get("co2_value") if d.get("co2_value") is not None else d.get("co2")
        if co2 is None:
            return None
        return bool(co2 >= 1200)


class CondensationRiskBinary(CoordinatorEntity[AirzoneCoordinator], BinarySensorEntity):
    _attr_should_poll = False
    _attr_icon = "mdi:water-percent-alert"
    _attr_name = None

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._attr_name = "Riesgo de condensación (máster)"
        self._attr_unique_id = f"{DOMAIN}_system_{self._sid}_condensation_risk"

    def _z(self) -> dict:
        mzid = self.coordinator.master_zone_id(self._sid)
        return self.coordinator.get_zone(self._sid, mzid) or {}

    @property
    def available(self) -> bool:
        z = self._z()
        return "roomTemp" in z and "humidity" in z

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"system-{self._sid}")},
            name=f"Sistema {self._sid}",
            manufacturer="Airzone",
            model="HVAC System",
        )

    @property
    def is_on(self) -> bool | None:
        z = self._z()
        t = z.get("roomTemp"); rh = z.get("humidity")
        if not isinstance(t, (int,float)) or not isinstance(rh, (int,float)):
            return None
        # Riesgo si punto de rocío está a <=2.0°C de la temp ambiente
        a = 17.62; b = 243.12
        gamma = (a*float(t))/(b+float(t)) + math.log(max(1e-6, float(rh)/100.0))
        dp = (b*gamma)/(a-gamma)
        return bool(dp >= float(t) - 2.0)
