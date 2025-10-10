from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirzoneCoordinator
from . import i18n

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    data = hass.data.get(DOMAIN, {})
    coord: AirzoneCoordinator | None = None
    if isinstance(data, dict):
        bundle = data.get(entry.entry_id)
        if isinstance(bundle, dict):
            coord = bundle.get("coordinator")
    if not isinstance(coord, AirzoneCoordinator):
        # compat legacy
        if isinstance(data, AirzoneCoordinator):
            coord = data
    if not isinstance(coord, AirzoneCoordinator):
        _LOGGER.warning("AirzoneCoordinator not found; aborting select setup.")
        return

    entities: List[SelectEntity] = []

    # MODO GLOBAL por SISTEMA
    system_ids = sorted({sid for (sid, _zid) in (coord.data or {}).keys()})
    for sid in system_ids:
        entities.append(GlobalModeSelect(coord, sid))

    # MODO y VELOCIDAD por ZONA
    for (sid, zid), z in (coord.data or {}).items():
        entities.append(ZoneModeSelect(coord, sid, zid))
        try:
            has_speed_values = isinstance(z.get("speed_values"), list) and len(z.get("speed_values")) > 0
            has_speeds = int(z.get("speeds", 0) or 0) > 0
            has_speed_field = "speed" in z
            if has_speed_values or has_speeds or has_speed_field:
                entities.append(ZoneFanSpeedSelect(coord, sid, zid))
        except Exception:
            pass

    # IAQ: Modo de ventilación
    if isinstance(getattr(coord, "iaqs", None), dict):
        for (sid, iid), _iaq in coord.iaqs.items():
            entities.append(IAQVentModeSelect(coord, sid, iid))

    async_add_entities(entities)


# ======================= SELECT: ZONA (MODO) ========================

class ZoneModeSelect(CoordinatorEntity[AirzoneCoordinator], SelectEntity):
    """Selector 'Modo' por zona (aplica solo a esa zona)."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "mode"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._zid = int(zone_id)
        self._attr_unique_id = f"{DOMAIN}_zone_{self._sid}_{self._zid}_mode"
        z = coordinator.get_zone(system_id, zone_id) or {}
        self._device_name = z.get("name") or f"Zona {self._sid}/{self._zid}"

    # ---- helpers ----
    def _zone(self) -> dict:
        return self.coordinator.get_zone(self._sid, self._zid) or {}

    def _zone_modes_codes(self) -> List[int]:
        """Modos enumerados para esta zona."""
        z = self._zone()
        zm = z.get("modes")
        codes: List[int] = []
        if isinstance(zm, list) and zm:
            try:
                codes = [int(x) for x in zm]
            except Exception:
                codes = []
        if not codes:
            try:
                cur = int(z.get("mode"))
                if cur:
                    codes = [cur]
            except Exception:
                pass
        known = [c for c in [2, 3, 4, 5, 7] if c in codes] or [2, 3, 4, 5, 7]
        return known

    # -------- SelectEntity --------
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

    @property
    def options(self) -> List[str]:
        off = i18n.label(self.coordinator.hass, "off")
        names = [i18n.mode_name(self.coordinator.hass, c) for c in self._zone_modes_codes()]
        names = [n for n in names if n and n != off]
        out = [off]
        for n in names:
            if n not in out:
                out.append(n)
        return out

    @property
    def current_option(self) -> Optional[str]:
        z = self._zone()
        try:
            if int(z.get("on", 0)) == 0:
                return i18n.label(self.coordinator.hass, "off")
        except Exception:
            pass
        try:
            return i18n.mode_name(self.coordinator.hass, int(z.get("mode")))
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        option = str(option or "").strip()
        if option not in self.options:
            _LOGGER.debug(
                "Opción '%s' no válida para zona %s/%s; opciones: %s",
                option, self._sid, self._zid, self.options
            )
            return
        if option == i18n.label(self.coordinator.hass, "off"):
            await self.coordinator.async_set_zone_params(self._sid, self._zid, on=0)
            return

        # buscar código del nombre
        for code in [2, 3, 4, 5, 7]:
            if i18n.mode_name(self.coordinator.hass, code) == option:
                await self.coordinator.async_set_zone_params(self._sid, self._zid, on=1, mode=int(code))
                return

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


# ======================= SELECT: SISTEMA (MODO GLOBAL) ========================

class GlobalModeSelect(CoordinatorEntity[AirzoneCoordinator], SelectEntity):
    """Selector 'Modo' global por sistema (aplica a todas las zonas)."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "mode_global"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._attr_unique_id = f"{DOMAIN}_system_{self._sid}_mode_global"

    # --- helpers ---
    def _zones(self) -> List[dict]:
        return self.coordinator.zones_of_system(self._sid)

    def _sys_modes_codes(self) -> List[int]:
        zones = self._zones()
        if not zones:
            return [2, 3, 4, 5, 7]
        codes: List[int] = []
        for z in zones:
            zm = z.get("modes")
            if isinstance(zm, list) and zm:
                try:
                    codes.extend([int(x) for x in zm])
                except Exception:
                    continue
            else:
                try:
                    codes.append(int(z.get("mode")))
                except Exception:
                    continue
        out = []
        for c in [2, 3, 4, 5, 7]:
            if c in codes and c not in out:
                out.append(c)
        return out or [2, 3, 4, 5, 7]

    # -------- SelectEntity --------
    @property
    def available(self) -> bool:
        return bool(self._zones())

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"system-{self._sid}")},
            name=f"Sistema {self._sid}",
            manufacturer="Airzone",
            model="HVAC System",
        )

    @property
    def options(self) -> List[str]:
        off = i18n.label(self.coordinator.hass, "off")
        names = [i18n.mode_name(self.coordinator.hass, c) for c in self._sys_modes_codes()]
        names = [n for n in names if n and n != off]
        out = [off]
        for n in names:
            if n not in out:
                out.append(n)
        return out

    @property
    def current_option(self) -> Optional[str]:
        zones = self._zones()
        try:
            if zones and all(int(z.get("on", 0)) == 0 for z in zones):
                return i18n.label(self.coordinator.hass, "off")
        except Exception:
            pass
        try:
            modes = [int(z.get("mode")) for z in zones if int(z.get("on", 0)) == 1]
            for cand in [2, 3, 4, 5, 7]:
                if cand in modes:
                    return i18n.mode_name(self.coordinator.hass, cand)
        except Exception:
            pass
        return None

    async def async_select_option(self, option: str) -> None:
        option = str(option or "").strip()
        if option not in self.options:
            _LOGGER.debug(
                "Opción '%s' no válida para sistema %s; opciones: %s",
                option, self._sid, self.options
            )
            return

        tasks: List[asyncio.Task] = []
        if option == i18n.label(self.coordinator.hass, "off"):
            for z in self._zones():
                try:
                    sid = int(z.get("systemID"))
                    zid = int(z.get("zoneID"))
                    tasks.append(asyncio.create_task(self.coordinator.async_set_zone_params(sid, zid, on=0)))
                except Exception:
                    continue
        else:
            code: Optional[int] = None
            for cand in [2, 3, 4, 5, 7]:
                if i18n.mode_name(self.coordinator.hass, cand) == option:
                    code = cand
                    break
            if code is None:
                return
            for z in self._zones():
                try:
                    sid = int(z.get("systemID"))
                    zid = int(z.get("zoneID"))
                    body: Dict[str, Any] = {"on": 1, "mode": int(code)}
                    tasks.append(asyncio.create_task(self.coordinator.async_set_zone_params(sid, zid, **body)))
                except Exception as e:
                    _LOGGER.debug("No se pudo programar cambio de modo en zona %s: %s", z, e)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


# ======================= SELECT: ZONA (VELOCIDAD) ========================

class ZoneFanSpeedSelect(CoordinatorEntity[AirzoneCoordinator], SelectEntity):
    """Selector de **velocidad** del ventilador por zona."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "speed"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._zid = int(zone_id)
        self._attr_unique_id = f"{DOMAIN}_zone_{self._sid}_{self._zid}_speed"
        z = coordinator.get_zone(system_id, zone_id) or {}
        self._device_name = z.get("name") or f"Zona {self._sid}/{self._zid}"

    # ---- helpers ----
    def _zone(self) -> dict:
        return self.coordinator.get_zone(self._sid, self._zid) or {}

    def _speed_values(self) -> List[int]:
        z = self._zone()
        sv = z.get("speed_values")
        if isinstance(sv, list) and sv:
            out: List[int] = []
            for x in sv:
                try:
                    v = int(x)
                    if v not in out:
                        out.append(v)
                except Exception:
                    continue
            return sorted(out)
        try:
            n = int(z.get("speeds", 0) or 0)
        except Exception:
            n = 0
        vals: List[int] = []
        if n > 0:
            cur = None
            try:
                cur = int(z.get("speed"))
            except Exception:
                pass
            include_auto = (cur == 0) or ("speed_type" in z)
            start = 0 if include_auto else 1
            vals = list(range(start, n + 1))
        if not vals and "speed" in z:
            try:
                vals = [int(z.get("speed"))]
            except Exception:
                vals = []
        return vals

    def _label_for(self, value: int) -> str:
        values = self._speed_values()
        max_level = max([v for v in values if v != 0], default=None)
        return i18n.speed_label(self.coordinator.hass, value, max_level, values)

    def _rev_map(self) -> Dict[str, int]:
        return {self._label_for(v): v for v in self._speed_values()}

    # -------- SelectEntity --------
    @property
    def available(self) -> bool:
        try:
            return bool(self._speed_values())
        except Exception:
            return False

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

    @property
    def options(self) -> List[str]:
        return [self._label_for(v) for v in self._speed_values()]

    @property
    def current_option(self) -> Optional[str]:
        z = self._zone()
        try:
            cur = int(z.get("speed"))
            return self._label_for(cur)
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        option = str(option or "").strip()
        rev = self._rev_map()
        if option not in rev:
            _LOGGER.debug(
                "Opción de velocidad no válida zona %s/%s: %s (opciones: %s)",
                self._sid, self._zid, option, list(rev)
            )
            return
        value = int(rev[option])
        await self.coordinator.async_set_zone_params(self._sid, self._zid, on=1, speed=value)

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


# ======================= SELECT: IAQ (MODO VENTILACIÓN) ========================

class IAQVentModeSelect(CoordinatorEntity[AirzoneCoordinator], SelectEntity):
    """Selector del 'modo de ventilación' de la sonda IAQ (iaq_mode_vent)."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "ventilation"

    _VENT_CODES = [0, 1, 2]  # 0=Off, 1=Manual, 2=Auto

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, iaq_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._iid = int(iaq_id)
        self._attr_unique_id = f"{DOMAIN}_iaq_{self._sid}_{self._iid}_ventilation"
        iaq = coordinator.get_iaq(system_id, iaq_id) or {}
        self._device_name = iaq.get("name") or f"IAQ {self._sid}/{self._iid}"

    # Helpers
    def _iaq(self) -> dict:
        return self.coordinator.get_iaq(self._sid, self._iid) or {}

    # SelectEntity
    @property
    def available(self) -> bool:
        d = self._iaq()
        return "iaq_mode_vent" in d

    @property
    def device_info(self) -> DeviceInfo:
        iaq = self._iaq()
        return DeviceInfo(
            identifiers={(DOMAIN, f"iaq-{self._sid}-{self._iid}")},
            name=iaq.get("name") or f"IAQ {self._sid}/{self._iid}",
            manufacturer="Airzone",
            model="IAQ Sensor",
        )

    @property
    def options(self) -> List[str]:
        return [i18n.iaq_vent_label(self.coordinator.hass, c) for c in self._VENT_CODES]

    @property
    def current_option(self) -> Optional[str]:
        iaq = self._iaq()
        try:
            code = int(iaq.get("iaq_mode_vent"))
            return i18n.iaq_vent_label(self.coordinator.hass, code)
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        option = str(option or "").strip()
        code = None
        for cand in self._VENT_CODES:
            if i18n.iaq_vent_label(self.coordinator.hass, cand) == option:
                code = cand
                break
        if code is None:
            _LOGGER.debug("Opción de ventilación IAQ no válida: %s", option)
            return
        await self.coordinator.async_set_iaq_params(self._sid, self._iid, iaq_mode_vent=int(code))

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
