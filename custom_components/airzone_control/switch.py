"""Switches del sistema: On/Off por zona maestra y ECO (solo si existe)."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _sys_data(coordinator) -> dict:
    d = coordinator.data or {}
    sys_list = d.get("hvac_system", {}).get("data")
    if isinstance(sys_list, list) and sys_list:
        return sys_list[0]
    return {}


def _master_zone(coordinator) -> dict:
    d = coordinator.data or {}
    return d.get("master_zone", {}) or {}


def _eco_supported(coordinator) -> bool:
    s = _sys_data(coordinator)
    mz = _master_zone(coordinator)
    # Algunos firmwares lo reportan en sistema; otros en la zona
    return any(k in s for k in ("eco", "eco_adapt")) or any(k in mz for k in ("eco", "eco_adapt"))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    entities: list[SwitchEntity] = [AirzoneSystemOnOffSwitch(coordinator)]
    if _eco_supported(coordinator):
        entities.append(AirzoneEcoModeSwitch(coordinator))
    async_add_entities(entities)


class _Base(CoordinatorEntity, SwitchEntity):
    _attr_should_poll = False

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @property
    def device_info(self) -> dict[str, Any]:
        sd = _sys_data(self.coordinator)
        model = sd.get("model") or "Airzone System"
        return {
            "identifiers": {(DOMAIN, "system")},
            "manufacturer": "Airzone",
            "name": f"Airzone System {model}",
            "model": model,
        }


class AirzoneSystemOnOffSwitch(_Base):
    """Encender/Apagar actuando sobre 'on' de la zona maestra (fallback a mode)."""
    _attr_name = "Airzone System On/Off"
    _attr_unique_id = "airzone_system_onoff"
    _attr_icon = "mdi:power"

    @property
    def is_on(self) -> bool:
        mz = _master_zone(self.coordinator)
        try:
            return bool(int(mz.get("on", 0)))
        except Exception:
            return False

    async def async_turn_on(self, **kwargs) -> None:
        sd = _sys_data(self.coordinator)
        mz = _master_zone(self.coordinator)
        payload = {"systemID": int(sd.get("systemID", 1)), "zoneID": int(mz.get("zoneID", 1)), "on": 1}
        status, data = await self.coordinator._api_put("hvac", payload)
        if status != 200:
            _LOGGER.debug("ON 'on:1' falló (%s %s). Fallback con 'mode'.", status, data)
            # fallback: forzar un modo encendido (Heat si existe)
            modes = mz.get("modes") if isinstance(mz.get("modes"), list) else []
            mode = 2 if 2 in modes else (modes[0] if modes else 2)
            payload = {"systemID": int(sd.get("systemID", 1)), "zoneID": int(mz.get("zoneID", 1)), "mode": mode}
            status, data = await self.coordinator._api_put("hvac", payload)
            if status != 200:
                _LOGGER.error("Fallback ON con mode falló: %s %s", status, data)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        sd = _sys_data(self.coordinator)
        mz = _master_zone(self.coordinator)
        payload = {"systemID": int(sd.get("systemID", 1)), "zoneID": int(mz.get("zoneID", 1)), "on": 0}
        status, data = await self.coordinator._api_put("hvac", payload)
        if status != 200:
            _LOGGER.debug("OFF 'on:0' falló (%s %s). Fallback con 'mode:0'.", status, data)
            payload = {"systemID": int(sd.get("systemID", 1)), "zoneID": int(mz.get("zoneID", 1)), "mode": 0}
            status, data = await self.coordinator._api_put("hvac", payload)
            if status != 200:
                _LOGGER.error("Fallback OFF con mode=0 falló: %s %s", status, data)
        await self.coordinator.async_request_refresh()


class AirzoneEcoModeSwitch(_Base):
    """ECO: solo si el firmware lo reporta; usa 'eco' en sistema o 'eco_adapt' en la master."""
    _attr_name = "Airzone ECO Mode"
    _attr_unique_id = "airzone_system_eco"
    _attr_icon = "mdi:leaf"

    @property
    def available(self) -> bool:
        return super().available and _eco_supported(self.coordinator)

    @property
    def is_on(self) -> bool:
        sd = _sys_data(self.coordinator)
        mz = _master_zone(self.coordinator)
        if "eco" in sd:
            try:
                return bool(int(sd.get("eco", 0)))
            except Exception:
                return False
        if "eco_adapt" in mz:
            return str(mz.get("eco_adapt")).lower() != "manual"
        return False

    async def async_turn_on(self, **kwargs) -> None:
        sd = _sys_data(self.coordinator)
        mz = _master_zone(self.coordinator)
        if "eco" in sd:
            status, data = await self.coordinator._api_put("hvac", {"systemID": int(sd.get("systemID", 1)), "eco": 1})
        else:
            status, data = await self.coordinator._api_put(
                "hvac", {"systemID": int(sd.get("systemID", 1)), "zoneID": int(mz.get("zoneID", 1)), "eco_adapt": "auto"}
            )
        if status != 200:
            _LOGGER.error("Error activando ECO: %s %s", status, data)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        sd = _sys_data(self.coordinator)
        mz = _master_zone(self.coordinator)
        if "eco" in sd:
            status, data = await self.coordinator._api_put("hvac", {"systemID": int(sd.get("systemID", 1)), "eco": 0})
        else:
            status, data = await self.coordinator._api_put(
                "hvac", {"systemID": int(sd.get("systemID", 1)), "zoneID": int(mz.get("zoneID", 1)), "eco_adapt": "manual"}
            )
        if status != 200:
            _LOGGER.error("Error desactivando ECO: %s %s", status, data)
        await self.coordinator.async_request_refresh()
