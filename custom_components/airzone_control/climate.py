from __future__ import annotations

import logging
from typing import Any, List, Optional

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import AirzoneCoordinator
from .api_modes import allowed_hvac_modes_for_zone, translate_current_mode, HVAC_TO_API_MODE, has_heat_capability, has_cool_capability

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities):
    # Coordinator lookup (2 common storage patterns)
    data = hass.data.get(DOMAIN, {})
    coord: AirzoneCoordinator | None = None
    if isinstance(data, dict):
        coord = data.get(entry.entry_id) or data.get("coordinator") or data.get("COORDINATOR")
        if isinstance(coord, dict):
            coord = coord.get("coordinator")
    if not isinstance(coord, AirzoneCoordinator):
        _LOGGER.warning("AirzoneCoordinator not found in hass.data; creating a default one may fail.")
        return

    entities: list[AirzoneZoneClimate] = []
    if not coord.data:
        await coord.async_request_refresh()
    for (system_id, zone_id), z in (coord.data or {}).items():
        name = z.get("name") or f"Zone {system_id}/{zone_id}"
        entities.append(AirzoneZoneClimate(coord, system_id, zone_id, name))
    add_entities(entities)

class AirzoneZoneClimate(CoordinatorEntity[AirzoneCoordinator], ClimateEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int, name: str) -> None:
        super().__init__(coordinator)
        self._system_id = int(system_id)
        self._zone_id = int(zone_id)
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_climate_{self._system_id}_{self._zone_id}"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._system_id}-{self._zone_id}")},
            name=self.name,
            manufacturer="Airzone",
            model="Local API zone",
        )

    # ---------- Helpers ----------
    def _zone(self) -> dict:
        z = self.coordinator.get_zone(self._system_id, self._zone_id) or {}
        return z

    # ---------- Properties ----------
    @property
    def available(self) -> bool:
        return bool(self._zone())

    @property
    def current_temperature(self) -> float | None:
        z = self._zone()
        return z.get("roomTemp")

    @property
    def target_temperature(self) -> float | None:
        z = self._zone()
        return z.get("setpoint") or z.get("heatsetpoint") or z.get("coolsetpoint")

    @property
    def min_temp(self) -> float:
        z = self._zone()
        return z.get("minTemp") or z.get("heatmintemp") or z.get("coolmintemp") or 7.0

    @property
    def max_temp(self) -> float:
        z = self._zone()
        return z.get("maxTemp") or z.get("heatmaxtemp") or z.get("coolmaxtemp") or 30.0

    @property
    def target_temperature_step(self) -> float | None:
        z = self._zone()
        step = z.get("temp_step")
        try:
            if step:
                return float(step)
        except Exception:
            pass
        # many Airzone firmwares use 0.5
        return 0.5

    @property
    def hvac_modes(self) -> list[HVACMode]:
        z = self._zone()
        return allowed_hvac_modes_for_zone(z)

    @property
    def hvac_mode(self) -> HVACMode:
        z = self._zone()
        allowed = self.hvac_modes
        return translate_current_mode(z, allowed)

    @property
    def hvac_action(self) -> HVACAction | None:
        z = self._zone()
        try:
            if int(z.get("on", 1)) == 0:
                return HVACAction.OFF
        except Exception:
            pass

        mode = self.hvac_mode
        if mode == HVACMode.HEAT:
            return HVACAction.HEATING if (z.get("heat_demand") or 0) > 0 else HVACAction.IDLE
        if mode == HVACMode.COOL:
            return HVACAction.COOLING if (z.get("cold_demand") or 0) > 0 else HVACAction.IDLE
        if mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        if mode == HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    # ---------- Commands ----------
    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self.coordinator.async_set_zone_params(self._system_id, self._zone_id, setpoint=float(temp), on=1)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_zone_params(self._system_id, self._zone_id, on=0)
            return
        code = HVAC_TO_API_MODE.get(hvac_mode)
        body: dict[str, Any] = {"on": 1}
        if code is not None:
            body["mode"] = code
        await self.coordinator.async_set_zone_params(self._system_id, self._zone_id, **body)

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set_zone_params(self._system_id, self._zone_id, on=1)

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_zone_params(self._system_id, self._zone_id, on=0)
