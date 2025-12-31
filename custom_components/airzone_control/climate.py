from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

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

from .const import DOMAIN, CONF_GROUPS
from .coordinator import AirzoneCoordinator
from .api_modes import (
    allowed_hvac_modes_for_zone,
    translate_current_mode,
    HVAC_TO_API_MODE,
)

_LOGGER = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    """Convierte un nombre libre en un identificador simple."""
    v = (value or "").strip().lower()
    v = re.sub(r"\s+", "_", v)
    v = re.sub(r"[^a-z0-9_]+", "", v)
    return v or "group"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add_entities):
    """Configura termostatos de zona + termostato maestro + termostatos de grupo."""
    data = hass.data.get(DOMAIN, {})
    coordinator: AirzoneCoordinator | None = None

    # Formato actual: hass.data[DOMAIN][entry_id] = {"coordinator": AirzoneCoordinator}
    if isinstance(data, dict):
        bundle = data.get(entry.entry_id)
        if isinstance(bundle, dict):
            coordinator = bundle.get("coordinator")

    # Formato legacy (por si acaso)
    if not isinstance(coordinator, AirzoneCoordinator):
        if isinstance(data, AirzoneCoordinator):
            coordinator = data

    if not isinstance(coordinator, AirzoneCoordinator):
        _LOGGER.warning("AirzoneCoordinator not found; aborting climate setup.")
        return

    entities: List[ClimateEntity] = []

    # --- Termostatos de ZONA (uno por cada zona descubierta) ---
    system_zone_ids: Dict[int, List[int]] = {}
    for (sid, zid), z in (coordinator.data or {}).items():
        try:
            system_id = int(sid)
            zone_id = int(zid)
        except Exception:
            continue

        # Ignoramos registros no-zona
        if zone_id <= 0:
            continue

        system_zone_ids.setdefault(system_id, []).append(zone_id)
        name = str(z.get("name") or f"Zone {zone_id}")
        entities.append(AirzoneZoneClimate(coordinator, system_id, zone_id, name))

    # --- Termostatos MAESTRO (uno por sistema) ---
    for system_id, zone_ids in sorted(system_zone_ids.items()):
        zid_list = sorted(set(zone_ids))
        if zid_list:
            entities.append(AirzoneMasterClimate(coordinator, system_id, zid_list))

    # --- Termostatos de GRUPO (desde options) ---
    groups = entry.options.get(CONF_GROUPS, []) or []
    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or _slugify(str(g.get("name") or "group")))
        name = str(g.get("name") or gid)
        zones = g.get("zones") or []
        members: List[Tuple[int, int]] = []
        for z in zones:
            try:
                sid_s, zid_s = str(z).split("/", 1)
                members.append((int(sid_s), int(zid_s)))
            except Exception:
                continue
        if members:
            entities.append(AirzoneGroupClimate(coordinator, gid, name, members))

    if entities:
        add_entities(entities)
    else:
        _LOGGER.debug("No climate entities to add (no zones found).")


class AirzoneZoneClimate(CoordinatorEntity[AirzoneCoordinator], ClimateEntity):
    """Termostato por zona."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AirzoneCoordinator,
        system_id: int,
        zone_id: int,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._system_id = int(system_id)
        self._zone_id = int(zone_id)
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_climate_{self._system_id}_{self._zone_id}"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._system_id}-{self._zone_id}")},
            name=self.name,
            manufacturer="Airzone",
            model="Local API zone",
        )

    # ---------- Helpers ----------

    def _zone(self) -> dict | None:
        return self.coordinator.get_zone(self._system_id, self._zone_id)

    @staticmethod
    def _zone_target_temperature(z: dict) -> Optional[float]:
        return z.get("setpoint") or z.get("heatsetpoint") or z.get("coolsetpoint")

    @staticmethod
    def _zone_current_temperature(z: dict) -> Optional[float]:
        return (
            z.get("roomTemp")
            or z.get("room_temperature")
            or z.get("temp_return")
            or z.get("temp")
            or z.get("temperature")
        )

    @staticmethod
    def _zone_min_temp(z: dict) -> float:
        return float(z.get("minTemp") or z.get("mintemp") or 15)

    @staticmethod
    def _zone_max_temp(z: dict) -> float:
        return float(z.get("maxTemp") or z.get("maxtemp") or 30)

    # ---------- Properties ----------

    @property
    def available(self) -> bool:
        return self._zone() is not None

    @property
    def current_temperature(self) -> float | None:
        z = self._zone()
        if not z:
            return None
        t = self._zone_current_temperature(z)
        return float(t) if t is not None else None

    @property
    def target_temperature(self) -> float | None:
        z = self._zone()
        if not z:
            return None
        t = self._zone_target_temperature(z)
        return float(t) if t is not None else None

    @property
    def min_temp(self) -> float:
        z = self._zone()
        if not z:
            return 15
        return self._zone_min_temp(z)

    @property
    def max_temp(self) -> float:
        z = self._zone()
        if not z:
            return 30
        return self._zone_max_temp(z)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        z = self._zone()
        if not z:
            return [HVACMode.OFF]
        modes = allowed_hvac_modes_for_zone(z)
        return modes or [HVACMode.OFF]

    @property
    def hvac_mode(self) -> HVACMode:
        z = self._zone()
        if not z:
            return HVACMode.OFF
        try:
            if int(z.get("on", 1)) == 0:
                return HVACMode.OFF
        except Exception:
            pass
        return translate_current_mode(z, self.hvac_modes)

    @property
    def hvac_action(self) -> HVACAction | None:
        z = self._zone()
        if not z:
            return HVACAction.OFF
        try:
            if int(z.get("on", 1)) == 0:
                return HVACAction.OFF
        except Exception:
            pass

        mode = self.hvac_mode
        if mode == HVACMode.HEAT:
            return HVACAction.HEATING
        if mode == HVACMode.COOL:
            return HVACAction.COOLING
        if mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        if mode == HVACMode.DRY:
            return HVACAction.DRYING
        if mode == HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    # ---------- Actions ----------

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        value = float(temp)
        await self.coordinator.async_set_zone_params(
            self._system_id,
            self._zone_id,
            setpoint=value,
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_set_zone_params(
                self._system_id,
                self._zone_id,
                on=0,
            )
            return

        code = HVAC_TO_API_MODE.get(hvac_mode)
        body: Dict[str, Any] = {"on": 1}
        if code is not None:
            body["mode"] = code

        await self.coordinator.async_set_zone_params(
            self._system_id,
            self._zone_id,
            **body,
        )

    async def async_turn_on(self) -> None:
        await self.coordinator.async_set_zone_params(
            self._system_id,
            self._zone_id,
            on=1,
        )

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_zone_params(
            self._system_id,
            self._zone_id,
            on=0,
        )


# ---------------------------------------------------------------------------
#  Termostato MAESTRO por sistema
# ---------------------------------------------------------------------------


class AirzoneMasterClimate(CoordinatorEntity[AirzoneCoordinator], ClimateEntity):
    """Control maestro por sistema: actúa sobre todas las zonas del sistema."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AirzoneCoordinator, system_id: int, zone_ids: List[int]
    ) -> None:
        super().__init__(coordinator)
        self._system_id = int(system_id)
        self._zone_ids: List[int] = [int(z) for z in zone_ids]
        self._attr_name = f"Termostato Maestro S{self._system_id}"
        self._attr_unique_id = f"{DOMAIN}_master_{self._system_id}"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"master-{self._system_id}")},
            name=f"Airzone System {self._system_id}",
            manufacturer="Airzone",
            model="Local API system",
        )

    def _zones(self) -> List[dict]:
        out: List[dict] = []
        for zid in self._zone_ids:
            z = self.coordinator.get_zone(self._system_id, zid)
            if z:
                out.append(z)
        return out

    @staticmethod
    def _zone_target_temperature(z: dict) -> Optional[float]:
        return z.get("setpoint") or z.get("heatsetpoint") or z.get("coolsetpoint")

    @staticmethod
    def _zone_current_temperature(z: dict) -> Optional[float]:
        return (
            z.get("roomTemp")
            or z.get("room_temperature")
            or z.get("temp_return")
            or z.get("temp")
            or z.get("temperature")
        )

    @staticmethod
    def _zone_min_temp(z: dict) -> float:
        return float(z.get("minTemp") or z.get("mintemp") or 15)

    @staticmethod
    def _zone_max_temp(z: dict) -> float:
        return float(z.get("maxTemp") or z.get("maxtemp") or 30)

    @property
    def available(self) -> bool:
        return bool(self._zones())

    @property
    def current_temperature(self) -> float | None:
        zones = self._zones()
        temps = []
        for z in zones:
            t = z.get("temp") or z.get("temperature")
            if t is not None:
                temps.append(float(t))
        if not temps:
            # fallback a roomTemp si no hay temp/temperature
            for z in zones:
                t = self._zone_current_temperature(z)
                if t is not None:
                    temps.append(float(t))
        if not temps:
            return None
        return sum(temps) / len(temps)

    @property
    def target_temperature(self) -> float | None:
        zones = self._zones()
        targets = []
        for z in zones:
            t = self._zone_target_temperature(z)
            if t is not None:
                targets.append(float(t))
        if not targets:
            return None
        return sum(targets) / len(targets)

    @property
    def min_temp(self) -> float:
        zones = self._zones()
        if not zones:
            return 15
        return min(self._zone_min_temp(z) for z in zones)

    @property
    def max_temp(self) -> float:
        zones = self._zones()
        if not zones:
            return 30
        return max(self._zone_max_temp(z) for z in zones)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        zones = self._zones()
        if not zones:
            return [HVACMode.OFF]
        mode_sets: List[set[HVACMode]] = []
        for z in zones:
            modes = allowed_hvac_modes_for_zone(z)
            if modes:
                mode_sets.append(set(modes))
        if not mode_sets:
            return [HVACMode.OFF]
        common = set.intersection(*mode_sets) if mode_sets else {HVACMode.OFF}
        if HVACMode.OFF not in common:
            common.add(HVACMode.OFF)
        return list(common)

    @property
    def hvac_mode(self) -> HVACMode:
        zones = self._zones()
        if not zones:
            return HVACMode.OFF

        # OFF solo si TODAS las zonas están OFF
        first_on: dict | None = None
        for z in zones:
            try:
                if int(z.get("on", 1)) != 0:
                    first_on = z
                    break
            except Exception:
                # Si no podemos interpretar 'on', asumimos que está activa
                first_on = z
                break

        if first_on is None:
            return HVACMode.OFF

        return translate_current_mode(first_on, self.hvac_modes)

    @property
    def hvac_action(self) -> HVACAction | None:
        zones = self._zones()
        if not zones:
            return HVACAction.OFF

        all_off = True
        for z in zones:
            try:
                if int(z.get("on", 1)) != 0:
                    all_off = False
                    break
            except Exception:
                all_off = False
                break
        if all_off:
            return HVACAction.OFF

        mode = self.hvac_mode
        if mode == HVACMode.HEAT:
            return HVACAction.HEATING
        if mode == HVACMode.COOL:
            return HVACAction.COOLING
        if mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        if mode == HVACMode.DRY:
            return HVACAction.DRYING
        if mode == HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        value = float(temp)

        for zid in self._zone_ids:
            await self.coordinator.async_set_zone_params(
                self._system_id,
                zid,
                request_refresh=False,
                setpoint=value,
            )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        # El termostato maestro NO cambia el modo (eso lo hace el modo global o el selector por zona).
        # Aquí solo hacemos ON/OFF masivo.
        if hvac_mode == HVACMode.OFF:
            for zid in self._zone_ids:
                await self.coordinator.async_set_zone_params(
                    self._system_id,
                    zid,
                    request_refresh=False,
                    on=0,
                )
            await self.coordinator.async_request_refresh()
            return

        for zid in self._zone_ids:
            await self.coordinator.async_set_zone_params(
                self._system_id,
                zid,
                request_refresh=False,
                on=1,
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        for zid in self._zone_ids:
            await self.coordinator.async_set_zone_params(
                self._system_id,
                zid,
                request_refresh=False,
                on=1,
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        for zid in self._zone_ids:
            await self.coordinator.async_set_zone_params(
                self._system_id,
                zid,
                request_refresh=False,
                on=0,
            )
        await self.coordinator.async_request_refresh()


# ---------------------------------------------------------------------------
#  Termostato de GRUPO (zonas lógicas del usuario)
# ---------------------------------------------------------------------------


class AirzoneGroupClimate(CoordinatorEntity[AirzoneCoordinator], ClimateEntity):
    """Control por grupo lógico: actúa sobre las zonas que el usuario asigne al grupo."""

    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: AirzoneCoordinator,
        group_id: str,
        name: str,
        members: List[Tuple[int, int]],
    ) -> None:
        super().__init__(coordinator)
        self._group_id = group_id
        self._members: List[Tuple[int, int]] = [
            (int(sid), int(zid)) for sid, zid in members
        ]
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_group_{self._group_id}"
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )

    # ---------- Helpers ----------

    def _zones(self) -> List[dict]:
        """Lista de zonas reales incluidas en este grupo."""
        out: List[dict] = []
        for system_id, zone_id in self._members:
            z = self.coordinator.get_zone(system_id, zone_id)
            if z:
                out.append(z)
        return out

    @staticmethod
    def _zone_target_temperature(z: dict) -> Optional[float]:
        return z.get("setpoint") or z.get("heatsetpoint") or z.get("coolsetpoint")

    @staticmethod
    def _zone_current_temperature(z: dict) -> Optional[float]:
        return (
            z.get("roomTemp")
            or z.get("room_temperature")
            or z.get("temp_return")
            or z.get("temp")
            or z.get("temperature")
        )

    @staticmethod
    def _zone_min_temp(z: dict) -> float:
        return float(z.get("minTemp") or z.get("mintemp") or 15)

    @staticmethod
    def _zone_max_temp(z: dict) -> float:
        return float(z.get("maxTemp") or z.get("maxtemp") or 30)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"group-{self._group_id}")},
            name=self.name,
            manufacturer="Airzone",
            model="Logical group",
        )

    # ---------- Properties ----------

    @property
    def available(self) -> bool:
        return bool(self._zones())

    @property
    def current_temperature(self) -> float | None:
        zones = self._zones()
        temps = []
        for z in zones:
            t = self._zone_current_temperature(z)
            if t is not None:
                temps.append(float(t))
        if not temps:
            return None
        return sum(temps) / len(temps)

    @property
    def target_temperature(self) -> float | None:
        zones = self._zones()
        targets = []
        for z in zones:
            t = self._zone_target_temperature(z)
            if t is not None:
                targets.append(float(t))
        if not targets:
            return None
        return sum(targets) / len(targets)

    @property
    def min_temp(self) -> float:
        zones = self._zones()
        if not zones:
            return 15
        return min(self._zone_min_temp(z) for z in zones)

    @property
    def max_temp(self) -> float:
        zones = self._zones()
        if not zones:
            return 30
        return max(self._zone_max_temp(z) for z in zones)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        zones = self._zones()
        if not zones:
            return [HVACMode.OFF]

        mode_sets: List[set[HVACMode]] = []
        for z in zones:
            modes = allowed_hvac_modes_for_zone(z)
            if modes:
                mode_sets.append(set(modes))

        if not mode_sets:
            return [HVACMode.OFF]

        common = set.intersection(*mode_sets) if mode_sets else {HVACMode.OFF}
        if HVACMode.OFF not in common:
            common.add(HVACMode.OFF)
        return list(common)

    @property
    def hvac_mode(self) -> HVACMode:
        zones = self._zones()
        if not zones:
            return HVACMode.OFF

        # OFF solo si TODAS las zonas del grupo están OFF
        first_on: dict | None = None
        for z in zones:
            try:
                if int(z.get("on", 1)) != 0:
                    first_on = z
                    break
            except Exception:
                first_on = z
                break

        if first_on is None:
            return HVACMode.OFF

        return translate_current_mode(first_on, self.hvac_modes)

    @property
    def hvac_action(self) -> HVACAction | None:
        zones = self._zones()
        if not zones:
            return HVACAction.OFF

        all_off = True
        for z in zones:
            try:
                if int(z.get("on", 1)) != 0:
                    all_off = False
                    break
            except Exception:
                all_off = False
                break
        if all_off:
            return HVACAction.OFF

        mode = self.hvac_mode
        if mode == HVACMode.HEAT:
            return HVACAction.HEATING
        if mode == HVACMode.COOL:
            return HVACAction.COOLING
        if mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN
        if mode == HVACMode.DRY:
            return HVACAction.DRYING
        if mode == HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    # ---------- Actions ----------

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        value = float(temp)

        for system_id, zone_id in self._members:
            await self.coordinator.async_set_zone_params(
                system_id,
                zone_id,
                request_refresh=False,
                setpoint=value,
            )
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            for system_id, zone_id in self._members:
                await self.coordinator.async_set_zone_params(
                    system_id,
                    zone_id,
                    request_refresh=False,
                    on=0,
                )
            await self.coordinator.async_request_refresh()
            return

        code = HVAC_TO_API_MODE.get(hvac_mode)
        body: Dict[str, Any] = {"on": 1}
        if code is not None:
            body["mode"] = code

        for system_id, zone_id in self._members:
            await self.coordinator.async_set_zone_params(
                system_id,
                zone_id,
                request_refresh=False,
                **body,
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        for system_id, zone_id in self._members:
            await self.coordinator.async_set_zone_params(
                system_id,
                zone_id,
                request_refresh=False,
                on=1,
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        for system_id, zone_id in self._members:
            await self.coordinator.async_set_zone_params(
                system_id,
                zone_id,
                request_refresh=False,
                on=0,
            )
        await self.coordinator.async_request_refresh()
