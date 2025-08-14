from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, Dict, Tuple, List

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

class AirzoneCoordinator(DataUpdateCoordinator[Dict[Tuple[int, int], dict]]):
    """
    Lee la API local de Airzone y expone:
      - data: dict[(systemID, zoneID)] -> payload de zona
      - systems: dict[systemID] -> payload de sistema (temperaturas, etc.)
      - iaqs: dict[(systemID, iaqsensorID)] -> payload de IAQ (desde /iaq)
      - iaq_fallback: dict[systemID] -> {'aq_quality':..., 'aq_mode':...} (si no hay /iaq)
      - webserver: dict -> info del webserver
      - version: cadena con la versión de LAPI (/version)
      - transports usados (diagnóstico): transport_hvac, transport_iaq
      - perfiles/capacidades: system_profiles, zone_profiles
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        self._host = host
        self._port = int(port or DEFAULT_PORT)
        self._base = f"http://{self._host}:{self._port}/api/v1"
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=max(5, int(scan_interval or DEFAULT_SCAN_INTERVAL))),
        )
        self._session: aiohttp.ClientSession | None = None

        self.systems: Dict[int, dict] = {}
        self.iaqs: Dict[Tuple[int, int], dict] = {}
        self.iaq_fallback: Dict[int, dict] = {}
        self.webserver: dict | None = None

        self.version: str | None = None
        self.transport_hvac: str | None = None  # "GET" / "POST"
        self.transport_iaq: str | None = None   # "GET" / "POST" / None

        # Perfiles/capacidades detectadas
        self.system_profiles: Dict[int, dict] = {}          # {sid: {'profile': str, 'capabilities': [...], ...}}
        self.zone_profiles: Dict[Tuple[int,int], dict] = {} # {(sid,zid): {...}}

    # ---------------- HTTP helpers ----------------

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _post_json(self, path: str, json: dict) -> Any:
        url = f"{self._base}{path}"
        async with self.session.post(url, json=json, timeout=10) as resp:
            txt = await resp.text()
            if resp.status != 200:
                raise UpdateFailed(f"POST {path} {resp.status}: {txt}")
            try:
                return await resp.json(content_type=None)
            except Exception:
                return {"raw": txt}

    async def _get_json(self, path: str, params: dict | None = None) -> Any:
        url = f"{self._base}{path}"
        async with self.session.get(url, params=params, timeout=10) as resp:
            txt = await resp.text()
            if resp.status != 200:
                raise UpdateFailed(f"GET {path} {resp.status}: {txt}")
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
        # Algunos firmwares devuelven directamente claves sueltas:
        keys = ("ext_temp", "temp_return", "work_temp", "num_airqsensor")
        if any(k in payload for k in keys):
            return payload
        return None

    @staticmethod
    def _extract_iaq_list(payload: Any) -> list[dict]:
        """
        Devuelve lista de IAQs normalizada:
         - acepta {"data":[...]}, {"systems":[{"data":[...]}]}, lista directa;
         - normaliza 'airqsensorID' -> 'iaqsensorID'.
        """
        items: list[dict] = []

        def _norm(x: dict) -> dict | None:
            if not isinstance(x, dict):
                return None
            if "systemID" not in x:
                return None
            if "iaqsensorID" not in x and "airqsensorID" in x:
                x = {**x, "iaqsensorID": x.get("airqsensorID")}
            if "iaqsensorID" not in x:
                return None
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

    # ---------------- Detección de perfiles/capacidades ----------------

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

        # Etiquetas neutras (sin mencionar "Aidoo")
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
        """Usa system payload + zone_profiles (no self.data) para que funcione en el primer refresh."""
        sysd = self.systems.get(sid, {}) or {}
        caps: list[str] = []
        for k in ("ext_temp", "temp_return", "work_temp"):
            if k in sysd:
                caps.append(k)

        # IAQ presente (real o fallback)
        if any(k[0] == sid for k in self.iaqs.keys()) or (sid in self.iaq_fallback):
            caps.append("iaq")

        # ¿Alguna de sus zonas es de doble setpoint?
        has_double = any(
            "double_sp" in (self.zone_profiles.get((sid, zid), {}).get("capabilities") or [])
            for (s, zid) in self.zone_profiles.keys()
            if s == sid
        )

        # Etiquetas neutras a nivel sistema
        if any(k in caps for k in ("ext_temp","temp_return","work_temp")):
            profile = "Air to Water (A2W)"
        else:
            profile = "Sistema HVAC (doble setpoint)" if has_double else "Sistema HVAC"

        zone_count = sum(1 for (s,_z) in self.zone_profiles.keys() if s == sid)
        iaq_count = sum(1 for (s,_i) in (self.iaqs or {}).keys() if s == sid)
        return {
            "profile": profile,
            "capabilities": caps,
            "zone_count": zone_count,
            "iaq_count": iaq_count,
        }

    # ---------------- Ciclo de actualización ----------------

    async def _ensure_version(self) -> None:
        if self.version:
            return
        try:
            v = await self._get_json("/version")
            # Intentar varias claves típicas
            self.version = (
                (isinstance(v, dict) and (v.get("version") or v.get("lapi_version") or v.get("LAPI"))) or
                (isinstance(v, str) and v) or "desconocida"
            )
        except Exception as e:
            _LOGGER.debug("Version fetch error: %s", e)
            self.version = "desconocida"

    async def _fetch_hvac_broadcast(self) -> dict:
        """Intenta GET (1.77) y si no, POST (1.76). Devuelve payload de zonas."""
        try:
            payload = await self._get_json("/hvac", params={"systemid": 0, "zoneid": 0})
            self.transport_hvac = "GET"
            return payload
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
        """Recoge IAQ con varias rutas y guarda transport_iaq."""
        items: list[dict] = []
        self.transport_iaq = None

        try:
            p = await self._get_json("/iaq", params={"systemid": 0, "iaqsensorid": 0})
            items = self._extract_iaq_list(p)
            if items:
                self.transport_iaq = "GET"
                return items
        except Exception as e:
            _LOGGER.debug("IAQ GET broadcast failed: %s", e)

        for params in [
            {"systemID": 0, "iaqsensorID": 0},
            {"systemId": 0, "iaqSensorId": 0},
        ]:
            try:
                p = await self._get_json("/iaq", params=params)
                items = self._extract_iaq_list(p)
                if items:
                    self.transport_iaq = "GET"
                    return items
            except Exception:
                continue

        for body in [
            {"systemID": 0, "iaqsensorID": 0},
            {"systemId": 0, "iaqSensorId": 0},
        ]:
            try:
                p = await self._post_json("/iaq", body)
                items = self._extract_iaq_list(p)
                if items:
                    self.transport_iaq = "POST"
                    return items
            except Exception:
                continue

        return items

    async def _async_update_data(self) -> Dict[Tuple[int, int], dict]:
        await self._ensure_version()

        # 1) ZONAS (broadcast)
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

                # Perfiles de zona (capacidades)
                self.zone_profiles[(sid, zid)] = self._determine_zone_profile(z)

                # Fallback IAQ por si no hay endpoint /iaq
                if "aq_quality" in z or "aq_mode" in z:
                    cur = self.iaq_fallback.setdefault(sid, {})
                    if "aq_quality" in z:
                        cur["aq_quality"] = z.get("aq_quality")
                    if "aq_mode" in z:
                        cur["aq_mode"] = z.get("aq_mode")
            except Exception as e:
                _LOGGER.debug("Skipping bad zone entry %s (%s)", z, e)

        # 2) SYSTEMS (uno por sistema)
        self.systems = {}
        async def fetch_system(sid: int):
            raw = await self._fetch_hvac_system(sid)
            data = self._extract_system_data(raw or {}, sid)
            if isinstance(data, dict):
                self.systems[sid] = data

        if system_ids:
            await asyncio.gather(*[fetch_system(s) for s in system_ids])

        # 3) WEBSERVER
        try:
            ws = await self._post_json("/webserver", {})
            if isinstance(ws, dict):
                self.webserver = ws
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
            self.system_profiles[sid] = self._determine_system_profile(sid)

        return mapped

    # ---------------- API pública ----------------

    def get_zone(self, system_id: int, zone_id: int) -> dict | None:
        return self.data.get((system_id, zone_id)) if self.data else None

    def get_system(self, system_id: int) -> dict | None:
        return self.systems.get(system_id)

    def get_iaq(self, system_id: int, iaq_id: int) -> dict | None:
        return self.iaqs.get((system_id, iaq_id))

    async def async_set_zone_params(self, system_id: int, zone_id: int, **params: Any) -> dict:
        """PUT /hvac para cambiar parámetros de una zona."""
        body = {"systemID": system_id, "zoneID": zone_id}
        body.update(params)
        url = f"{self._base}/hvac"
        async with self.session.put(url, json=body, timeout=10) as resp:
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
