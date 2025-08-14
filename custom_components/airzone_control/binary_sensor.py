"""Plataforma de binary_sensors para Airzone Control.

Incluye:
- Por zona: Battery Low, Window Open
- Webserver: Cloud Connected
- System: MC Connected
"""
from __future__ import annotations

from typing import Any, Dict, Optional, List

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


# ----------------- helpers -----------------
def _coerce_bool(val: Any) -> Optional[bool]:
    """Convierte '1'/'0', 1/0, True/False, 'true'/'false' en bool."""
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


def _zones_from(coordinator) -> List[Dict[str, Any]]:
    return (coordinator.data or {}).get("hvac_zone", {}).get("data", []) or []


def _system_from(coordinator) -> Dict[str, Any]:
    sys_data = (coordinator.data or {}).get("hvac_system", {})
    if isinstance(sys_data, dict) and isinstance(sys_data.get("data"), list) and sys_data["data"]:
        return sys_data["data"][0]
    return sys_data if isinstance(sys_data, dict) else {}


def _webserver_from(coordinator) -> Dict[str, Any]:
    return (coordinator.data or {}).get("webserver", {}) or {}


# ----------------- setup -----------------
async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[BinarySensorEntity] = []

    # Por zona
    for z in _zones_from(coordinator):
        # Battery Low (si el firmware expone 'battery')
        if "battery" in z:
            entities.append(AirzoneZoneBatteryLowBinarySensor(coordinator, z))
        # Window Open (si el firmware expone 'open_window')
        if "open_window" in z:
            entities.append(AirzoneZoneWindowBinarySensor(coordinator, z))

    # Webserver: Cloud connected
    entities.append(AirzoneWebserverCloudConnectedBinarySensor(coordinator))

    # System: MC connected (conexión controladora-máquina)
    entities.append(AirzoneSystemMCConnectedBinarySensor(coordinator))

    async_add_entities(entities, True)


# ----------------- base zona -----------------
class _ZoneBaseBinary(CoordinatorEntity, BinarySensorEntity):
    """Base para binary_sensors de una zona Airzone."""

    _attr_should_poll = False

    def __init__(self, coordinator, zone_data: Dict[str, Any]) -> None:
        super().__init__(coordinator)
        self.zone_data = zone_data
        self.system_id = zone_data.get("systemID", 1)
        self.zone_id = zone_data.get("zoneID", 0)
        self.zone_name = zone_data.get("name", f"Zone {self.zone_id}")

    def _refresh_zone_data(self) -> None:
        for z in _zones_from(self.coordinator):
            if z.get("systemID") == self.system_id and z.get("zoneID") == self.zone_id:
                self.zone_data = z
                return

    def _handle_coordinator_update(self) -> None:
        self._refresh_zone_data()
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def device_info(self):
        # Igual que en sensor.py para agrupar en el mismo dispositivo de la zona
        return {
            "identifiers": {(DOMAIN, f"zone_{self.system_id}_{self.zone_id}")},
            "name": f"Airzone Zone {self.zone_name}",
            "manufacturer": "Airzone",
            "model": "Local API Thermostat",
        }


class AirzoneZoneBatteryLowBinarySensor(_ZoneBaseBinary):
    """Indica True si la batería de la zona está baja."""
    _attr_device_class = BinarySensorDeviceClass.BATTERY

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_name = f"{self.zone_name} Battery Low"
        self._attr_unique_id = f"airzone_battlow_{self.system_id}_{self.zone_id}"

    @property
    def is_on(self) -> bool:
        # En algunos firmwares es 0..100; en otros puede ser la cadena "Low"
        battery_val = self.zone_data.get("battery")
        if battery_val is None:
            return False
        try:
            return int(battery_val) < 20
        except (ValueError, TypeError):
            return str(battery_val).strip().lower() == "low"


class AirzoneZoneWindowBinarySensor(_ZoneBaseBinary):
    """Indica True si la ventana de la zona está abierta."""
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, coordinator, zone_data):
        super().__init__(coordinator, zone_data)
        self._attr_name = f"{self.zone_name} Window Open"
        self._attr_unique_id = f"airzone_window_{self.system_id}_{self.zone_id}"

    @property
    def is_on(self) -> bool:
        return self.zone_data.get("open_window") == 1


# ----------------- webserver & system -----------------
class AirzoneWebserverCloudConnectedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Conectividad del Webserver con la nube de Airzone."""
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Airzone Cloud Connected"
    _attr_unique_id = "airzone_cloud_connected"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)

    @property
    def is_on(self) -> Optional[bool]:
        return _coerce_bool(_webserver_from(self.coordinator).get("cloud_connected"))

    @property
    def extra_state_attributes(self):
        ws = _webserver_from(self.coordinator)
        return {"raw": ws.get("cloud_connected")}

    @property
    def device_info(self):
        ws = _webserver_from(self.coordinator)
        info = {
            "identifiers": {(DOMAIN, "webserver")},
            "name": "Airzone Webserver",
            "manufacturer": "Airzone",
            "model": ws.get("ws_type", "Webserver"),
        }
        mac = ws.get("mac")
        if isinstance(mac, str) and mac:
            info["connections"] = {("mac", mac)}
        return info


class AirzoneSystemMCConnectedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Conectividad MC (controladora ↔ máquina)."""
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_name = "Airzone MC Connected"
    _attr_unique_id = "airzone_mc_connected"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)

    @property
    def is_on(self) -> Optional[bool]:
        return _coerce_bool(_system_from(self.coordinator).get("mc_connected"))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "system")},
            "name": "Airzone System",
            "manufacturer": "Airzone",
            "model": "Central Controller",
        }
