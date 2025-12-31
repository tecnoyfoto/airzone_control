from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirzoneCoordinator

_LOGGER = logging.getLogger(__name__)

# Ajustes "Hotel": robustez vs rapidez
_HOTEL_PASSES = 3  # número total de pasadas (1 inicial + reintentos)
_HOTEL_SLEEP_BETWEEN_CALLS = 0.05  # segundos entre PUTs para evitar saturar el webserver


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Crear los botones por sistema (Hotel)."""
    data = hass.data.get(DOMAIN, {})
    coord: AirzoneCoordinator | None = None
    if isinstance(data, dict):
        bundle = data.get(entry.entry_id)
        if isinstance(bundle, dict):
            coord = bundle.get("coordinator")
    if not isinstance(coord, AirzoneCoordinator):
        if isinstance(data, AirzoneCoordinator):
            coord = data
    if not isinstance(coord, AirzoneCoordinator):
        _LOGGER.warning("AirzoneCoordinator not found; aborting button setup.")
        return

    system_ids = sorted({sid for (sid, _zid) in (coord.data or {}).keys()})
    entities: List[ButtonEntity] = []
    for sid in system_ids:
        # unique_id estables (evitan duplicados)
        entities.append(HotelTurnAllOffButton(coord, sid))
        entities.append(HotelTurnAllOnButton(coord, sid))
        entities.append(HotelCopySetpointButton(coord, sid))

    async_add_entities(entities)


# -------------------- Base de botones por sistema --------------------


class _SystemButton(CoordinatorEntity[AirzoneCoordinator], ButtonEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True  # nombre traducido por translations/*.json

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator)
        self._sid = int(system_id)

    @property
    def available(self) -> bool:
        return any(
            1
            for (sid, _z) in (self.coordinator.data or {}).keys()
            if sid == self._sid
        )

    @property
    def device_info(self) -> DeviceInfo:
        # El nombre del DISPOSITIVO es la etiqueta de sistema; el nombre de la entidad lo aporta translation_key
        return DeviceInfo(
            identifiers={(DOMAIN, f"system-{self._sid}")},
            name=f"Sistema {self._sid}",
            manufacturer="Airzone",
            model="HVAC System",
        )

    def _zones(self) -> List[dict]:
        return self.coordinator.zones_of_system(self._sid)

    async def _hotel_set_all_on(self, desired_on: int) -> None:
        """Fuerza ON/OFF en todas las zonas con reintentos.

        Motivo: algunos webservers Airzone (según firmware/carga) pierden
        algún PUT si mandamos muchos a la vez.
        """
        desired_on = 1 if int(desired_on) else 0

        zones = self._zones()
        zone_ids: List[int] = []
        for z in zones:
            try:
                zone_ids.append(int(z.get("zoneID")))
            except Exception:
                continue

        if not zone_ids:
            return

        # Aseguramos tener estado inicial para validar reintentos
        await self.coordinator.async_request_refresh()

        for pas in range(_HOTEL_PASSES):
            pending: List[int] = []
            for zid in zone_ids:
                z = self.coordinator.get_zone(self._sid, zid)
                if not z:
                    pending.append(zid)
                    continue
                try:
                    cur = int(z.get("on", -1))
                except Exception:
                    cur = -1
                if cur != desired_on:
                    pending.append(zid)

            if not pending:
                return

            _LOGGER.debug(
                "[Hotel] System %s pass %s/%s -> set on=%s for zones %s",
                self._sid,
                pas + 1,
                _HOTEL_PASSES,
                desired_on,
                pending,
            )

            for zid in pending:
                try:
                    await self.coordinator.async_set_zone_params(
                        self._sid,
                        zid,
                        request_refresh=False,
                        on=desired_on,
                    )
                except Exception as e:
                    _LOGGER.debug("[Hotel] set on=%s failed for %s/%s: %s", desired_on, self._sid, zid, e)
                await asyncio.sleep(_HOTEL_SLEEP_BETWEEN_CALLS)

            await self.coordinator.async_request_refresh()

        # Si llegamos aquí, todavía queda algo desincronizado
        still: List[int] = []
        for zid in zone_ids:
            z = self.coordinator.get_zone(self._sid, zid)
            if not z:
                still.append(zid)
                continue
            try:
                cur = int(z.get("on", -1))
            except Exception:
                cur = -1
            if cur != desired_on:
                still.append(zid)

        if still:
            _LOGGER.warning(
                "[Hotel] System %s: after %s passes some zones did not reach on=%s: %s",
                self._sid,
                _HOTEL_PASSES,
                desired_on,
                still,
            )


# -------------------- Apagar todo (Hotel) --------------------


class HotelTurnAllOffButton(_SystemButton):
    _attr_translation_key = "hotel_off_all"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id)
        self._attr_unique_id = f"{DOMAIN}_system_{self._sid}_hotel_off_all"

    async def async_press(self) -> None:
        zones = self._zones()
        _LOGGER.debug("[Hotel] Turn ALL OFF on system %s (%d zones)", self._sid, len(zones))
        await self._hotel_set_all_on(0)


# -------------------- Encender todo (Hotel) --------------------


class HotelTurnAllOnButton(_SystemButton):
    _attr_translation_key = "hotel_on_all"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id)
        self._attr_unique_id = f"{DOMAIN}_system_{self._sid}_hotel_on_all"

    async def async_press(self) -> None:
        zones = self._zones()
        _LOGGER.debug("[Hotel] Turn ALL ON on system %s (%d zones)", self._sid, len(zones))
        await self._hotel_set_all_on(1)


# -------------------- Copiar consigna a todas (Hotel) --------------------


class HotelCopySetpointButton(_SystemButton):
    _attr_translation_key = "hotel_copy_sp"

    def __init__(self, coordinator: AirzoneCoordinator, system_id: int) -> None:
        super().__init__(coordinator, system_id)
        self._attr_unique_id = f"{DOMAIN}_system_{self._sid}_hotel_copy_sp"

    async def async_press(self) -> None:
        def _sfloat(d: dict, k: str) -> Optional[float]:
            v = d.get(k)
            try:
                return float(v)
            except Exception:
                return None

        def _sint(d: dict, k: str, default: int = 0) -> int:
            try:
                return int(d.get(k, default))
            except Exception:
                return default

        def _round_step(val: float, step: float) -> float:
            if not step:
                return float(val)
            return round(val / step) * step

        def _clamp(val: float, vmin: Optional[float], vmax: Optional[float]) -> float:
            out = float(val)
            if vmin is not None:
                out = max(out, float(vmin))
            if vmax is not None:
                out = min(out, float(vmax))
            return out

        mzid = self.coordinator.master_zone_id(self._sid)
        if mzid is None:
            _LOGGER.debug("[Hotel] Copy SP: no master zone in system %s", self._sid)
            return

        await self.coordinator.async_request_refresh()
        mz = self.coordinator.get_zone(self._sid, mzid) or {}

        m_set = _sfloat(mz, "setpoint")
        m_hs = _sfloat(mz, "heatsetpoint")
        m_cs = _sfloat(mz, "coolsetpoint")
        m_mode = _sint(mz, "mode", 0)
        m_step = _sfloat(mz, "temp_step") or 0.5

        if m_set is None:
            if m_mode == 3 and m_hs is not None:
                m_set = m_hs
            elif m_mode == 2 and m_cs is not None:
                m_set = m_cs
            elif m_hs is not None and m_cs is not None:
                m_set = (m_hs + m_cs) / 2.0

        zones = self._zones()
        _LOGGER.debug("[Hotel] Copy SP from master zone %s to %d zones", mzid, len(zones))

        for z in zones:
            try:
                zid = int(z.get("zoneID"))
            except Exception:
                continue
            if zid == mzid:
                continue

            step = _sfloat(z, "temp_step") or m_step
            maxTemp = _sfloat(z, "maxTemp")
            minTemp = _sfloat(z, "minTemp")
            heatmax = _sfloat(z, "heatmaxtemp") or maxTemp
            heatmin = _sfloat(z, "heatmintemp") or minTemp
            coolmax = _sfloat(z, "coolmaxtemp") or maxTemp
            coolmin = _sfloat(z, "coolmintemp") or minTemp

            double_sp = (
                _sint(z, "double_sp", 0) == 1
                or ("heatsetpoint" in z and "coolsetpoint" in z)
            )

            body: Dict[str, Any] = {}

            if double_sp and (m_hs is not None or m_cs is not None):
                if m_hs is not None:
                    v = _clamp(_round_step(m_hs, step), heatmin, heatmax)
                    body["heatsetpoint"] = v
                if m_cs is not None:
                    v = _clamp(_round_step(m_cs, step), coolmin, coolmax)
                    body["coolsetpoint"] = v
            elif m_set is not None:
                v = _clamp(_round_step(m_set, step), minTemp, maxTemp)
                body["setpoint"] = v
            else:
                _LOGGER.debug(
                    "[Hotel] Copy SP: nothing to copy for zone %s/%s", self._sid, zid
                )
                continue

            # IMPORTANTÍSIMO: copiar consigna NO cambia el ON/OFF
            try:
                await self.coordinator.async_set_zone_params(
                    self._sid,
                    zid,
                    request_refresh=False,
                    **body,
                )
            except Exception as e:
                _LOGGER.debug("[Hotel] Copy SP failed for %s/%s: %s", self._sid, zid, e)

            await asyncio.sleep(_HOTEL_SLEEP_BETWEEN_CALLS)

        await self.coordinator.async_request_refresh()
