"""Switches por sistema:
- Encendido/Apagado (actúa sobre la zona máster)
- ECO (si existe en sistema/zona)
- Modo Hotel (Seguir global)
"""
from __future__ import annotations

from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirzoneCoordinator

ACS_ZONE_MARKER_KEYS = (
    "acs_temp",
    "acs_setpoint",
    "acs_power",
    "tankTemp",
    "tank_temp",
    "tankSetpoint",
    "tank_setpoint",
    "tank_power",
    "acs_powerful",
    "acs_powerful_mode",
    "tank_powerful",
    "tank_powerful_mode",
    "powerful_mode",
)
ACS_POWER_KEYS = ("acs_power", "tank_power", "dhw_power")
ACS_POWERFUL_KEYS = (
    "acs_powerful",
    "acs_powerful_mode",
    "tank_powerful",
    "tank_powerful_mode",
    "dhw_powerful",
    "powerful_mode",
)


def _as_bool(val: Any) -> bool | None:
    try:
        if isinstance(val, bool):
            return val
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


def _acs_zone(coord: AirzoneCoordinator, sid: int) -> dict | None:
    for zone in coord.zones_of_system(sid):
        if any(key in zone for key in ACS_ZONE_MARKER_KEYS):
            return zone
    return None


def _acs_field_target(coord: AirzoneCoordinator, sid: int, keys: tuple[str, ...]) -> tuple[int, str] | None:
    system = coord.get_system(sid) or {}
    for key in keys:
        if key in system:
            return (0, key)

    zone = _acs_zone(coord, sid) or {}
    for key in keys:
        if key in zone:
            try:
                return (int(zone.get("zoneID")), key)
            except Exception:
                return None

    return None


def _acs_field_value(coord: AirzoneCoordinator, sid: int, keys: tuple[str, ...]) -> Any:
    system = coord.get_system(sid) or {}
    for key in keys:
        if key in system:
            return system.get(key)

    zone = _acs_zone(coord, sid) or {}
    for key in keys:
        if key in zone:
            return zone.get(key)

    return None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    data = hass.data.get(DOMAIN, {})
    coord: AirzoneCoordinator | None = None
    if isinstance(data, dict):
        coord = data.get(entry.entry_id, {}).get("coordinator")
    if not isinstance(coord, AirzoneCoordinator):
        return

    entities: list[SwitchEntity] = []
    for sid in sorted({sid for (sid, _) in (coord.data or {}).keys()}):
        entities.append(SystemOnOffSwitch(coord, sid))
        # ECO si lo soporta
        sys = coord.get_system(sid) or {}
        zones = coord.zones_of_system(sid)
        eco_supported = ("eco" in sys) or any("eco_adapt" in z for z in zones)
        if eco_supported:
            entities.append(SystemEcoModeSwitch(coord, sid))
        if _acs_field_target(coord, sid, ACS_POWER_KEYS):
            entities.append(SystemACSPowerSwitch(coord, sid))
        if _acs_field_target(coord, sid, ACS_POWERFUL_KEYS):
            entities.append(SystemACSPowerfulSwitch(coord, sid))
        # NUEVO: Modo Hotel (Seguir global)
        entities.append(SystemFollowMasterSwitch(coord, sid))

    async_add_entities(entities)


class _SystemBase(CoordinatorEntity[AirzoneCoordinator], SwitchEntity):
    _attr_should_poll = False

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"system-{self._sid}")},
            name=f"Sistema {self._sid}",
            manufacturer="Airzone",
            model="HVAC System",
        )


class SystemOnOffSwitch(_SystemBase):
    """Encender/Apagar actuando sobre 'on' de la zona máster."""
    _attr_icon = "mdi:power"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id)
        self._attr_name = f"Sistema {self._sid} - Encendido"
        self._attr_unique_id = f"{DOMAIN}_system_onoff_{self._sid}"

    @property
    def is_on(self) -> bool:
        zid = self.coordinator.master_zone_id(self._sid)
        if zid is None:
            return False
        z = self.coordinator.get_zone(self._sid, zid) or {}
        try:
            return bool(int(z.get("on", 0)))
        except Exception:
            return False

    async def async_turn_on(self, **kwargs) -> None:
        zid = self.coordinator.master_zone_id(self._sid)
        if zid is None:
            return
        await self.coordinator.async_set_zone_params(self._sid, zid, on=1)

    async def async_turn_off(self, **kwargs) -> None:
        zid = self.coordinator.master_zone_id(self._sid)
        if zid is None:
            return
        await self.coordinator.async_set_zone_params(self._sid, zid, on=0)


class SystemEcoModeSwitch(_SystemBase):
    """ECO: usa 'eco' en sistema si existe; si no, 'eco_adapt' en la zona máster."""
    _attr_icon = "mdi:leaf"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id)
        self._attr_name = f"Sistema {self._sid} - ECO"
        self._attr_unique_id = f"{DOMAIN}_system_eco_{self._sid}"

    @property
    def is_on(self) -> bool:
        sys = self.coordinator.get_system(self._sid) or {}
        if "eco" in sys:
            try:
                return bool(int(sys.get("eco", 0)))
            except Exception:
                return False
        zid = self.coordinator.master_zone_id(self._sid)
        if zid is None:
            return False
        z = self.coordinator.get_zone(self._sid, zid) or {}
        if "eco_adapt" in z:
            return str(z.get("eco_adapt")).lower() != "manual"
        return False

    async def async_turn_on(self, **kwargs) -> None:
        sys = self.coordinator.get_system(self._sid) or {}
        if "eco" in sys:
            await self.coordinator.async_set_zone_params(self._sid, 0, **{"eco": 1})
            return
        zid = self.coordinator.master_zone_id(self._sid)
        if zid is not None:
            await self.coordinator.async_set_zone_params(self._sid, zid, eco_adapt="auto")

    async def async_turn_off(self, **kwargs) -> None:
        sys = self.coordinator.get_system(self._sid) or {}
        if "eco" in sys:
            await self.coordinator.async_set_zone_params(self._sid, 0, **{"eco": 0})
            return
        zid = self.coordinator.master_zone_id(self._sid)
        if zid is not None:
            await self.coordinator.async_set_zone_params(self._sid, zid, eco_adapt="manual")


class SystemACSPowerSwitch(_SystemBase):
    """Encendido del ACS cuando la API expone un campo dedicado."""
    _attr_icon = "mdi:water-boiler"
    _attr_has_entity_name = True
    _attr_translation_key = "acs_power"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id)
        self._attr_name = None
        self._attr_unique_id = f"{DOMAIN}_system_acs_power_{self._sid}"

    @property
    def available(self) -> bool:
        return super().available and _acs_field_target(self.coordinator, self._sid, ACS_POWER_KEYS) is not None

    @property
    def is_on(self) -> bool:
        value = _acs_field_value(self.coordinator, self._sid, ACS_POWER_KEYS)
        state = _as_bool(value)
        return bool(state) if state is not None else False

    async def async_turn_on(self, **kwargs) -> None:
        target = _acs_field_target(self.coordinator, self._sid, ACS_POWER_KEYS)
        if target is None:
            return
        zone_id, field = target
        await self.coordinator.async_set_zone_params(self._sid, zone_id, **{field: 1})

    async def async_turn_off(self, **kwargs) -> None:
        target = _acs_field_target(self.coordinator, self._sid, ACS_POWER_KEYS)
        if target is None:
            return
        zone_id, field = target
        await self.coordinator.async_set_zone_params(self._sid, zone_id, **{field: 0})


class SystemACSPowerfulSwitch(_SystemBase):
    """Modo potente del ACS cuando la API expone un campo dedicado."""
    _attr_icon = "mdi:water-boiler-alert"
    _attr_has_entity_name = True
    _attr_translation_key = "acs_powerful"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id)
        self._attr_name = None
        self._attr_unique_id = f"{DOMAIN}_system_acs_powerful_{self._sid}"

    @property
    def available(self) -> bool:
        return super().available and _acs_field_target(self.coordinator, self._sid, ACS_POWERFUL_KEYS) is not None

    @property
    def is_on(self) -> bool:
        value = _acs_field_value(self.coordinator, self._sid, ACS_POWERFUL_KEYS)
        state = _as_bool(value)
        return bool(state) if state is not None else False

    async def async_turn_on(self, **kwargs) -> None:
        target = _acs_field_target(self.coordinator, self._sid, ACS_POWERFUL_KEYS)
        if target is None:
            return
        zone_id, field = target
        await self.coordinator.async_set_zone_params(self._sid, zone_id, **{field: 1})

    async def async_turn_off(self, **kwargs) -> None:
        target = _acs_field_target(self.coordinator, self._sid, ACS_POWERFUL_KEYS)
        if target is None:
            return
        zone_id, field = target
        await self.coordinator.async_set_zone_params(self._sid, zone_id, **{field: 0})


class SystemFollowMasterSwitch(_SystemBase):
    """Modo hotel: todas las zonas siguen on/mode de la zona máster."""
    _attr_icon = "mdi:vector-link"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id)
        self._attr_name = f"Sistema {self._sid} - Modo Hotel (Seguir global)"
        self._attr_unique_id = f"{DOMAIN}_system_follow_master_{self._sid}"

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_follow_master_enabled(self._sid)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_follow_master(self._sid, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_follow_master(self._sid, False)
