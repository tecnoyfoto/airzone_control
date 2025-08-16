"""Binary sensors Airzone: por zona (batería/ventana), webserver cloud y MC por sistema."""
from __future__ import annotations

from typing import Any, Optional, List

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import AirzoneCoordinator


def _coerce_bool(val: Any) -> Optional[bool]:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
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

    # Por zona
    for (sid, zid), z in (coord.data or {}).items():
        if "battery" in z:
            entities.append(ZoneBatteryLowBinary(coord, sid, zid))
        if "open_window" in z:
            entities.append(ZoneWindowOpenBinary(coord, sid, zid))

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


class ZoneBatteryLowBinary(_ZoneBase):
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator: AirzoneCoordinator, sid: int, zid: int) -> None:
        z = coordinator.get_zone(sid, zid) or {}
        super().__init__(coordinator, sid, zid, name=f"{z.get('name') or f'Zone {sid}/{zid}'} Battery Low",
                         unique=f"{DOMAIN}_zone_{sid}_{zid}_battlow")

    @property
    def is_on(self) -> bool:
        battery_val = self._zone().get("battery")
        if battery_val is None:
            return False
        try:
            return int(battery_val) < 20
        except (ValueError, TypeError):
            return str(battery_val).strip().lower() == "low"


class ZoneWindowOpenBinary(_ZoneBase):
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, coordinator: AirzoneCoordinator, sid: int, zid: int) -> None:
        z = coordinator.get_zone(sid, zid) or {}
        super().__init__(coordinator, sid, zid, name=f"{z.get('name') or f'Zone {sid}/{zid}'} Window Open",
                         unique=f"{DOMAIN}_zone_{sid}_{zid}_window")

    @property
    def is_on(self) -> bool:
        return _coerce_bool(self._zone().get("open_window")) is True


class WebserverCloudConnectedBinary(CoordinatorEntity[AirzoneCoordinator], BinarySensorEntity):
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Airzone Cloud Connected"
    _attr_unique_id = f"{DOMAIN}_webserver_cloud"

    def __init__(self, coordinator: AirzoneCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def is_on(self) -> Optional[bool]:
        ws = self.coordinator.webserver or {}
        return _coerce_bool(ws.get("cloud_connected"))

    @property
    def extra_state_attributes(self):
        ws = self.coordinator.webserver or {}
        return {"raw": ws.get("cloud_connected")}

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
        self._attr_name = f"Sistema {self._sid} - MC Connected"
        self._attr_unique_id = f"{DOMAIN}_mc_connected_{self._sid}"

    @property
    def is_on(self) -> Optional[bool]:
        sys = self.coordinator.get_system(self._sid) or {}
        return _coerce_bool(sys.get("mc_connected"))

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"system-{self._sid}")},
            name=f"Sistema {self._sid}",
            manufacturer="Airzone",
            model="HVAC System",
        )
