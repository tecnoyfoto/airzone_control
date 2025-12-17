from __future__ import annotations

from typing import Any
import json
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_HOST,
    DEFAULT_PORT,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_GROUPS,
    DEFAULT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# Rutas candidatas de la Local API
CANDIDATE_PREFIXES: list[str] = ["", "/api/v1", "/airzone/local/api/v1", "/lapi/v1"]

# Máximo de grupos configurables vía UI "bonita"
MAX_GROUP_SLOTS = 8


def _normalize_prefix(prefix: str | None) -> str:
    """Normaliza prefijos para componer URLs.

    - Asegura que empiece por '/' (si no está vacío)
    - Elimina '/' final
    """
    pref = (prefix or "").strip()
    if not pref:
        return ""
    if not pref.startswith("/"):
        pref = "/" + pref
    return pref.rstrip("/")


# ─────────────────────────────────────────
#  Utilidades de red
# ─────────────────────────────────────────


async def _probe_one(hass: HomeAssistant, host: str, port: int, prefix: str) -> bool:
    """Devuelve True si el Airzone responde en esta combinación host/port/prefix."""
    pref = _normalize_prefix(prefix)
    base = f"http://{host}:{port}{pref}"
    timeout = 6

    try:
        async with aiohttp.ClientSession() as session:
            # /webserver (GET y POST)
            try:
                with async_timeout.timeout(timeout):
                    async with session.get(f"{base}/webserver", timeout=timeout) as r:
                        if r.status == 200:
                            return True
            except Exception:
                pass

            try:
                with async_timeout.timeout(timeout):
                    async with session.post(f"{base}/webserver", json={}, timeout=timeout) as r:
                        if r.status == 200:
                            return True
            except Exception:
                pass

    except Exception:
        return False

    return False


async def _autodetect_prefix(hass: HomeAssistant, host: str, port: int) -> str | None:
    """Devuelve el primer prefijo que responde o None si ninguno responde."""
    for pref in CANDIDATE_PREFIXES:
        ok = await _probe_one(hass, host, port, pref)
        if ok:
            return _normalize_prefix(pref)
    return None


def _slugify_id(name: str) -> str:
    """Crear un id simple a partir del nombre."""
    slug = name.strip().lower()
    slug = slug.replace(" ", "_")
    slug = "".join(ch for ch in slug if ch.isalnum() or ch in ("_", "-"))
    while "__" in slug:
        slug = slug.replace("__", "_")
    slug = slug.strip("_") or "group"
    return slug


def _parse_zones_from_response(payload: Any) -> dict[str, str]:
    """Construye un mapa 'systemID/zoneID' -> 'Nombre (systemID/zoneID)'.

    Soporta respuestas tipo:
    - {"data": [ ... ]}
    - {"systems": [ {"data": [ ... ]}, ... ]}
    - [ ... ] (lista directa)
    """
    zones: dict[str, str] = {}

    def _pick(d: dict[str, Any], *keys: str) -> Any:
        for k in keys:
            if k in d:
                return d.get(k)
        # fallback case-insensitive
        lower = {str(k).lower(): v for k, v in d.items()}
        for k in keys:
            lk = str(k).lower()
            if lk in lower:
                return lower[lk]
        return None

    def _add_from_list(items: list[Any]) -> None:
        for item in items:
            if not isinstance(item, dict):
                continue
            system_id = _pick(item, "systemID", "systemId", "systemid")
            zone_id = _pick(item, "zoneID", "zoneId", "zoneid")
            if system_id is None or zone_id is None:
                continue
            key = f"{system_id}/{zone_id}"
            name = _pick(item, "name", "zoneName", "zonename") or f"Zona {zone_id}"
            zones[key] = f"{name} ({key})"

    if isinstance(payload, list):
        _add_from_list(payload)
        return zones

    if not isinstance(payload, dict):
        return zones

    data = payload.get("data")
    if isinstance(data, list):
        _add_from_list(data)

    systems = payload.get("systems")
    if isinstance(systems, list):
        for sys_item in systems:
            if not isinstance(sys_item, dict):
                continue
            sys_data = sys_item.get("data")
            if isinstance(sys_data, list):
                _add_from_list(sys_data)
            # Algunos firmwares podrían devolver "zones"
            sys_zones = sys_item.get("zones")
            if isinstance(sys_zones, list):
                _add_from_list(sys_zones)

    return zones


# ─────────────────────────────────────────
#  Config flow principal
# ─────────────────────────────────────────


class AirzoneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flujo de configuración para la integración Airzone Control."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._prefix: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Crear el options flow (botón Configurar)."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = (user_input.get(CONF_HOST) or "").strip()
            port = int(user_input.get(CONF_PORT) or DEFAULT_PORT)

            if not host:
                errors["base"] = "no_host"
            else:
                prefix = await _autodetect_prefix(self.hass, host, port)
                if not prefix:
                    # No hemos podido autodetectar → pedir prefijo manual
                    self._host = host
                    self._port = port
                    return await self.async_step_prefix()

                self._host = host
                self._port = port
                self._prefix = prefix

                unique = f"{host}:{port}"
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_HOST: host,
                    CONF_PORT: port,
                    "api_prefix": prefix,
                }
                options = {
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_GROUPS: [],
                }

                return self.async_create_entry(
                    title=f"Airzone ({host})",
                    data=data,
                    options=options,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    int, vol.Range(min=1, max=65535)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_prefix(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Paso para seleccionar un prefijo si la autodetección falla."""
        errors: dict[str, str] = {}

        if user_input is not None:
            pref = user_input.get("api_prefix") or ""
            ok = await _probe_one(self.hass, self._host, self._port, pref)
            if not ok:
                errors["base"] = "cannot_connect"
            else:
                self._prefix = _normalize_prefix(pref)
                unique = f"{self._host}:{self._port}"
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    "api_prefix": self._prefix,
                }
                options = {
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                    CONF_GROUPS: [],
                }
                return self.async_create_entry(
                    title=f"Airzone ({self._host})",
                    data=data,
                    options=options,
                )

        schema = vol.Schema(
            {
                vol.Required(
                    "api_prefix",
                    default=CANDIDATE_PREFIXES[0],
                ): vol.In(CANDIDATE_PREFIXES),
            }
        )

        return self.async_show_form(
            step_id="prefix",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Soporte básico para YAML: redirigimos al flujo normal."""
        return await self.async_step_user(user_input)


# ─────────────────────────────────────────
#  Options flow (scan_interval + grupos)
# ─────────────────────────────────────────


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow para configurar scan_interval y grupos de zonas."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._zones_map: dict[str, str] | None = None

    async def _fetch_zones_once(self, host: str, port: int, prefix: str) -> dict[str, str]:
        """Intenta obtener zonas desde un prefijo concreto."""
        pref = _normalize_prefix(prefix)
        base = f"http://{host}:{port}{pref}"
        url = f"{base}/hvac"

        session = async_get_clientsession(self.hass)

        attempts: list[tuple[str, dict[str, Any] | None, dict[str, Any] | None]] = [
            # POST (lo más habitual en la Local API)
            ("POST", None, {"systemID": 0, "zoneID": 0}),
            ("POST", None, {"systemId": 0, "zoneId": 0}),
            # GET fallback (por compatibilidad)
            ("GET", {"systemid": 0, "zoneid": 0}, None),
            ("GET", {"systemID": 0, "zoneID": 0}, None),
        ]

        for method, params, body in attempts:
            try:
                with async_timeout.timeout(6):
                    async with session.request(
                        method,
                        url,
                        params=params,
                        json=body,
                    ) as resp:
                        if resp.status != 200:
                            continue
                        payload = await resp.json(content_type=None)
                        zones = _parse_zones_from_response(payload)
                        if zones:
                            return zones
            except Exception:
                continue

        return {}

    async def _load_zones_map(self) -> dict[str, str]:
        """Obtiene el mapa de zonas 'id' -> 'nombre (id)' desde la Local API."""
        if self._zones_map is not None:
            return self._zones_map

        host = self._entry.data.get(CONF_HOST, DEFAULT_HOST)
        port = self._entry.data.get(CONF_PORT, DEFAULT_PORT)
        prefix = self._entry.data.get("api_prefix")

        zones: dict[str, str] = {}

        # 1) Intento con el prefijo guardado (si existe)
        if prefix is not None:
            zones = await self._fetch_zones_once(host, port, prefix)

        # 2) Si no funciona o no hay prefijo, autodetectar y reintentar
        if not zones:
            detected = await _autodetect_prefix(self.hass, host, port)
            if detected is not None:
                zones = await self._fetch_zones_once(host, port, detected)

                # Persistir el prefijo detectado si falta o es distinto
                current = _normalize_prefix(prefix)
                if detected != current:
                    try:
                        self.hass.config_entries.async_update_entry(
                            self._entry,
                            data={**self._entry.data, "api_prefix": detected},
                        )
                    except Exception:
                        # No es crítico: solo afecta a mostrar la lista de zonas en opciones
                        pass

        if not zones:
            _LOGGER.debug(
                "No se pudo cargar la lista de zonas desde la Local API (host=%s port=%s prefix=%s)",
                host,
                port,
                prefix,
            )

        self._zones_map = zones
        return zones

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        current_scan = self._entry.options.get(
            CONF_SCAN_INTERVAL,
            DEFAULT_SCAN_INTERVAL,
        )
        current_groups = self._entry.options.get(CONF_GROUPS, []) or []

        zones_map = await self._load_zones_map()

        if user_input is not None:
            # --- 1) scan_interval ---
            scan_val = user_input.get(CONF_SCAN_INTERVAL, current_scan)
            try:
                new_scan = int(scan_val)
                if new_scan < 2 or new_scan > 300:
                    errors["scan_interval"] = "invalid_scan_interval"
            except Exception:
                errors["scan_interval"] = "invalid_scan_interval"

            # --- 2) grupos ---
            groups: list[dict[str, Any]] = []

            raw_json = (user_input.get("groups_json") or "").strip()
            if raw_json:
                # Modo avanzado: JSON manda
                try:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, list):
                        groups = [g for g in parsed if isinstance(g, dict)]
                    else:
                        errors["groups_json"] = "invalid_json"
                except Exception:
                    errors["groups_json"] = "invalid_json"
            else:
                # Modo "fácil": slots de grupos
                seen_ids: set[str] = set()
                for idx in range(1, MAX_GROUP_SLOTS + 1):
                    name_key = f"group_{idx}_name"
                    zones_key = f"group_{idx}_zones"

                    name = (user_input.get(name_key) or "").strip()
                    zones_sel = user_input.get(zones_key) or []

                    if not name or not zones_sel:
                        continue

                    gid = _slugify_id(name)
                    # Evitar IDs duplicados
                    base_gid = gid
                    suffix = 2
                    while gid in seen_ids:
                        gid = f"{base_gid}_{suffix}"
                        suffix += 1

                    seen_ids.add(gid)

                    groups.append(
                        {
                            "id": gid,
                            "name": name,
                            "zones": [str(z) for z in zones_sel],
                        }
                    )

            if not errors:
                options = dict(self._entry.options)
                options[CONF_SCAN_INTERVAL] = new_scan
                options[CONF_GROUPS] = groups

                return self.async_create_entry(title="", data=options)

        # Prefill slots desde grupos actuales (solo primeros MAX_GROUP_SLOTS)
        slot_names: dict[int, str] = {}
        slot_zones: dict[int, list[str]] = {}

        for idx, grp in enumerate(current_groups[:MAX_GROUP_SLOTS], start=1):
            if not isinstance(grp, dict):
                continue
            slot_names[idx] = grp.get("name") or grp.get("id") or f"Grupo {idx}"
            z = grp.get("zones") or []
            if isinstance(z, list):
                slot_zones[idx] = [str(v) for v in z]

        # JSON “raw” por defecto (solo cuando conviene):
        # - Si no podemos cargar zonas (no hay UI bonita), o
        # - Si hay más grupos que slots (evitamos pérdidas al guardar).
        groups_default_json = ""
        if (not zones_map) or (len(current_groups) > MAX_GROUP_SLOTS):
            try:
                groups_default_json = json.dumps(
                    current_groups,
                    ensure_ascii=False,
                    indent=2,
                )
            except Exception:
                groups_default_json = "[]"

        schema_dict: dict[Any, Any] = {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=current_scan,
            ): vol.All(int, vol.Range(min=2, max=300)),
        }

        # Solo mostramos slots bonitos si tenemos lista de zonas
        if zones_map:
            for idx in range(1, MAX_GROUP_SLOTS + 1):
                name_default = slot_names.get(idx, "")
                zones_default = slot_zones.get(idx, [])

                schema_dict[
                    vol.Optional(
                        f"group_{idx}_name",
                        default=name_default,
                    )
                ] = str
                schema_dict[
                    vol.Optional(
                        f"group_{idx}_zones",
                        default=zones_default,
                    )
                ] = cv.multi_select(zones_map)

        # Campo avanzado JSON (opcional)
        schema_dict[
            vol.Optional(
                "groups_json",
                default=groups_default_json,
            )
        ] = str

        schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
