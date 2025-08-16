"""Switches por sistema:
- Encendido/Apagado (actúa sobre la zona máster)
- ECO (si existe en sistema/zona)
- Modo Hotel (Seguir global)
"""
from __future__ import annotations

from typing import Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirzoneCoordinator


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
