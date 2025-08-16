from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Tuple, List, Optional

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Prefijos candidatos vistos en firmwares reales
CANDIDATE_PREFIXES: list[str] = ["", "/api/v1", "/airzone/local/api/v1", "/lapi/v1"]


class AirzoneCoordinator(DataUpdateCoordinator[Dict[Tuple[int, int], dict]]):
    def __init__(
        self,
        hass: HomeAssistant,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        api_prefix: str | None = None,
    ) -> None:
        self._host = host
        self._port = int(port or DEFAULT_PORT)
        self._prefix: str | None = api_prefix  # puede venir del config_flow

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=max(2, int(scan_interval or DEFAULT_SCAN_INTERVAL))),
        )

        self._session: aiohttp.ClientSession | None = None

        # Caches de datos normalizados
        self.webserver: dict | None = None
        self.systems: dict[int, dict] = {}
        self.iaqs: dict[tuple[int, int], dict] = {}
        self.iaq_fallback: dict[int, dict] = {}
        self.zone_profiles: dict[tuple[int, int], dict] = {}
        self.system_profiles: dict[int, dict] = {}

        # Diagnóstico
        self.transport_hvac: str | None = None
        self.transport_iaq: str | None = None
        self.version: str = "desconocida"

        # --- NUEVO: “modo hotel / seguir global” por sistema ---
        self._follow_master_enabled: set[int] = set()

    # ---------------- base url / sesión ----------------
    def _base(self) -> str:
        return f"http://{self._host}:{self._port}{(self._prefix or '')}"

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        self._session = aiohttp.ClientSession()
        return self._session

    async def _detect_prefix(self) -> None:
        if self._prefix is not None:
            return
        timeout = 6
        s = await self._ensure_session()
        for pref in CANDIDATE_PREFIXES:
            base = f"http://{self._host}:{self._port}{pref}"
            try:
                async with s.get(f"{base}/webserver", timeout=timeout) as r:
                    if r.status == 200:
                        self._prefix = pref
                        _LOGGER.debug("Detected API prefix via GET /webserver: %s", pref)
                        return
            except Exception:
                pass
            try:
                async with s.post(f"{base}/webserver", json={}, timeout=timeout) as r:
                    if r.status == 200:
                        self._prefix = pref
                        _LOGGER.debug("Detected API prefix via POST /webserver: %s", pref)
                        return
            except Exception:
                pass
            try:
                async with s.get(f"{base}/hvac", params={"systemid": 0, "zoneid": 0}, timeout=timeout) as r:
                    if r.status == 200:
                        self._prefix = pref
                        _LOGGER.debug("Detected API prefix via GET /hvac: %s", pref)
                        return
            except Exception:
                pass
            try:
                async with s.post(f"{base}/hvac", json={"systemID": 0, "zoneID": 0}, timeout=timeout) as r:
                    if r.status == 200:
                        self._prefix = pref
                        _LOGGER.debug("Detected API prefix via POST /hvac: %s", pref)
                        return
            except Exception:
                pass
        self._prefix = ""  # última oportunidad

    # ---------------- HTTP helpers ----------------
    async def _get_json(self, path: str, params: dict | None = None) -> dict | list | None:
        s = await self._ensure_session()
        url = f"{self._base()}{path}"
        async with s.get(url, params=params, timeout=6) as resp:
            txt = await resp.text()
            if resp.status != 200:
                _LOGGER.debug("GET %s %s -> %s %s", path, params, resp.status, txt)
                return None
            try:
                return await resp.json(content_type=None)
            except Exception:
                return {"raw": txt}

    async def _post_json(self, path: str, body: dict) -> dict | list | None:
        s = await self._ensure_session()
        url = f"{self._base()}{path}"
        async with s.post(url, json=body, timeout=6) as resp:
            txt = await resp.text()
            if resp.status != 200:
                _LOGGER.debug("POST %s %s -> %s %s", path, body, resp.status, txt)
                return None
            try:
                return await resp.json(content_type=None)
            except Exception:
                return {"raw": txt}

    # ---------------- Normalizadores ----------------

    @staticmethod
    def _extract_zone_list(payload: Any) -> list[dict]:
        if not isinstance(payload, dict):
            return []
        if isinstance(payload.get("data"), list):
            return [x for x in payload["data"] if isinstance(x, dict) and "systemID" in x and "zoneID" in x]
        if isinstance(payload.get("systems"), list):
            out: list[dict] = []
            for s in payload["systems"]:
                d = s.get("data")
                if isinstance(d, list):
                    out.extend([x for x in d if isinstance(x, dict) and "systemID" in x and "zoneID" in x])
            return out
        return []

    @staticmethod
    def _extract_system_data(payload: Any, system_id: int) -> dict | None:
        if not isinstance(payload, dict):
            return None
        d = payload.get("data")
        if isinstance(d, dict):
            return d
        if isinstance(d, list):
            for item in d:
                if isinstance(item, dict) and int(item.get("systemID", -1)) == system_id:
                    di = item.get("data")
                    return di if isinstance(di, dict) else item
        if isinstance(payload.get("systems"), list):
            for s in payload["systems"]:
                if int(s.get("systemID", -1)) == system_id:
                    di = s.get("data")
                    return di if isinstance(di, dict) else s
        if any(k in payload for k in ("ext_temp", "temp_return", "work_temp", "num_airqsensor")):
            return payload
        return None

    @staticmethod
    def _extract_iaq_list(payload: Any) -> list[dict]:
        items: list[dict] = []

        def _norm(x: Any) -> dict | None:
            if not isinstance(x, dict):
                return None
            if "airqsensorID" in x and "iaqsensorID" not in x:
                x["iaqsensorID"] = x.pop("airqsensorID")
            return x

        if isinstance(payload, dict):
            d = payload.get("data")
            if isinstance(d, list):
                for x in d:
                    n = _norm(x);  n and items.append(n)
            elif isinstance(d, dict):
                n = _norm(d);   n and items.append(n)

            if isinstance(payload.get("systems"), list):
                for s in payload["systems"]:
                    dl = s.get("data")
                    if isinstance(dl, list):
                        for x in dl:
                            n = _norm(x); n and items.append(n)
                    elif isinstance(dl, dict):
                        n = _norm(dl); n and items.append(n)

        elif isinstance(payload, list):
            for x in payload:
                n = _norm(x); n and items.append(n)

        return items

    # ---------------- Perfiles/capacidades ----------------

    @staticmethod
    def _determine_zone_profile(z: dict) -> dict:
        caps: list[str] = []
        if z.get("double_sp") or ("heatsetpoint" in z or "coolsetpoint" in z):
            caps.append("double_sp")
        if "setpoint" in z:
            caps.append("setpoint")
        if "modes" in z:
            caps.append("modes")
        if z.get("speeds", 0) or z.get("speed_values"):
            caps.append("speeds")
        if any(k in z for k in ("slats_vertical","slats_horizontal","slats_vswing","slats_hswing")):
            caps.append("slats")
        for k in ("air_demand","cold_demand","heat_demand","floor_demand","open_window","antifreeze","eco_adapt"):
            if k in z:
                caps.append(k)
        if "humidity" in z:
            caps.append("humidity")

        if "double_sp" in caps:
            profile = "Zona doble setpoint"
        elif "setpoint" in caps and "slats" in caps:
            profile = "Zona setpoint único (+slats)"
        elif "setpoint" in caps:
            profile = "Zona setpoint único"
        else:
            profile = "Zona genérica"

        return {"profile": profile, "capabilities": caps}

    def _determine_system_profile(self, sid: int) -> dict:
        sysd = self.systems.get(sid, {}) or {}
        caps: list[str] = []
        for k in ("ext_temp", "temp_return", "work_temp"):
            if k in sysd:
                caps.append(k)

        if any(k[0] == sid for k in self.iaqs.keys()) or (sid in self.iaq_fallback):
            caps.append("iaq")

        has_double = any(
            "double_sp" in (self.zone_profiles.get((sid, zid), {}).get("capabilities") or [])
            for (s, zid) in self.zone_profiles.keys()
            if s == sid
        )

        if any(k in caps for k in ("ext_temp","temp_return","work_temp")):
            profile = "Air to Water (A2W)"
        else:
            profile = "Sistema HVAC (doble setpoint)" if has_double else "Sistema HVAC"

        return {"profile": profile, "capabilities": caps}

    # ---------------- Helpers públicos ----------------

    def zones_of_system(self, system_id: int) -> list[dict]:
        return [z for (sid, _), z in (self.data or {}).items() if sid == int(system_id)]

    def get_zone(self, system_id: int, zone_id: int) -> dict | None:
        return (self.data or {}).get((int(system_id), int(zone_id)))

    def get_system(self, system_id: int) -> dict | None:
        return self.systems.get(int(system_id))

    def get_iaq(self, system_id: int, iaq_id: int) -> dict | None:
        return self.iaqs.get((int(system_id), int(iaq_id)))

    # --- NUEVO: determinar zona máster de un sistema ---
    def master_zone_id(self, system_id: int) -> Optional[int]:
        zones = self.zones_of_system(system_id)
        if not zones:
            return None
        # Pistas explícitas
        for z in zones:
            for key in ("master", "is_master", "zone_master"):
                try:
                    if int(z.get(key, 0)) == 1:
                        return int(z.get("zoneID"))
                except Exception:
                    pass
            name = str(z.get("name") or "").lower()
            if "master" in name or "principal" in name or "despacho" in name:
                try:
                    return int(z.get("zoneID"))
                except Exception:
                    pass
        # Fallback: la de menor zoneID
        try:
            return min(int(z.get("zoneID")) for z in zones if "zoneID" in z)
        except Exception:
            return None

    # --- NUEVO: API “seguir global” ---
    def is_follow_master_enabled(self, system_id: int) -> bool:
        return int(system_id) in self._follow_master_enabled

    async def async_set_follow_master(self, system_id: int, enabled: bool) -> None:
        sid = int(system_id)
        if enabled:
            self._follow_master_enabled.add(sid)
            # Enforzar inmediatamente una pasada
            self.hass.async_create_task(self._enforce_follow_master(sid))
        else:
            self._follow_master_enabled.discard(sid)

    async def _enforce_follow_master(self, system_id: int) -> None:
        """Hace que todas las zonas copien on/mode de la zona máster. No bloquea el bucle principal."""
        sid = int(system_id)
        if sid not in self._follow_master_enabled:
            return
        mzid = self.master_zone_id(sid)
        if mzid is None:
            _LOGGER.debug("No master zone found for system %s; cannot enforce follow.", sid)
            return
        mz = self.get_zone(sid, mzid) or {}
        try:
            desired_on = int(mz.get("on", 0))
        except Exception:
            desired_on = 0
        # El modo solo lo aplicamos si está definido y es entero
        desired_mode: Optional[int] = None
        try:
            m = int(mz.get("mode"))
            desired_mode = m
        except Exception:
            desired_mode = None

        tasks: List[asyncio.Task] = []
        for z in self.zones_of_system(sid):
            try:
                zid = int(z.get("zoneID"))
            except Exception:
                continue
            if zid == mzid:
                continue
            # Comparar y ajustar 'on'
            try:
                cur_on = int(z.get("on", 0))
            except Exception:
                cur_on = 0
            if cur_on != desired_on:
                tasks.append(asyncio.create_task(self.async_set_zone_params(sid, zid, on=desired_on)))
                continue  # ya habrá otro refresh; el modo lo aplicamos en la siguiente pasada

            # Si está encendido y tenemos modo deseado, y difiere -> ponerlo
            if desired_on == 1 and desired_mode is not None:
                try:
                    cur_mode = int(z.get("mode"))
                except Exception:
                    cur_mode = None
                if cur_mode != desired_mode:
                    # Por seguridad, solo cambiamos de modo si la zona o el sistema dicen soportarlo
                    zm = z.get("modes") if isinstance(z.get("modes"), list) else (z.get("sys_modes") or [])
                    allowed = set(int(x) for x in zm if isinstance(zm, list))
                    if not allowed or desired_mode in allowed:
                        tasks.append(asyncio.create_task(self.async_set_zone_params(sid, zid, on=1, mode=desired_mode)))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    _LOGGER.warning("Follow-master: error al aplicar en alguna zona de sistema %s: %s", sid, r)
            # Tras aplicar, pedimos refresh
            self.hass.async_create_task(self.async_request_refresh())

    # ---------------- Fetchers ----------------

    async def _fetch_hvac_broadcast(self) -> dict | list | None:
        try:
            p = await self._get_json("/hvac", params={"systemid": 0, "zoneid": 0})
            if isinstance(p, (dict, list)):
                self.transport_hvac = "GET"
                return p
        except Exception as e:
            _LOGGER.debug("HVAC GET broadcast failed: %s", e)
        payload = await self._post_json("/hvac", {"systemID": 0, "zoneID": 0})
        self.transport_hvac = "POST"
        return payload

    async def _fetch_hvac_system(self, sid: int) -> dict | None:
        try:
            payload = await self._get_json("/hvac", params={"systemid": sid})
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
        try:
            return await self._post_json("/hvac", {"systemID": sid})
        except Exception as e:
            _LOGGER.debug("HVAC system %s fetch failed: %s", sid, e)
            return None

    async def _fetch_iaq_all(self) -> list[dict]:
        items: list[dict] = []
        self.transport_iaq = None

        try:
            p = await self._get_json("/iaq", params={"systemid": 0, "iaqsensorid": 0})
            items = self._extract_iaq_list(p)
            if items:
                self.transport_iaq = "GET"
                return items
        except Exception:
            pass

        for body in [{"systemID": 0, "iaqsensorID": 0}, {"systemID": 0}]:
            try:
                p = await self._post_json("/iaq", body)
                items = self._extract_iaq_list(p)
                if items:
                    self.transport_iaq = "POST"
                    return items
            except Exception:
                continue

        return items

    # ---------------- Update loop ----------------

    async def _async_update_data(self) -> Dict[Tuple[int, int], dict]:
        await self._detect_prefix()

        # 1) ZONAS
        zones = await self._fetch_hvac_broadcast()
        zones_list = self._extract_zone_list(zones)

        mapped: Dict[Tuple[int, int], dict] = {}
        system_ids: set[int] = set()
        self.iaq_fallback = {}
        self.zone_profiles = {}

        for z in zones_list:
            try:
                sid = int(z.get("systemID"))
                zid = int(z.get("zoneID"))
                mapped[(sid, zid)] = z
                system_ids.add(sid)
                self.zone_profiles[(sid, zid)] = self._determine_zone_profile(z)

                if "aq_quality" in z or "aq_mode" in z:
                    cur = self.iaq_fallback.setdefault(sid, {})
                    if "aq_quality" in z:
                        cur["aq_quality"] = z.get("aq_quality")
                    if "aq_mode" in z:
                        cur["aq_mode"] = z.get("aq_mode")
            except Exception as e:
                _LOGGER.debug("Skipping bad zone entry %s (%s)", z, e)

        # 2) SYSTEMS
        self.systems = {}

        async def fetch_system(sid: int):
            raw = await self._fetch_hvac_system(sid)
            data = self._extract_system_data(raw or {}, sid)
            if isinstance(data, dict):
                self.systems[sid] = data

        if system_ids:
            await asyncio.gather(*[fetch_system(s) for s in system_ids])

        # Inyectar sys_modes en cada zona
        try:
            for (sid, zid), z in mapped.items():
                try:
                    sysd = self.systems.get(sid) or {}
                    sm = sysd.get("modes")
                    if isinstance(sm, list) and sm:
                        z["sys_modes"] = sm
                except Exception:
                    continue
        except Exception:
            pass

        # 3) WEBSERVER
        try:
            ws = await self._post_json("/webserver", {})
            if isinstance(ws, dict):
                self.webserver = ws
                v = ws.get("api_ver") or ws.get("version") or ws.get("ws_firmware")
                if isinstance(v, str) and v:
                    self.version = v
        except Exception as e:
            _LOGGER.debug("Webserver fetch error: %s", e)
            self.webserver = None

        # 4) IAQ
        self.iaqs = {}
        iaq_items = await self._fetch_iaq_all()
        for item in iaq_items:
            try:
                sid = int(item.get("systemID"))
                iid = int(item.get("iaqsensorID"))
                self.iaqs[(sid, iid)] = item
            except Exception:
                continue

        # 5) Perfiles de sistema
        self.system_profiles = {}
        for sid in system_ids:
            prof = self._determine_system_profile(sid)
            prof["zone_count"] = len([1 for (s, _z) in mapped.keys() if s == sid])
            prof["iaq_count"] = len([1 for (s, _i) in self.iaqs.keys() if s == sid]) or (1 if sid in self.iaq_fallback else 0)
            self.system_profiles[sid] = prof

        # >>> NUEVO: si hay sistemas con “seguir global”, enforzamos (en background)
        for sid in list(self._follow_master_enabled):
            self.hass.async_create_task(self._enforce_follow_master(sid))

        return mapped

    # ---------------- API de escritura ----------------

    async def async_set_zone_params(self, system_id: int, zone_id: int, **kwargs) -> dict | None:
        """PUT /hvac con refresco inmediato (no bloqueante)."""
        body = {"systemID": int(system_id), "zoneID": int(zone_id)}
        body.update(kwargs)
        await self._detect_prefix()
        s = await self._ensure_session()
        url = f"{self._base()}/hvac"
        async with s.put(url, json=body, timeout=6) as resp:
            txt = await resp.text()
            if resp.status != 200:
                _LOGGER.error("PUT /hvac %s -> %s %s", body, resp.status, txt)
                raise UpdateFailed(f"PUT /hvac {resp.status}: {txt}")
            try:
                data = await resp.json(content_type=None)
            except Exception:
                data = {"raw": txt}
        # refresco sin bloquear
        self.hass.async_create_task(self.async_request_refresh())
        return data

    async def async_close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
