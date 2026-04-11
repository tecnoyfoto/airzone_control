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
INTEGRATION_DRIVER = "homeassistant"

class AirzoneCoordinator(DataUpdateCoordinator[dict[Tuple[int,int], dict]]):
    """Coordinador de datos para Airzone Local API (1.76+ → 1.78)."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        api_prefix: str | None = None,
    ) -> None:
        self._host = host.strip()
        self._port = int(port or DEFAULT_PORT)
        self._https_port = 3443
        self._prefix: str | None = api_prefix  # puede venir del config_flow
        self._prefer_https: Optional[bool] = None  # autodetección en runtime

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
        self.transport_scheme: str | None = None  # "http" o "https"

        # Control "seguir global"
        self._follow_master_enabled: set[int] = set()

        # API version y WS info
        self.version: str | None = None
        self.driver: str | None = None
        self._integration_checked = False

        # Recuperación ante lecturas vacías/intermitentes
        self._hvac_empty_reads = 0
        self._iaq_empty_reads = 0

    # ---------------- bases URL / sesión ----------------
    def _http_base(self) -> str:
        return f"http://{self._host}:{self._port}{(self._prefix or '')}"

    def _https_base(self) -> str:
        return f"https://{self._host}:{self._https_port}{(self._prefix or '')}"

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session and not self._session.closed:
            return self._session
        self._session = aiohttp.ClientSession()
        return self._session

    async def _detect_prefix(self) -> None:
        """Detecta prefijo ('', '/api/v1') probando primero el esquema preferido y, si falla, el alternativo."""
        if self._prefix is not None:
            return
        timeout = 6
        s = await self._ensure_session()

        # Orden de prueba: si ya se decidió https/http, respetarlo; si no, http primero.
        schemes = ["https", "http"] if self._prefer_https else ["http", "https"]

        for scheme in schemes:
            for pref in CANDIDATE_PREFIXES:
                base = (self._https_base() if scheme == "https" else self._http_base()).replace((self._prefix or ""), pref)
                try:
                    async with s.get(f"{base}/webserver", timeout=timeout, ssl=(False if scheme == "https" else None)) as r:
                        if r.status == 200:
                            self._prefix = pref
                            self._prefer_https = (scheme == "https")
                            self.transport_scheme = scheme
                            _LOGGER.debug("Detected API prefix via GET /webserver: %s (scheme=%s)", pref, scheme)
                            return
                except Exception:
                    pass
                try:
                    async with s.post(f"{base}/webserver", json={}, timeout=timeout, ssl=(False if scheme == "https" else None)) as r:
                        if r.status == 200:
                            self._prefix = pref
                            self._prefer_https = (scheme == "https")
                            self.transport_scheme = scheme
                            _LOGGER.debug("Detected API prefix via POST /webserver: %s (scheme=%s)", pref, scheme)
                            return
                except Exception:
                    pass
        # Si no detecta, deja _prefix tal cual (None) y que fallen las llamadas con logs útiles.

    # ---------------- helpers HTTP genéricos (GET/POST con HTTPS fallback) ----------------
    async def _request_json(
        self, method: str, path: str, *, params: dict | None = None, body: dict | None = None, timeout: int = 8
    ) -> dict | list | None:
        """
        Intenta la llamada en orden preferido (http/https) y hace fallback al alternativo.
        En https no verifica certificado (self-signed de LAPI 1.78).
        """
        await self._detect_prefix()
        s = await self._ensure_session()

        # Construir candidatos en orden
        order = ["https", "http"] if self._prefer_https else ["http", "https"]
        bases = []
        for scheme in order:
            base = self._https_base() if scheme == "https" else self._http_base()
            ssl_opt = (False if scheme == "https" else None)
            bases.append((scheme, base, ssl_opt))

        last_txt = ""
        last_status = None
        for scheme, base, ssl_opt in bases:
            url = f"{base}{path}"
            try:
                if method == "GET":
                    async with s.get(url, params=params, timeout=timeout, ssl=ssl_opt) as resp:
                        txt = await resp.text()
                        if resp.status != 200:
                            _LOGGER.debug("%s %s %s -> %s %s", method, path, params, resp.status, txt)
                            last_status, last_txt = resp.status, txt
                            continue
                        try:
                            data = await resp.json(content_type=None)
                        except Exception:
                            data = {"raw": txt}
                else:
                    async with s.request(method, url, json=(body or {}), timeout=timeout, ssl=ssl_opt) as resp:
                        txt = await resp.text()
                        if resp.status != 200:
                            _LOGGER.debug("%s %s %s -> %s %s", method, path, body, resp.status, txt)
                            last_status, last_txt = resp.status, txt
                            continue
                        try:
                            data = await resp.json(content_type=None)
                        except Exception:
                            data = {"raw": txt}

                # éxito
                self._prefer_https = (scheme == "https")
                self.transport_scheme = scheme
                return data
            except Exception as e:
                last_txt = str(e)
                continue

        if last_status:
            _LOGGER.debug("%s %s final error -> %s %s", method, path, last_status, last_txt)
        return None

    async def _get_json(self, path: str, params: dict | None = None) -> dict | list | None:
        return await self._request_json("GET", path, params=params)

    async def _post_json(self, path: str, body: dict) -> dict | list | None:
        return await self._request_json("POST", path, body=body)

    async def _put_json(self, path: str, body: dict) -> dict | list | None:
        return await self._request_json("PUT", path, body=body)

    # ---------------- Normalizadores ----------------

    @staticmethod
    def _normalize_zone(z: dict) -> dict:
        out = dict(z)

        # Unificar ventana abierta: open_window (1.78) | window_external_source (≤1.77)
        val = None
        if "open_window" in out:
            try:
                val = int(out.get("open_window")) or 0
            except Exception:
                val = 0
        elif "window_external_source" in out:
            try:
                val = int(out.get("window_external_source")) or 0
            except Exception:
                val = 0
        if val is not None:
            out["open_window"] = val
            out["window_external_source"] = val

        # Tipos numéricos más usados
        for key in (
            "systemID",
            "zoneID",
            "on",
            "mode",
            "speed",
            "speeds",
            "heatStage",
            "coldStage",
            "heatStages",
            "coldStages",
            "units",
            "master_zoneID",
            "sleep",
            "double_sp",
            "battery_low",
            "battery",
            "coverage",
            "aq_quality",
            "antifreeze",
            "slats_vertical",
            "slats_horizontal",
            "slats_vswing",
            "slats_hswing",
            "heatangle",
            "coldangle",
            "erv_mode",
        ):
            if key in out:
                try:
                    out[key] = int(out[key])
                except Exception:
                    pass

        # speed_values como lista de int única y ordenada
        if isinstance(out.get("speed_values"), list):
            try:
                sv = sorted({int(x) for x in out["speed_values"]})
                out["speed_values"] = sv
            except Exception:
                pass

        return out

    @staticmethod
    def _normalize_system(s: dict) -> dict:
        out = dict(s)
        for key in (
            "systemID",
            "system_type",
            "system_technology",
            "num_airqsensors",
            "mc_connected",
            "energy_consump",
            "energy_produced",
            "power_gen_heat",
            "consumption_ue",
            "acs_power",
            "erv_mode",
        ):
            if key in out:
                try:
                    out[key] = int(out[key])
                except Exception:
                    pass
        return out

    @staticmethod
    def _extract_zone_list(payload: Any) -> list[dict]:
        if not isinstance(payload, dict):
            return []
        data = payload.get("data")
        if isinstance(data, dict):
            data = [data]
        if isinstance(data, list):
            out: list[dict] = []
            for x in data:
                if isinstance(x, dict):
                    out.append(AirzoneCoordinator._normalize_zone(x))
            return out
        # formato por sistemas
        systems = payload.get("systems")
        items: list[dict] = []
        if isinstance(systems, list):
            for s in systems:
                dl = s.get("data")
                if isinstance(dl, list):
                    for x in dl:
                        if isinstance(x, dict):
                            items.append(AirzoneCoordinator._normalize_zone(x))
                elif isinstance(dl, dict):
                    items.append(AirzoneCoordinator._normalize_zone(dl))
        return items

    @staticmethod
    def _extract_iaq_list(payload: Any) -> list[dict]:
        items: list[dict] = []

        def _norm(x: Any) -> dict | None:
            if not isinstance(x, dict):
                return None
            if "airqsensorID" in x and "iaqsensorID" not in x:
                x["iaqsensorID"] = x.pop("airqsensorID")
            # normalizar enteros comunes
            for k in ("systemID", "iaqsensorID", "iaq_mode_vent"):
                if k in x:
                    try:
                        x[k] = int(x[k])
                    except Exception:
                        pass
            return x

        if isinstance(payload, dict):
            d = payload.get("data")
            if isinstance(d, list):
                for x in d:
                    n = _norm(x);  n and items.append(n)
            elif isinstance(d, dict):
                n = _norm(d); n and items.append(n)
            elif "systems" in payload and isinstance(payload["systems"], list):
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

    @classmethod
    def _extract_system_list(cls, payload: Any) -> list[dict]:
        if not isinstance(payload, dict):
            return []

        items: list[dict] = []
        systems = payload.get("systems")
        if not isinstance(systems, list):
            return items

        for entry in systems:
            if not isinstance(entry, dict):
                continue

            system = {k: v for k, v in entry.items() if k not in ("data", "zones")}
            sid = system.get("systemID")
            if sid is None:
                data = entry.get("data")
                if isinstance(data, list) and data:
                    sid = data[0].get("systemID")
                elif isinstance(data, dict):
                    sid = data.get("systemID")
                zones = entry.get("zones")
                if sid is None and isinstance(zones, list) and zones:
                    sid = zones[0].get("systemID")

            if sid is None:
                continue

            try:
                system["systemID"] = int(sid)
            except Exception:
                continue

            items.append(cls._normalize_system(system))

        return items

    @staticmethod
    def _derive_systems_from_zones(zones: list[dict]) -> dict[int, dict]:
        systems: dict[int, dict] = {}
        zone_system_keys = (
            "system_firmware",
            "system_type",
            "system_technology",
            "manufacturer",
            "num_airqsensors",
            "mc_connected",
            "energy_consump",
            "energy_produced",
            "power_gen_heat",
            "consumption_ue",
            "acs_power",
            "erv_mode",
        )

        for zone in zones:
            try:
                sid = int(zone.get("systemID"))
            except Exception:
                continue

            system = systems.setdefault(sid, {"systemID": sid})
            for key in zone_system_keys:
                if key in zone and key not in system:
                    system[key] = zone.get(key)

        return systems

    @staticmethod
    def _extract_value(payload: Any, keys: tuple[str, ...]) -> Any:
        if isinstance(payload, dict):
            for key in keys:
                if key in payload and payload.get(key) not in (None, ""):
                    return payload.get(key)

            data = payload.get("data")
            if isinstance(data, dict):
                value = AirzoneCoordinator._extract_value(data, keys)
                if value not in (None, ""):
                    return value

            if isinstance(data, list):
                for item in data:
                    value = AirzoneCoordinator._extract_value(item, keys)
                    if value not in (None, ""):
                        return value

        elif isinstance(payload, list):
            for item in payload:
                value = AirzoneCoordinator._extract_value(item, keys)
                if value not in (None, ""):
                    return value

        return None

    @classmethod
    def _extract_version(cls, payload: Any) -> str | None:
        value = cls._extract_value(
            payload,
            (
                "version",
                "api_ver",
                "ws_firmware",
                "firmware",
                "app_version",
                "localapi_version",
            ),
        )
        if value in (None, ""):
            return None
        return str(value)

    @classmethod
    def _extract_driver(cls, payload: Any) -> str | None:
        value = cls._extract_value(payload, ("driver",))
        if value in (None, ""):
            return None
        return str(value)

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
        elif "modes" in caps:
            profile = "Zona con modos"
        else:
            profile = "Zona básica"

        return {
            "profile": profile,
            "capabilities": caps,
        }

    def _determine_system_profile(self, system_id: int) -> dict:
        zones = self.zones_of_system(system_id)
        caps: list[str] = []
        if any("humidity" in (self._determine_zone_profile(z).get("capabilities") or []) for z in zones):
            caps.append("humidity")
        return {
            "profile": "Sistema",
            "capabilities": caps,
        }

    # ---------------- Mapa de datos ----------------

    @staticmethod
    def _map_zones(zlist: list[dict]) -> dict[tuple[int,int], dict]:
        out: dict[tuple[int,int], dict] = {}
        for z in zlist:
            try:
                sid = int(z.get("systemID"))
                zid = int(z.get("zoneID"))
                out[(sid, zid)] = z
            except Exception:
                continue
        return out

    # ---------------- API públicas de lectura ----------------

    def zones_of_system(self, system_id: int) -> list[dict]:
        return [z for (sid, _zid), z in (self.data or {}).items() if sid == int(system_id)]

    def get_zone(self, system_id: int, zone_id: int) -> dict | None:
        return (self.data or {}).get((int(system_id), int(zone_id)))

    def get_iaq(self, system_id: int, iaq_id: int) -> dict | None:
        return self.iaqs.get((int(system_id), int(iaq_id)))

    def get_system(self, system_id: int) -> dict | None:
        return self.systems.get(int(system_id))

    # --- Zona máster (heurística) ---
    def master_zone_id(self, system_id: int) -> Optional[int]:
        zones = self.zones_of_system(system_id)
        if not zones:
            return None
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
        try:
            return min(int(z.get("zoneID")) for z in zones if "zoneID" in z)
        except Exception:
            return None

    # --- Seguir modo máster ---
    def is_follow_master_enabled(self, system_id: int) -> bool:
        return int(system_id) in self._follow_master_enabled

    async def async_set_follow_master(self, system_id: int, enabled: bool) -> None:
        sid = int(system_id)
        if enabled:
            self._follow_master_enabled.add(sid)
            self.hass.async_create_task(self._enforce_follow_master(sid))
        else:
            self._follow_master_enabled.discard(sid)

    async def _enforce_follow_master(self, system_id: int) -> None:
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
        desired_mode = None
        try:
            desired_mode = int(mz.get("mode"))
        except Exception:
            pass

        tasks: list[asyncio.Task] = []
        for (s, zid), z in (self.data or {}).items():
            if s != sid:
                continue
            if zid == mzid:
                continue
            try:
                cur_on = int(z.get("on", 0))
            except Exception:
                cur_on = 0
            if cur_on != desired_on:
                tasks.append(asyncio.create_task(self.async_set_zone_params(sid, zid, on=desired_on)))
                continue
            if desired_on == 1 and desired_mode is not None:
                try:
                    cur_mode = int(z.get("mode"))
                    if cur_mode != desired_mode:
                        tasks.append(asyncio.create_task(self.async_set_zone_params(sid, zid, mode=desired_mode)))
                except Exception:
                    pass

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _known_system_ids(self) -> list[int]:
        """System IDs conocidos a partir del último estado válido."""
        ids: set[int] = set()

        for (sid, _zid) in (self.data or {}).keys():
            try:
                ids.add(int(sid))
            except Exception:
                pass

        for (sid, _iid) in (self.iaqs or {}).keys():
            try:
                ids.add(int(sid))
            except Exception:
                pass

        for sid in (self.system_profiles or {}).keys():
            try:
                ids.add(int(sid))
            except Exception:
                pass

        if not ids:
            ids.add(1)

        return sorted(ids)

    # ---------------- fetchers ----------------

    async def _fetch_hvac_all(self) -> list[dict]:
        """Lee todas las zonas de todos los sistemas (broadcast) con fallback por systemID real."""
        # 1) GET con systemid=127 (broadcast documentado) y zoneid=0
        try:
            p = await self._get_json("/hvac", params={"systemid": 127, "zoneid": 0})
            if isinstance(p, (dict, list)):
                items = self._extract_zone_list(p)
                if items:
                    self.transport_hvac = f"GET(127)"
                    return p
        except Exception as e:
            _LOGGER.debug("HVAC GET broadcast(127) failed: %s", e)

        # 2) GET con systemid=0 (algunos firmwares lo soportan)
        try:
            p = await self._get_json("/hvac", params={"systemid": 0, "zoneid": 0})
            if isinstance(p, (dict, list)):
                items = self._extract_zone_list(p)
                if items:
                    self.transport_hvac = f"GET(0)"
                    return p
        except Exception as e:
            _LOGGER.debug("HVAC GET broadcast(0) failed: %s", e)

        # 3) POST con systemID=127
        p = await self._post_json("/hvac", {"systemID": 127, "zoneID": 0})
        if isinstance(p, (dict, list)) and self._extract_zone_list(p):
            self.transport_hvac = "POST(127)"
            return p

        # 4) POST con systemID=0
        p = await self._post_json("/hvac", {"systemID": 0, "zoneID": 0})
        if isinstance(p, (dict, list)) and self._extract_zone_list(p):
            self.transport_hvac = "POST(0)"
            return p

        # 5) Fallback por systemID reales conocidos (sin tocar la lógica de control/PUT)
        combined: list[dict] = []
        seen: set[tuple[int, int]] = set()
        used_ids: list[int] = []
        for sid in self._known_system_ids():
            payload = await self._fetch_hvac_system(sid)
            items = self._extract_zone_list(payload) if isinstance(payload, (dict, list)) else []
            if not items:
                continue
            used_ids.append(sid)
            for item in items:
                try:
                    key = (int(item.get("systemID")), int(item.get("zoneID")))
                except Exception:
                    continue
                if key in seen:
                    continue
                seen.add(key)
                combined.append(item)

        if combined:
            self.transport_hvac = f"SYSTEM({','.join(str(s) for s in used_ids)})"
            return {"data": combined}

        self.transport_hvac = "EMPTY"
        return {"data": []}

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
        """Lee todos los IAQ (broadcast) con fallback por systemID real."""
        items: list[dict] = []
        self.transport_iaq = None

        # 1) GET broadcast 0 / 127
        for val in (0, 127):
            try:
                p = await self._get_json("/iaq", params={"systemid": val, "iaqsensorid": 0})
                items = self._extract_iaq_list(p)
                if items:
                    self.transport_iaq = f"GET({val})"
                    return items
            except Exception as e:
                _LOGGER.debug("IAQ GET broadcast(%s) failed: %s", val, e)

        # 2) POST broadcast 0 / 127
        for val in (0, 127):
            try:
                p = await self._post_json("/iaq", {"systemID": val, "iaqsensorID": 0})
                items = self._extract_iaq_list(p)
                if items:
                    self.transport_iaq = f"POST({val})"
                    return items
            except Exception as e:
                _LOGGER.debug("IAQ POST broadcast(%s) failed: %s", val, e)

        # 3) Fallback por systemID reales conocidos
        combined: list[dict] = []
        seen: set[tuple[int, int]] = set()
        used_ids: list[int] = []
        for sid in self._known_system_ids():
            sys_items = await self._fetch_iaq_system(sid)
            if not sys_items:
                continue
            used_ids.append(sid)
            for item in sys_items:
                try:
                    key = (int(item.get("systemID")), int(item.get("iaqsensorID")))
                except Exception:
                    continue
                if key in seen:
                    continue
                seen.add(key)
                combined.append(item)

        if combined:
            self.transport_iaq = f"SYSTEM({','.join(str(s) for s in used_ids)})"
            return combined

        self.transport_iaq = "EMPTY"
        return []

    async def _fetch_iaq_system(self, sid: int) -> list[dict]:
        try:
            p = await self._get_json("/iaq", params={"systemid": sid, "iaqsensorid": 0})
            if isinstance(p, (dict, list)):
                return self._extract_iaq_list(p)
        except Exception:
            pass
        try:
            p = await self._post_json("/iaq", {"systemID": sid, "iaqsensorID": 0})
            return self._extract_iaq_list(p)
        except Exception as e:
            _LOGGER.debug("IAQ system %s fetch failed: %s", sid, e)
            return []

    async def _ensure_integration_driver(self) -> None:
        if self._integration_checked:
            return

        self._integration_checked = True

        try:
            info = await self._post_json("/integration", {})
        except Exception as err:
            _LOGGER.debug("Integration driver check failed: %s", err)
            return

        current = self._extract_driver(info)
        if current:
            self.driver = current

        if current and current.lower() not in ("integrator", INTEGRATION_DRIVER):
            _LOGGER.info("Leaving existing Airzone integration driver unchanged: %s", current)
            return

        if current and current.lower() == INTEGRATION_DRIVER:
            return

        try:
            result = await self._put_json("/integration", {"driver": INTEGRATION_DRIVER})
            updated = self._extract_driver(result)
            if updated:
                self.driver = updated
        except Exception as err:
            _LOGGER.debug("Integration driver registration failed: %s", err)

    # ---------------- update ----------------

    async def _async_update_data(self) -> dict[Tuple[int,int], dict]:
        # 1) HVAC (todas las zonas)
        try:
            hvac_payload = await self._fetch_hvac_all()
        except Exception as e:
            raise UpdateFailed(f"HVAC fetch error: {e}") from e

        extracted_zones = self._extract_zone_list(hvac_payload) or []
        mapped = self._map_zones(extracted_zones)
        if mapped:
            self.data = mapped
            self._hvac_empty_reads = 0
        else:
            self._hvac_empty_reads += 1
            if self.data:
                mapped = self.data
                _LOGGER.warning(
                    "HVAC update came back empty; keeping last valid state (empty_reads=%s, transport=%s)",
                    self._hvac_empty_reads,
                    self.transport_hvac,
                )
            else:
                raise UpdateFailed("HVAC update returned no valid zones")

        extracted_systems = self._extract_system_list(hvac_payload)
        systems: dict[int, dict] = {
            int(item["systemID"]): item for item in extracted_systems if "systemID" in item
        }
        derived_systems = self._derive_systems_from_zones(extracted_zones)
        for sid, data in derived_systems.items():
            base = systems.setdefault(sid, {"systemID": sid})
            for key, value in data.items():
                base.setdefault(key, value)
        for sid in {sid for (sid, _zid) in mapped.keys()}:
            systems.setdefault(int(sid), {"systemID": int(sid)})
        self.systems = systems

        # 2) Webserver info (GET con fallback a POST)
        try:
            ws = await self._get_json("/webserver")
            if not isinstance(ws, dict):
                ws = await self._post_json("/webserver", {})
            if isinstance(ws, dict):
                self.webserver = ws
        except Exception as e:
            _LOGGER.debug("Webserver fetch error: %s", e)

        try:
            version_payload = await self._post_json("/version", {})
            detected_version = self._extract_version(version_payload)
            if detected_version:
                self.version = detected_version
        except Exception as e:
            _LOGGER.debug("Version fetch error: %s", e)

        if not self.version and isinstance(self.webserver, dict):
            detected_version = self._extract_version(self.webserver)
            if detected_version:
                self.version = detected_version

        await self._ensure_integration_driver()

        # 3) IAQ
        iaq_items = await self._fetch_iaq_all()
        new_iaqs: dict[tuple[int, int], dict] = {}
        for item in iaq_items:
            try:
                sid = int(item.get("systemID"))
                iid = int(item.get("iaqsensorID"))
                new_iaqs[(sid, iid)] = item
            except Exception:
                continue

        if new_iaqs:
            self.iaqs = new_iaqs
            self._iaq_empty_reads = 0
        elif self.iaqs:
            self._iaq_empty_reads += 1
            _LOGGER.warning(
                "IAQ update came back empty; keeping last valid IAQ state (empty_reads=%s, transport=%s)",
                self._iaq_empty_reads,
                self.transport_iaq,
            )
        else:
            self.iaqs = {}

        # 4) Perfiles de sistema
        system_ids = sorted({sid for (sid, _z) in mapped.keys()})
        self.system_profiles = {}
        for sid in system_ids:
            prof = self._determine_system_profile(sid)
            prof["zone_count"] = len([1 for (s, _z) in mapped.keys() if s == sid])
            prof["iaq_count"] = len([1 for (s, _i) in self.iaqs.keys() if s == sid]) or (1 if sid in self.iaq_fallback else 0)
            self.system_profiles[sid] = prof

        # 5) Enforce follow-master en segundo plano
        for sid in list(self._follow_master_enabled):
            self.hass.async_create_task(self._enforce_follow_master(sid))

        return mapped

    # ---------------- setters ----------------

    async def async_set_zone_params(self, system_id: int, zone_id: int, *, request_refresh: bool = True, **kwargs) -> dict | None:
        """PUT /hvac con refresco inmediato (no bloqueante)."""
        body = {"systemID": int(system_id), "zoneID": int(zone_id)}
        body.update(kwargs)
        await self._detect_prefix()
        s = await self._ensure_session()

        # Intentar PUT por esquema preferido y fallback
        for scheme in (["https","http"] if self._prefer_https else ["http","https"]):
            base = self._https_base() if scheme == "https" else self._http_base()
            url = f"{base}/hvac"
            try:
                async with s.put(url, json=body, timeout=6, ssl=(False if scheme == "https" else None)) as resp:
                    txt = await resp.text()
                    if resp.status != 200:
                        _LOGGER.error("PUT /hvac %s -> %s %s", body, resp.status, txt)
                        continue
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = {"raw": txt}
                    # refresco sin bloquear
                    if request_refresh:
                        self.hass.async_create_task(self.async_request_refresh())
                    self._prefer_https = (scheme == "https")
                    self.transport_scheme = scheme
                    return data
            except Exception as e:
                _LOGGER.debug("PUT /hvac %s failed on %s: %s", body, scheme, e)
                continue

        raise UpdateFailed("PUT /hvac failed on both http/https")

    async def async_set_iaq_params(self, system_id: int, iaq_id: int, **kwargs) -> dict | None:
        """PUT /iaq con refresco inmediato (no bloqueante)."""
        body = {"systemID": int(system_id), "iaqsensorID": int(iaq_id)}
        body.update(kwargs)
        await self._detect_prefix()
        s = await self._ensure_session()

        for scheme in (["https","http"] if self._prefer_https else ["http","https"]):
            base = self._https_base() if scheme == "https" else self._http_base()
            url = f"{base}/iaq"
            try:
                async with s.put(url, json=body, timeout=6, ssl=(False if scheme == "https" else None)) as resp:
                    txt = await resp.text()
                    if resp.status != 200:
                        _LOGGER.error("PUT /iaq %s -> %s %s", body, resp.status, txt)
                        continue
                    try:
                        data = await resp.json(content_type=None)
                    except Exception:
                        data = {"raw": txt}
                    self.hass.async_create_task(self.async_request_refresh())
                    self._prefer_https = (scheme == "https")
                    self.transport_scheme = scheme
                    return data
            except Exception as e:
                _LOGGER.debug("PUT /iaq %s failed on %s: %s", body, scheme, e)
                continue

        raise UpdateFailed("PUT /iaq failed on both http/https")

    async def async_close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
