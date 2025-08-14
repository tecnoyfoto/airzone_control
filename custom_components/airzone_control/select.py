from __future__ import annotations

from typing import List
import asyncio
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import AirzoneCoordinator
from .api_modes import allowed_hvac_modes_for_zone, HVAC_TO_API_MODE, translate_current_mode
from homeassistant.components.climate.const import HVACMode

_LOGGER = logging.getLogger(__name__)

DISPLAY = {
    HVACMode.OFF: "Apagado",
    HVACMode.HEAT: "Calor",
    HVACMode.COOL: "Frío",
    HVACMode.FAN_ONLY: "Solo ventilador",
    HVACMode.AUTO: "Auto",
    HVACMode.DRY: "Seco",
}
REVERSE = {v: k for k, v in DISPLAY.items()}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities):
    data = hass.data.get(DOMAIN, {})
    coord: AirzoneCoordinator | None = None
    if isinstance(data, dict):
        coord = data.get(entry.entry_id, {}).get("coordinator")
    if not isinstance(coord, AirzoneCoordinator):
        return

    entities: list[SelectEntity] = []
    if not coord.data:
        await coord.async_request_refresh()

    # Select por zona
    for (sid, zid), _ in (coord.data or {}).items():
        entities.append(ZoneModeSelect(coord, sid, zid))

    # Select global por sistema
    for sid in sorted({sid for (sid, _) in (coord.data or {}).keys()}):
        entities.append(SystemGlobalModeSelect(coord, sid))

    add_entities(entities)

# -------------------- Zona --------------------

class ZoneModeSelect(CoordinatorEntity[AirzoneCoordinator], SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._zid = int(zone_id)
        z = coordinator.get_zone(self._sid, self._zid) or {}
        name = (z.get("name") or f"Zone {self._sid}/{self._zid}") + " - Modo"
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_select_mode_{self._sid}_{self._zid}"

    @property
    def device_info(self) -> DeviceInfo:
        z = self.coordinator.get_zone(self._sid, self._zid) or {}
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._sid}-{self._zid}")},
            name=z.get("name") or f"Zone {self._sid}/{self._zid}",
            manufacturer="Airzone",
            model="Local API zone",
        )

    def _allowed(self) -> list[HVACMode]:
        z = self.coordinator.get_zone(self._sid, self._zid) or {}
        return allowed_hvac_modes_for_zone(z)

    @property
    def options(self) -> list[str]:
        return [DISPLAY[m] for m in self._allowed() if m in DISPLAY]

    @property
    def current_option(self) -> str | None:
        z = self.coordinator.get_zone(self._sid, self._zid) or {}
        hvac = translate_current_mode(z, self._allowed())
        return DISPLAY.get(hvac)

    async def async_select_option(self, option: str) -> None:
        hvac = REVERSE.get(option)
        if hvac is None:
            return
        if hvac == HVACMode.OFF:
            await self.coordinator.async_set_zone_params(self._sid, self._zid, on=0)
            return
        code = HVAC_TO_API_MODE.get(hvac)
        body = {"on": 1}
        if code is not None:
            body["mode"] = code
        await self.coordinator.async_set_zone_params(self._sid, self._zid, **body)

# -------------------- Global (Sistema) --------------------

class SystemGlobalModeSelect(CoordinatorEntity[AirzoneCoordinator], SelectEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._attr_name = f"Sistema {self._sid} - Modo global"
        self._attr_unique_id = f"{DOMAIN}_select_mode_global_{self._sid}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"system-{self._sid}")},
            name=f"Sistema {self._sid}",
            manufacturer="Airzone",
            model="HVAC System",
        )

    def _zones_of_sid(self) -> list[dict]:
        data = self.coordinator.data or {}
        return [z for (sid, _), z in data.items() if sid == self._sid]

    def _allowed(self) -> list[HVACMode]:
        # Unión de modos permitidos de las zonas del sistema
        allowed: set[HVACMode] = set()
        for z in self._zones_of_sid():
            for m in allowed_hvac_modes_for_zone(z):
                allowed.add(m)
        # Ordenar según DISPLAY
        ordered = [m for m in DISPLAY.keys() if m in allowed]
        return ordered

    @property
    def options(self) -> list[str]:
        return [DISPLAY[m] for m in self._allowed() if m in DISPLAY]

    @property
    def current_option(self) -> str | None:
        # Si todas las zonas comparten el mismo modo, muéstralo; si no, None
        zones = self._zones_of_sid()
        if not zones:
            return None
        from .api_modes import translate_current_mode
        modes = []
        for z in zones:
            modes.append(translate_current_mode(z, allowed_hvac_modes_for_zone(z)))
        first = modes[0]
        if all(m == first for m in modes):
            return DISPLAY.get(first)
        return None

    async def async_select_option(self, option: str) -> None:
        hvac = REVERSE.get(option)
        if hvac is None:
            return
        tasks = []
        if hvac == HVACMode.OFF:
            for (_sid, zid), _ in (self.coordinator.data or {}).items():
                if _sid == self._sid:
                    tasks.append(self.coordinator.async_set_zone_params(self._sid, zid, on=0))
        else:
            code = HVAC_TO_API_MODE.get(hvac)
            body = {"on": 1}
            if code is not None:
                body["mode"] = code
            for (_sid, zid), _ in (self.coordinator.data or {}).items():
                if _sid == self._sid:
                    tasks.append(self.coordinator.async_set_zone_params(self._sid, zid, **body))
        if tasks:
            await asyncio.gather(*tasks)
