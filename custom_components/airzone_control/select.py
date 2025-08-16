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

_LOGGER = logging.getLogger(__name__)

# Tabla canónica (Local API)
# 0/1=Apagado, 2=Frío, 3=Calor, 4=Ventilación, 5=Seco, 7=Auto
MODE_NAME_BY_CODE: Dict[int, str] = {
    0: "Apagado",
    1: "Apagado",
    2: "Frío",
    3: "Calor",
    4: "Ventilación",
    5: "Seco",
    7: "Auto",
}
MODE_CODE_BY_NAME: Dict[str, int] = {v: k for k, v in MODE_NAME_BY_CODE.items()}


# =========================== SETUP ===========================

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
        _LOGGER.warning("AirzoneCoordinator not found; aborting select setup.")
        return

    entities: List[SelectEntity] = []

    # --- Select de MODO GLOBAL por SISTEMA ---
    system_ids = sorted({sid for (sid, _zid) in (coord.data or {}).keys()})
    for sid in system_ids:
        entities.append(GlobalModeSelect(coord, sid))

    # --- Select de MODO por ZONA ---
    for (sid, zid), z in (coord.data or {}).items():
        entities.append(ZoneModeSelect(coord, sid, zid))

    async_add_entities(entities)


# ======================= SELECT: ZONA ========================

class ZoneModeSelect(CoordinatorEntity[AirzoneCoordinator], SelectEntity):
    """Selector 'Modo' por zona (aplica solo a esa zona)."""

    _attr_should_poll = False

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int, zone_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._zid = int(zone_id)
        z = coordinator.get_zone(system_id, zone_id) or {}
        name = z.get("name") or f"Zona {self._sid}/{self._zid}"
        self._attr_name = "Modo"
        self._attr_unique_id = f"{DOMAIN}_zone_{self._sid}_{self._zid}_mode"
        self._device_name = name  # solo para device_info

    # ---- helpers ----
    def _zone(self) -> dict:
        return self.coordinator.get_zone(self._sid, self._zid) or {}

    def _zone_modes_codes(self) -> List[int]:
        """Modos enumerados por la API para esta zona (o heredados del sistema)."""
        z = self._zone()
        # 1) modos de la zona
        zm = z.get("modes")
        if isinstance(zm, list) and zm:
            try:
                return [int(x) for x in zm if int(x) in MODE_NAME_BY_CODE]
            except Exception:
                pass
        # 2) modos de sistema inyectados por el coordinator
        sm = z.get("sys_modes")
        if isinstance(sm, list) and sm:
            try:
                return [int(x) for x in sm if int(x) in MODE_NAME_BY_CODE]
            except Exception:
                pass
        # 3) fallback: solo el modo actual (si existe)
        try:
            cur = int(z.get("mode"))
            return [cur] if cur in MODE_NAME_BY_CODE else []
        except Exception:
            return []

    # ---- SelectEntity ----
    @property
    def available(self) -> bool:
        return bool(self._zone())

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._sid}-{self._zid}")},
            name=self._device_name,
            manufacturer="Airzone",
            model="Local API zone",
        )

    @property
    def options(self) -> List[str]:
        codes = self._zone_modes_codes()
        # "Apagado" siempre visible
        names = [MODE_NAME_BY_CODE.get(c) for c in codes if c in MODE_NAME_BY_CODE and c not in (0, 1)]
        out = ["Apagado"]
        out.extend([n for n in names if n and n not in out])
        return out

    @property
    def current_option(self) -> Optional[str]:
        z = self._zone()
        try:
            if int(z.get("on", 1)) == 0:
                return "Apagado"
        except Exception:
            pass
        try:
            code = int(z.get("mode"))
            return MODE_NAME_BY_CODE.get(code)
        except Exception:
            return None

    async def async_select_option(self, option: str) -> None:
        option = str(option or "").strip()
        if option not in self.options:
            _LOGGER.debug("Opción '%s' no válida para zona %s/%s; opciones: %s",
                          option, self._sid, self._zid, self.options)
            return
        if option == "Apagado":
            await self.coordinator.async_set_zone_params(self._sid, self._zid, on=0)
            return

        code = MODE_CODE_BY_NAME.get(option)
        if code in (None, 0, 1):
            return
        await self.coordinator.async_set_zone_params(self._sid, self._zid, on=1, mode=int(code))

    # Mantener UI al día
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


# ====================== SELECT: GLOBAL =======================

class GlobalModeSelect(CoordinatorEntity[AirzoneCoordinator], SelectEntity):
    """Selector 'Modo global' por sistema. Aplica el modo a TODAS las zonas."""

    _attr_should_poll = False

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)
        self._attr_name = "Modo global"
        self._attr_unique_id = f"{DOMAIN}_system_{self._sid}_global_mode"

    # -------- helpers --------
    def _zones(self) -> List[dict]:
        return self.coordinator.zones_of_system(self._sid)

    def _sys_modes_codes(self) -> List[int]:
        """Prioriza `modes` de sistema; si no existen, une los de las zonas."""
        sysd = self.coordinator.get_system(self._sid) or {}
        modes = sysd.get("modes")
        if isinstance(modes, list) and modes:
            try:
                return [int(x) for x in modes if int(x) in MODE_NAME_BY_CODE]
            except Exception:
                pass

        codes: List[int] = []
        for z in self._zones():
            zm = z.get("modes")
            if isinstance(zm, list):
                for x in zm:
                    try:
                        xi = int(x)
                        if xi in MODE_NAME_BY_CODE and xi not in codes:
                            codes.append(xi)
                    except Exception:
                        continue
        return codes

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
        codes = self._sys_modes_codes()
        names = [MODE_NAME_BY_CODE.get(c) for c in codes if c in MODE_NAME_BY_CODE and c not in (0, 1)]
        out = ["Apagado"]
        out.extend([n for n in names if n and n not in out])
        return out

    @property
    def current_option(self) -> Optional[str]:
        zones = self._zones()
        if not zones:
            return None

        try:
            ons = [int(z.get("on", 0)) for z in zones]
        except Exception:
            ons = [1 for _ in zones]

        if all(v == 0 for v in ons):
            return "Apagado"

        mode_set = set()
        for z in zones:
            try:
                if int(z.get("on", 0)) == 0:
                    continue
                m = int(z.get("mode"))
                mode_set.add(m)
            except Exception:
                pass

        if len(mode_set) == 1:
            code = next(iter(mode_set))
            return MODE_NAME_BY_CODE.get(code)
        return None  # mixto

    async def async_select_option(self, option: str) -> None:
        option = str(option or "").strip()
        if option not in self.options:
            _LOGGER.debug("Opción '%s' no válida para sistema %s; opciones: %s", option, self._sid, self.options)
            return

        zones = self._zones()
        if not zones:
            return

        tasks: List[asyncio.Task] = []
        if option == "Apagado":
            for z in zones:
                try:
                    sid = int(z.get("systemID"))
                    zid = int(z.get("zoneID"))
                    tasks.append(asyncio.create_task(self.coordinator.async_set_zone_params(sid, zid, on=0)))
                except Exception as e:
                    _LOGGER.debug("No se pudo programar apagado de zona %s: %s", z, e)
        else:
            code = MODE_CODE_BY_NAME.get(option)
            if code in (0, 1, None):
                return
            for z in zones:
                try:
                    sid = int(z.get("systemID"))
                    zid = int(z.get("zoneID"))
                    body: Dict[str, Any] = {"on": 1, "mode": int(code)}
                    tasks.append(asyncio.create_task(self.coordinator.async_set_zone_params(sid, zid, **body)))
                except Exception as e:
                    _LOGGER.debug("No se pudo programar cambio de modo en zona %s: %s", z, e)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    _LOGGER.warning("Error aplicando modo global en alguna zona: %s", r)

        self.async_write_ha_state()
