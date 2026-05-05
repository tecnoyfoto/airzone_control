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
    CLOUD_CATEGORY_LABELS,
    CLOUD_CATEGORY_CLIMATE_ZONES,
    CLOUD_CATEGORY_ENERGY,
    CLOUD_CATEGORY_IAQ,
    CLOUD_PROFILE_COMPLEMENT_LOCAL,
    CLOUD_PROFILE_CUSTOM,
    CLOUD_PROFILE_FULL,
    CLOUD_PROFILE_LABELS,
    CONNECTION_TYPE_CLOUD,
    CONNECTION_TYPE_LOCAL,
    CONF_CLOUD_EXCLUDE_IAQ_NAMES,
    CONF_CLOUD_INCLUDE_BOUND_IAQS,
    CONF_CLOUD_INCLUDE_CATEGORIES,
    CONF_CLOUD_INCLUDE_DEVICE_IDS,
    CONF_CLOUD_PROFILE,
    CONF_CONNECTION_TYPE,
    CONF_EMAIL,
    CONF_GROUPS,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USER_ID,
    DEFAULT_CLOUD_BASE_URL,
    DEFAULT_CLOUD_EXCLUDE_IAQ_NAMES,
    DEFAULT_CLOUD_INCLUDE_BOUND_IAQS,
    DEFAULT_CLOUD_INCLUDE_CATEGORIES,
    DEFAULT_CLOUD_INCLUDE_DEVICE_IDS,
    DEFAULT_CLOUD_SCAN_INTERVAL,
    DEFAULT_CLOUD_PROFILE,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import AirzoneCoordinator
from .coordinator_cloud import CloudApiError, async_cloud_login

_LOGGER = logging.getLogger(__name__)

# Rutas candidatas de la Local API
CANDIDATE_PREFIXES: list[str] = ["", "/api/v1", "/airzone/local/api/v1", "/lapi/v1"]

# Máximo de grupos configurables vía UI "bonita"
MAX_GROUP_SLOTS = 8

COMPLEMENT_LOCAL_CLOUD_CATEGORIES = [
    CLOUD_CATEGORY_ENERGY,
    CLOUD_CATEGORY_IAQ,
]


def _normalize_prefix(prefix: str | None) -> str:
    """Normaliza prefijos para componer URLs."""
    pref = (prefix or "").strip()
    if not pref:
        return ""
    if not pref.startswith("/"):
        pref = "/" + pref
    return pref.rstrip("/")


async def _probe_one(hass: HomeAssistant, host: str, port: int, prefix: str) -> bool:
    """Devuelve True si el Airzone responde en esta combinación host/port/prefix."""
    pref = _normalize_prefix(prefix)
    base = f"http://{host}:{port}{pref}"
    timeout = 6

    try:
        async with aiohttp.ClientSession() as session:
            try:
                with async_timeout.timeout(timeout):
                    async with session.get(f"{base}/webserver", timeout=timeout) as response:
                        if response.status == 200:
                            return True
            except Exception:
                pass

            try:
                with async_timeout.timeout(timeout):
                    async with session.post(f"{base}/webserver", json={}, timeout=timeout) as response:
                        if response.status == 200:
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


async def _validate_cloud_credentials(
    hass: HomeAssistant,
    email: str,
    password: str,
) -> dict[str, Any]:
    """Valida las credenciales Cloud contra la API oficial."""
    session = async_get_clientsession(hass)
    return await async_cloud_login(session, email, password)


def _cloud_device_label(device: dict[str, Any], group_name: str | None = None) -> str:
    name = str(device.get("name") or "").strip() or str(device.get("type") or "Cloud device")
    device_type = str(device.get("type") or "unknown")
    meta = device.get("meta") if isinstance(device.get("meta"), dict) else {}
    parts = [name, device_type]
    if group_name:
        parts.append(str(group_name))
    system_number = meta.get("system_number")
    zone_number = meta.get("zone_number")
    if system_number not in (None, "") or zone_number not in (None, ""):
        parts.append(f"S{system_number or '-'} Z{zone_number or '-'}")
    return " - ".join(parts)


def _cloud_profile_categories(profile: str, selected_categories: Any) -> list[str]:
    if profile == CLOUD_PROFILE_FULL:
        return list(DEFAULT_CLOUD_INCLUDE_CATEGORIES)
    if profile == CLOUD_PROFILE_COMPLEMENT_LOCAL:
        return list(COMPLEMENT_LOCAL_CLOUD_CATEGORIES)
    return list(selected_categories or DEFAULT_CLOUD_INCLUDE_CATEGORIES)


def _cloud_profile_needs_device_selection(profile: str) -> bool:
    return profile in {CLOUD_PROFILE_COMPLEMENT_LOCAL, CLOUD_PROFILE_CUSTOM}


def _infer_cloud_profile(options: dict[str, Any], data: dict[str, Any]) -> str:
    profile = options.get(CONF_CLOUD_PROFILE, data.get(CONF_CLOUD_PROFILE))
    if profile in CLOUD_PROFILE_LABELS:
        return str(profile)

    categories = list(options.get(CONF_CLOUD_INCLUDE_CATEGORIES, data.get(CONF_CLOUD_INCLUDE_CATEGORIES, DEFAULT_CLOUD_INCLUDE_CATEGORIES)) or [])
    device_ids = list(options.get(CONF_CLOUD_INCLUDE_DEVICE_IDS, data.get(CONF_CLOUD_INCLUDE_DEVICE_IDS, DEFAULT_CLOUD_INCLUDE_DEVICE_IDS)) or [])
    if set(categories) == set(DEFAULT_CLOUD_INCLUDE_CATEGORIES) and not device_ids:
        return CLOUD_PROFILE_FULL
    if set(categories) == set(COMPLEMENT_LOCAL_CLOUD_CATEGORIES):
        return CLOUD_PROFILE_COMPLEMENT_LOCAL
    return CLOUD_PROFILE_CUSTOM


async def _fetch_cloud_device_options(
    hass: HomeAssistant,
    email: str,
    password: str,
) -> dict[str, str]:
    """Return selectable Airzone Cloud devices as device_id -> label."""
    session = async_get_clientsession(hass)
    payload = await async_cloud_login(session, email, password)
    token = payload.get("token")
    if not token:
        return {}

    base_url = DEFAULT_CLOUD_BASE_URL.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    options: dict[str, str] = {}

    async with session.get(f"{base_url}/installations", params={"items": 10, "page": 0}, headers=headers, timeout=15) as response:
        if response.status >= 400:
            return {}
        installations_payload = await response.json(content_type=None)

    installations = []
    if isinstance(installations_payload, dict):
        installations = [item for item in installations_payload.get("installations", []) if isinstance(item, dict)]

    for installation in installations:
        installation_id = installation.get("installation_id")
        if not installation_id:
            continue
        async with session.get(f"{base_url}/installations/{installation_id}", headers=headers, timeout=15) as response:
            if response.status >= 400:
                continue
            detail = await response.json(content_type=None)
        if not isinstance(detail, dict):
            continue
        for group in detail.get("groups", []) or []:
            if not isinstance(group, dict):
                continue
            group_name = group.get("name")
            for device in group.get("devices", []) or []:
                if not isinstance(device, dict):
                    continue
                device_id = device.get("device_id")
                if not device_id:
                    continue
                options[str(device_id)] = _cloud_device_label(device, group_name)

    return dict(sorted(options.items(), key=lambda item: item[1].casefold()))


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
    """Construye un mapa 'systemID/zoneID' -> 'Nombre (systemID/zoneID)'."""
    zones: dict[str, str] = {}

    def _pick(dct: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in dct:
                return dct.get(key)
        lower = {str(key).lower(): value for key, value in dct.items()}
        for key in keys:
            lookup = str(key).lower()
            if lookup in lower:
                return lower[lookup]
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
            sys_zones = sys_item.get("zones")
            if isinstance(sys_zones, list):
                _add_from_list(sys_zones)

    return zones


class AirzoneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flujo de configuración para la integración Airzone Control."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._prefix: str | None = None
        self._email: str = ""
        self._cloud_data: dict[str, Any] = {}
        self._cloud_options: dict[str, Any] = {}
        self._cloud_device_options: dict[str, str] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Crear el options flow (botón Configurar)."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            if user_input.get(CONF_CONNECTION_TYPE) == CONNECTION_TYPE_CLOUD:
                return await self.async_step_cloud()
            return await self.async_step_local()

        schema = vol.Schema(
            {
                vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPE_LOCAL): vol.In(
                    {
                        CONNECTION_TYPE_LOCAL: "Local API",
                        CONNECTION_TYPE_CLOUD: "Cloud API",
                    }
                )
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors={})

    async def async_step_local(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = (user_input.get(CONF_HOST) or "").strip()
            port = int(user_input.get(CONF_PORT) or DEFAULT_PORT)

            if not host:
                errors["base"] = "no_host"
            else:
                prefix = await _autodetect_prefix(self.hass, host, port)
                if not prefix:
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
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
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
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
            }
        )
        return self.async_show_form(step_id="local", data_schema=schema, errors=errors)

    async def async_step_cloud(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = (user_input.get(CONF_EMAIL) or "").strip().lower()
            self._email = email
            password = user_input.get(CONF_PASSWORD) or ""
            cloud_profile = str(user_input.get(CONF_CLOUD_PROFILE) or DEFAULT_CLOUD_PROFILE)

            if not email:
                errors["base"] = "no_email"
            elif not password:
                errors["base"] = "no_password"
            else:
                try:
                    payload = await _validate_cloud_credentials(self.hass, email, password)
                except CloudApiError as err:
                    if err.error_id == "userNotConfirmed":
                        errors["base"] = "user_not_confirmed"
                    elif err.error_id in {"userNotExist", "badParams", "auth_error"}:
                        errors["base"] = "invalid_auth"
                    else:
                        errors["base"] = "cannot_connect"
                except (aiohttp.ClientError, TimeoutError):
                    errors["base"] = "cannot_connect"
                except Exception:
                    _LOGGER.exception("Unexpected Airzone Cloud authentication error")
                    errors["base"] = "cannot_connect"
                else:
                    user_id = str(payload.get("_id") or payload.get("user_id") or email)
                    await self.async_set_unique_id(f"cloud:{user_id}")
                    self._abort_if_unique_id_configured()

                    data = {
                        CONF_CONNECTION_TYPE: CONNECTION_TYPE_CLOUD,
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_USER_ID: user_id,
                    }
                    options = {
                        CONF_SCAN_INTERVAL: DEFAULT_CLOUD_SCAN_INTERVAL,
                        CONF_GROUPS: [],
                        CONF_CLOUD_PROFILE: cloud_profile,
                        CONF_CLOUD_INCLUDE_CATEGORIES: _cloud_profile_categories(
                            cloud_profile,
                            user_input.get(CONF_CLOUD_INCLUDE_CATEGORIES),
                        ),
                        CONF_CLOUD_INCLUDE_BOUND_IAQS: bool(
                            user_input.get(
                                CONF_CLOUD_INCLUDE_BOUND_IAQS,
                                DEFAULT_CLOUD_INCLUDE_BOUND_IAQS,
                            )
                        ),
                        CONF_CLOUD_EXCLUDE_IAQ_NAMES: (
                            user_input.get(CONF_CLOUD_EXCLUDE_IAQ_NAMES)
                            or DEFAULT_CLOUD_EXCLUDE_IAQ_NAMES
                        ).strip(),
                    }
                    self._cloud_data = data
                    self._cloud_options = options
                    try:
                        self._cloud_device_options = await _fetch_cloud_device_options(self.hass, email, password)
                    except Exception:
                        _LOGGER.exception("Could not fetch Airzone Cloud device list during setup")
                        self._cloud_device_options = {}
                    if self._cloud_device_options and _cloud_profile_needs_device_selection(cloud_profile):
                        return await self.async_step_cloud_devices()
                    return self.async_create_entry(title=f"Airzone Cloud ({email})", data=data, options=options)

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=self._email): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(
                    CONF_CLOUD_PROFILE,
                    default=DEFAULT_CLOUD_PROFILE,
                ): vol.In(CLOUD_PROFILE_LABELS),
                vol.Optional(
                    CONF_CLOUD_INCLUDE_CATEGORIES,
                    default=DEFAULT_CLOUD_INCLUDE_CATEGORIES,
                ): cv.multi_select(CLOUD_CATEGORY_LABELS),
                vol.Optional(
                    CONF_CLOUD_INCLUDE_BOUND_IAQS,
                    default=DEFAULT_CLOUD_INCLUDE_BOUND_IAQS,
                ): cv.boolean,
                vol.Optional(
                    CONF_CLOUD_EXCLUDE_IAQ_NAMES,
                    default=DEFAULT_CLOUD_EXCLUDE_IAQ_NAMES,
                ): str,
            }
        )
        return self.async_show_form(step_id="cloud", data_schema=schema, errors=errors)

    async def async_step_cloud_devices(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Allow selecting which Cloud devices this entry should expose."""
        if user_input is not None:
            selected = list(user_input.get(CONF_CLOUD_INCLUDE_DEVICE_IDS) or [])
            options = dict(self._cloud_options)
            options[CONF_CLOUD_INCLUDE_DEVICE_IDS] = selected
            return self.async_create_entry(
                title=f"Airzone Cloud ({self._cloud_data.get(CONF_EMAIL)})",
                data=self._cloud_data,
                options=options,
            )

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CLOUD_INCLUDE_DEVICE_IDS,
                    default=[],
                ): cv.multi_select(self._cloud_device_options),
            }
        )
        return self.async_show_form(step_id="cloud_devices", data_schema=schema, errors={})

    async def async_step_prefix(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Paso para seleccionar un prefijo si la autodetección local falla."""
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
                    CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
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
                vol.Required("api_prefix", default=CANDIDATE_PREFIXES[0]): vol.In(CANDIDATE_PREFIXES),
            }
        )
        return self.async_show_form(step_id="prefix", data_schema=schema, errors=errors)

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Soporte básico para YAML legado: se trata siempre como Local API."""
        return await self.async_step_local(user_input)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow para configurar scan_interval y grupos de zonas."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._zones_map: dict[str, str] | None = None
        self._cloud_device_options: dict[str, str] | None = None

    def _zones_from_loaded_coordinator(self) -> dict[str, str]:
        data = self.hass.data.get(DOMAIN, {})
        if not isinstance(data, dict):
            return {}

        bundle = data.get(self._entry.entry_id)
        if not isinstance(bundle, dict):
            return {}

        coord = bundle.get("coordinator")
        if not isinstance(coord, AirzoneCoordinator):
            return {}

        zones: dict[str, str] = {}
        for (sid, zid), zone in (coord.data or {}).items():
            try:
                system_id = int(sid)
                zone_id = int(zid)
            except Exception:
                continue
            if zone_id <= 0:
                continue
            key = f"{system_id}/{zone_id}"
            name = zone.get("name") or f"Zona {zone_id}"
            zones[key] = f"{name} ({key})"
        return zones

    async def _fetch_zones_once(self, host: str, port: int, prefix: str) -> dict[str, str]:
        """Intenta obtener zonas desde un prefijo concreto."""
        pref = _normalize_prefix(prefix)
        base = f"http://{host}:{port}{pref}"
        url = f"{base}/hvac"

        session = async_get_clientsession(self.hass)
        attempts: list[tuple[str, dict[str, Any] | None, dict[str, Any] | None]] = [
            ("POST", None, {"systemID": 0, "zoneID": 0}),
            ("POST", None, {"systemId": 0, "zoneId": 0}),
            ("GET", {"systemid": 0, "zoneid": 0}, None),
            ("GET", {"systemID": 0, "zoneID": 0}, None),
        ]

        for method, params, body in attempts:
            try:
                with async_timeout.timeout(6):
                    async with session.request(method, url, params=params, json=body) as response:
                        if response.status != 200:
                            continue
                        payload = await response.json(content_type=None)
                        zones = _parse_zones_from_response(payload)
                        if zones:
                            return zones
            except Exception:
                continue

        return {}

    async def _load_zones_map(self) -> dict[str, str]:
        """Obtiene el mapa de zonas desde el coordinator cargado o, si es local, desde la API."""
        if self._zones_map is not None:
            return self._zones_map

        zones = self._zones_from_loaded_coordinator()
        if zones:
            self._zones_map = zones
            return zones

        if self._entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_LOCAL) != CONNECTION_TYPE_LOCAL:
            self._zones_map = {}
            return self._zones_map

        host = self._entry.data.get(CONF_HOST, DEFAULT_HOST)
        port = self._entry.data.get(CONF_PORT, DEFAULT_PORT)
        prefix = self._entry.data.get("api_prefix")

        if prefix is not None:
            zones = await self._fetch_zones_once(host, port, prefix)

        if not zones:
            detected = await _autodetect_prefix(self.hass, host, port)
            if detected is not None:
                zones = await self._fetch_zones_once(host, port, detected)
                current = _normalize_prefix(prefix)
                if detected != current:
                    try:
                        self.hass.config_entries.async_update_entry(
                            self._entry,
                            data={**self._entry.data, "api_prefix": detected},
                        )
                    except Exception:
                        pass

        if not zones:
            _LOGGER.debug(
                "No se pudo cargar la lista de zonas para el options flow (entry=%s)",
                self._entry.entry_id,
            )

        self._zones_map = zones
        return zones

    async def _load_cloud_device_options(self) -> dict[str, str]:
        if self._cloud_device_options is not None:
            return self._cloud_device_options

        if self._entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_LOCAL) != CONNECTION_TYPE_CLOUD:
            self._cloud_device_options = {}
            return self._cloud_device_options

        try:
            self._cloud_device_options = await _fetch_cloud_device_options(
                self.hass,
                self._entry.data.get(CONF_EMAIL, ""),
                self._entry.data.get(CONF_PASSWORD, ""),
            )
        except Exception:
            _LOGGER.exception("Could not fetch Airzone Cloud device list for options flow")
            self._cloud_device_options = {}
        return self._cloud_device_options

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        is_cloud = self._entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_LOCAL) == CONNECTION_TYPE_CLOUD
        default_scan = DEFAULT_CLOUD_SCAN_INTERVAL if is_cloud else DEFAULT_SCAN_INTERVAL
        current_scan = self._entry.options.get(CONF_SCAN_INTERVAL, default_scan)
        current_groups = self._entry.options.get(CONF_GROUPS, []) or []
        current_cloud_profile = _infer_cloud_profile(dict(self._entry.options), dict(self._entry.data))
        current_cloud_categories = self._entry.options.get(
            CONF_CLOUD_INCLUDE_CATEGORIES,
            self._entry.data.get(CONF_CLOUD_INCLUDE_CATEGORIES, DEFAULT_CLOUD_INCLUDE_CATEGORIES),
        )
        include_bound_default = (
            DEFAULT_CLOUD_INCLUDE_BOUND_IAQS
            if CLOUD_CATEGORY_CLIMATE_ZONES in current_cloud_categories
            else False
        )
        current_cloud_include_bound_iaqs = self._entry.options.get(
            CONF_CLOUD_INCLUDE_BOUND_IAQS,
            self._entry.data.get(CONF_CLOUD_INCLUDE_BOUND_IAQS, include_bound_default),
        )
        current_cloud_exclude_iaq_names = self._entry.options.get(
            CONF_CLOUD_EXCLUDE_IAQ_NAMES,
            self._entry.data.get(CONF_CLOUD_EXCLUDE_IAQ_NAMES, DEFAULT_CLOUD_EXCLUDE_IAQ_NAMES),
        )
        current_cloud_device_ids = self._entry.options.get(
            CONF_CLOUD_INCLUDE_DEVICE_IDS,
            self._entry.data.get(CONF_CLOUD_INCLUDE_DEVICE_IDS, DEFAULT_CLOUD_INCLUDE_DEVICE_IDS),
        )
        zones_map = await self._load_zones_map()
        cloud_device_options = await self._load_cloud_device_options() if is_cloud else {}

        if user_input is not None:
            scan_val = user_input.get(CONF_SCAN_INTERVAL, current_scan)
            try:
                new_scan = int(scan_val)
                if new_scan < 2 or new_scan > 300:
                    errors["scan_interval"] = "invalid_scan_interval"
            except Exception:
                errors["scan_interval"] = "invalid_scan_interval"

            groups: list[dict[str, Any]] = []
            raw_json = (user_input.get("groups_json") or "").strip()
            if raw_json:
                try:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, list):
                        groups = [group for group in parsed if isinstance(group, dict)]
                    else:
                        errors["groups_json"] = "invalid_json"
                except Exception:
                    errors["groups_json"] = "invalid_json"
            else:
                seen_ids: set[str] = set()
                for idx in range(1, MAX_GROUP_SLOTS + 1):
                    name_key = f"group_{idx}_name"
                    zones_key = f"group_{idx}_zones"
                    name = (user_input.get(name_key) or "").strip()
                    zones_sel = user_input.get(zones_key) or []
                    if not name or not zones_sel:
                        continue
                    gid = _slugify_id(name)
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
                            "zones": [str(zone) for zone in zones_sel],
                        }
                    )

            if not errors:
                options = dict(self._entry.options)
                options[CONF_SCAN_INTERVAL] = new_scan
                options[CONF_GROUPS] = groups
                if is_cloud:
                    selected_profile = str(user_input.get(CONF_CLOUD_PROFILE) or current_cloud_profile)
                    options[CONF_CLOUD_PROFILE] = selected_profile
                    options[CONF_CLOUD_INCLUDE_CATEGORIES] = _cloud_profile_categories(
                        selected_profile,
                        user_input.get(CONF_CLOUD_INCLUDE_CATEGORIES),
                    )
                    options[CONF_CLOUD_INCLUDE_BOUND_IAQS] = bool(
                        user_input.get(
                            CONF_CLOUD_INCLUDE_BOUND_IAQS,
                            DEFAULT_CLOUD_INCLUDE_BOUND_IAQS,
                        )
                    )
                    options[CONF_CLOUD_EXCLUDE_IAQ_NAMES] = (
                        user_input.get(CONF_CLOUD_EXCLUDE_IAQ_NAMES)
                        or DEFAULT_CLOUD_EXCLUDE_IAQ_NAMES
                    ).strip()
                    if cloud_device_options:
                        if _cloud_profile_needs_device_selection(selected_profile):
                            options[CONF_CLOUD_INCLUDE_DEVICE_IDS] = list(
                                user_input.get(CONF_CLOUD_INCLUDE_DEVICE_IDS)
                                or DEFAULT_CLOUD_INCLUDE_DEVICE_IDS
                            )
                        else:
                            options[CONF_CLOUD_INCLUDE_DEVICE_IDS] = list(DEFAULT_CLOUD_INCLUDE_DEVICE_IDS)
                return self.async_create_entry(title="", data=options)

        slot_names: dict[int, str] = {}
        slot_zones: dict[int, list[str]] = {}
        for idx, group in enumerate(current_groups[:MAX_GROUP_SLOTS], start=1):
            if not isinstance(group, dict):
                continue
            slot_names[idx] = group.get("name") or group.get("id") or f"Grupo {idx}"
            zone_list = group.get("zones") or []
            if isinstance(zone_list, list):
                slot_zones[idx] = [str(value) for value in zone_list]

        groups_default_json = ""
        if (not zones_map) or (len(current_groups) > MAX_GROUP_SLOTS):
            try:
                groups_default_json = json.dumps(current_groups, ensure_ascii=False, indent=2)
            except Exception:
                groups_default_json = "[]"

        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_SCAN_INTERVAL, default=current_scan): vol.All(int, vol.Range(min=2, max=300)),
        }

        if is_cloud:
            schema_dict[
                vol.Optional(
                    CONF_CLOUD_PROFILE,
                    default=current_cloud_profile,
                )
            ] = vol.In(CLOUD_PROFILE_LABELS)
            schema_dict[
                vol.Optional(
                    CONF_CLOUD_INCLUDE_CATEGORIES,
                    default=list(current_cloud_categories or DEFAULT_CLOUD_INCLUDE_CATEGORIES),
                )
            ] = cv.multi_select(CLOUD_CATEGORY_LABELS)
            schema_dict[
                vol.Optional(
                    CONF_CLOUD_INCLUDE_BOUND_IAQS,
                    default=bool(current_cloud_include_bound_iaqs),
                )
            ] = cv.boolean
            schema_dict[
                vol.Optional(
                    CONF_CLOUD_EXCLUDE_IAQ_NAMES,
                    default=str(current_cloud_exclude_iaq_names or DEFAULT_CLOUD_EXCLUDE_IAQ_NAMES),
                )
            ] = str
            if cloud_device_options:
                default_device_ids = [
                    str(device_id)
                    for device_id in (current_cloud_device_ids or [])
                    if str(device_id) in cloud_device_options
                ]
                schema_dict[
                    vol.Optional(
                        CONF_CLOUD_INCLUDE_DEVICE_IDS,
                        default=default_device_ids,
                    )
                ] = cv.multi_select(cloud_device_options)

        if zones_map:
            for idx in range(1, MAX_GROUP_SLOTS + 1):
                schema_dict[vol.Optional(f"group_{idx}_name", default=slot_names.get(idx, ""))] = str
                schema_dict[vol.Optional(f"group_{idx}_zones", default=slot_zones.get(idx, []))] = cv.multi_select(zones_map)

        schema_dict[vol.Optional("groups_json", default=groups_default_json)] = str
        schema = vol.Schema(schema_dict)
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
