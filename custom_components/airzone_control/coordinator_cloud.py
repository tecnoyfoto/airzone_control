from __future__ import annotations

import asyncio
import hashlib
import logging
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import (
    CLOUD_CATEGORY_ACS,
    CLOUD_CATEGORY_AUX,
    CLOUD_CATEGORY_CLIMATE_ZONES,
    CLOUD_CATEGORY_ENERGY,
    CLOUD_CATEGORY_IAQ,
    CONNECTION_TYPE_CLOUD,
    DEFAULT_CLOUD_EXCLUDE_IAQ_NAMES,
    DEFAULT_CLOUD_BASE_URL,
    DEFAULT_CLOUD_INCLUDE_CATEGORIES,
    DEFAULT_CLOUD_INCLUDE_BOUND_IAQS,
    DEFAULT_CLOUD_INCLUDE_DEVICE_IDS,
    DEFAULT_CLOUD_SCAN_INTERVAL,
)
from .coordinator import AirzoneCoordinator

_LOGGER = logging.getLogger(__name__)

ZONE_DEVICE_TYPES = {"az_zone", "aidoo", "aidoo_it"}
SYSTEM_DEVICE_TYPES = {"az_system"}
ENERGY_DEVICE_TYPES = {"az_energy_clamp"}
ACS_DEVICE_TYPES = {"az_acs", "aidoo_acs"}
IAQ_DEVICE_TYPES = {"az_airqsensor"}
AUX_DEVICE_TYPES = {"az_vmc", "az_relay", "az_dehumidifier"}
SUPPORTED_STATUS_DEVICE_TYPES = (
    ZONE_DEVICE_TYPES
    | SYSTEM_DEVICE_TYPES
    | ENERGY_DEVICE_TYPES
    | ACS_DEVICE_TYPES
    | IAQ_DEVICE_TYPES
    | AUX_DEVICE_TYPES
)


class CloudApiError(Exception):
    """Airzone Cloud API error with a stable backend error id when available."""

    def __init__(self, error_id: str | None, message: str | None = None) -> None:
        self.error_id = error_id or "unknown"
        self.message = message or self.error_id
        super().__init__(self.message)


async def async_cloud_login(
    session: aiohttp.ClientSession,
    email: str,
    password: str,
    *,
    base_url: str = DEFAULT_CLOUD_BASE_URL,
    timeout: int = 15,
) -> dict[str, Any]:
    """Authenticate against Airzone Cloud and return the login payload."""
    url = f"{base_url.rstrip('/')}/auth/login"
    async with session.post(
        url,
        json={"email": email.strip(), "password": password},
        timeout=timeout,
    ) as response:
        text = await response.text()
        payload: dict[str, Any] = {}
        try:
            parsed = await response.json(content_type=None)
            if isinstance(parsed, dict):
                payload = parsed
        except Exception:
            payload = {}

        if response.status == 200:
            return payload

        error_id = payload.get("_id") if isinstance(payload, dict) else None
        message = payload.get("msg") if isinstance(payload, dict) else text
        if response.status in (400, 401, 403, 422):
            raise CloudApiError(str(error_id or "auth_error"), str(message or "Authentication failed"))

        raise aiohttp.ClientError(f"Airzone Cloud login failed: HTTP {response.status}: {text}")


class AirzoneCloudCoordinator(AirzoneCoordinator):
    """Coordinator for Airzone Cloud API, normalized to the local coordinator shape."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        email: str,
        password: str,
        scan_interval: int = DEFAULT_CLOUD_SCAN_INTERVAL,
        user_id: str | None = None,
        include_categories: list[str] | tuple[str, ...] | set[str] | None = None,
        include_bound_iaqs: bool = DEFAULT_CLOUD_INCLUDE_BOUND_IAQS,
        include_device_ids: list[str] | tuple[str, ...] | set[str] | None = None,
        require_device_selection: bool = False,
        exclude_iaq_names: str | list[str] | tuple[str, ...] | set[str] = DEFAULT_CLOUD_EXCLUDE_IAQ_NAMES,
    ) -> None:
        super().__init__(
            hass,
            host="cloud",
            port=443,
            scan_interval=scan_interval,
            api_prefix=None,
        )
        self._email = email.strip().lower()
        self._password = password
        self._user_id = user_id
        self._base_url = DEFAULT_CLOUD_BASE_URL.rstrip("/")
        self._token: str | None = None
        self._refresh_token: str | None = None
        self._session = async_get_clientsession(hass)
        self._include_categories = self._normalize_include_categories(include_categories)
        self._include_bound_iaqs = bool(include_bound_iaqs)
        self._include_device_ids = self._normalize_include_device_ids(include_device_ids)
        self._require_device_selection = bool(require_device_selection)
        self._exclude_iaq_names = self._normalize_exclude_iaq_names(exclude_iaq_names)
        self.cloud_energy_meters: dict[str, dict[str, Any]] = {}

        self.connection_type = CONNECTION_TYPE_CLOUD
        self.uid_scope = f"cloud_{self._stable_scope_id(user_id or self._email)}"
        self.read_only = True
        self.transport_scheme = "cloud"
        self.transport_hvac = "cloud"
        self.transport_iaq = "cloud"
        self.driver = "cloud"
        self.expose_webserver_entities = self._cloud_category_enabled(CLOUD_CATEGORY_CLIMATE_ZONES)

    @staticmethod
    def _normalize_include_categories(categories: list[str] | tuple[str, ...] | set[str] | None) -> set[str]:
        if not categories:
            categories = DEFAULT_CLOUD_INCLUDE_CATEGORIES
        valid = {
            CLOUD_CATEGORY_CLIMATE_ZONES,
            CLOUD_CATEGORY_IAQ,
            CLOUD_CATEGORY_ENERGY,
            CLOUD_CATEGORY_ACS,
            CLOUD_CATEGORY_AUX,
        }
        normalized = {str(category) for category in categories if str(category) in valid}
        return normalized or set(DEFAULT_CLOUD_INCLUDE_CATEGORIES)

    def _cloud_category_enabled(self, category: str) -> bool:
        return category in self._include_categories

    @staticmethod
    def _normalize_include_device_ids(device_ids: list[str] | tuple[str, ...] | set[str] | None) -> set[str]:
        if not device_ids:
            device_ids = DEFAULT_CLOUD_INCLUDE_DEVICE_IDS
        return {str(device_id) for device_id in device_ids if str(device_id).strip()}

    @staticmethod
    def _normalize_exclude_iaq_names(value: str | list[str] | tuple[str, ...] | set[str]) -> set[str]:
        if isinstance(value, str):
            raw_values = value.replace("\n", ",").split(",")
        else:
            raw_values = [str(item) for item in value]
        return {item.strip().casefold() for item in raw_values if item.strip()}

    def _device_category(self, device_type: Any) -> str | None:
        if device_type in ZONE_DEVICE_TYPES or device_type in SYSTEM_DEVICE_TYPES:
            return CLOUD_CATEGORY_CLIMATE_ZONES
        if device_type in ENERGY_DEVICE_TYPES:
            return CLOUD_CATEGORY_ENERGY
        if device_type in ACS_DEVICE_TYPES:
            return CLOUD_CATEGORY_ACS
        if device_type in IAQ_DEVICE_TYPES:
            return CLOUD_CATEGORY_IAQ
        if device_type in AUX_DEVICE_TYPES:
            return CLOUD_CATEGORY_AUX
        return None

    def _device_enabled(self, device_type: Any) -> bool:
        category = self._device_category(device_type)
        return bool(category and self._cloud_category_enabled(category))

    def _entry_enabled(self, entry: dict[str, Any]) -> bool:
        device_id = str(entry.get("device_id") or "")
        if self._require_device_selection and not self._include_device_ids:
            return False
        if self._include_device_ids and device_id not in self._include_device_ids:
            return False
        return self._device_enabled(entry.get("device_type"))

    @staticmethod
    def _stable_scope_id(value: str) -> str:
        digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
        return digest[:12]

    @staticmethod
    def _stable_int(*parts: str) -> int:
        raw = "::".join(str(part) for part in parts if part not in (None, ""))
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        value = int(digest[:8], 16) & 0x7FFFFFFF
        return value or 1

    @staticmethod
    def _to_number(value: Any) -> int | float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        try:
            num = float(value)
        except Exception:
            return None
        return int(num) if num.is_integer() else num

    @staticmethod
    def _to_int(value: Any) -> int | None:
        num = AirzoneCloudCoordinator._to_number(value)
        if num is None:
            return None
        try:
            return int(num)
        except Exception:
            return None

    @staticmethod
    def _bool_to_int(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, (int, float)):
            return 1 if int(value) else 0
        text = str(value).strip().lower()
        if text in ("1", "true", "yes", "on"):
            return 1
        if text in ("0", "false", "no", "off"):
            return 0
        return None

    @staticmethod
    def _temp_celsius(value: Any) -> float | None:
        if isinstance(value, dict):
            for key in ("celsius", "cel", "value"):
                if key in value and value.get(key) is not None:
                    try:
                        return float(value[key])
                    except Exception:
                        return None
            return None
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    @classmethod
    def _canonical_mode(cls, cloud_mode: Any) -> int | None:
        try:
            code = int(cloud_mode)
        except Exception:
            return None
        mapping = {
            0: 0,
            1: 7,
            2: 2,
            3: 3,
            4: 4,
            5: 5,
            6: 3,
            7: 3,
            8: 3,
            9: 3,
            10: 2,
            11: 2,
            12: 2,
        }
        return mapping.get(code)

    @classmethod
    def _canonical_modes(cls, modes: Any) -> list[int]:
        if not isinstance(modes, list):
            return []
        out: list[int] = []
        for value in modes:
            mapped = cls._canonical_mode(value)
            if mapped is None:
                continue
            if mapped not in out:
                out.append(mapped)
        return out

    @classmethod
    def _current_setpoint(cls, status: dict[str, Any], canonical_mode: int | None) -> float | None:
        if "setpoint" in status:
            val = cls._temp_celsius(status.get("setpoint"))
            if val is not None:
                return val

        key_map: dict[int | None, tuple[str, ...]] = {
            3: ("setpoint_air_heat", "setpoint_air_emerheat"),
            2: ("setpoint_air_cool",),
            4: ("setpoint_air_vent",),
            5: ("setpoint_air_dry",),
            7: ("setpoint_air_auto",),
            0: ("setpoint_air_stop",),
            None: (
                "setpoint_air_heat",
                "setpoint_air_cool",
                "setpoint_air_auto",
                "setpoint_air_dry",
                "setpoint_air_vent",
                "setpoint_air_stop",
            ),
        }
        for key in key_map.get(canonical_mode, ()) + key_map[None]:
            if key not in status:
                continue
            val = cls._temp_celsius(status.get(key))
            if val is not None:
                return val
        return None

    @classmethod
    def _current_min_temp(cls, status: dict[str, Any], canonical_mode: int | None) -> float | None:
        key_map: dict[int | None, tuple[str, ...]] = {
            3: ("range_sp_hot_air_min", "range_sp_emerheat_air_min"),
            2: ("range_sp_cool_air_min",),
            4: ("range_sp_vent_air_min",),
            5: ("range_sp_dry_air_min",),
            7: ("range_sp_auto_air_min",),
            0: ("range_sp_stop_air_min",),
            None: (
                "range_sp_hot_air_min",
                "range_sp_cool_air_min",
                "range_sp_auto_air_min",
                "range_sp_dry_air_min",
                "range_sp_vent_air_min",
                "range_sp_stop_air_min",
            ),
        }
        for key in key_map.get(canonical_mode, ()) + key_map[None]:
            val = cls._temp_celsius(status.get(key))
            if val is not None:
                return val
        return None

    @classmethod
    def _current_max_temp(cls, status: dict[str, Any], canonical_mode: int | None) -> float | None:
        key_map: dict[int | None, tuple[str, ...]] = {
            3: ("range_sp_hot_air_max", "range_sp_emerheat_air_max"),
            2: ("range_sp_cool_air_max",),
            4: ("range_sp_vent_air_max",),
            5: ("range_sp_dry_air_max",),
            7: ("range_sp_auto_air_max",),
            0: ("range_sp_stop_air_max",),
            None: (
                "range_sp_hot_air_max",
                "range_sp_cool_air_max",
                "range_sp_auto_air_max",
                "range_sp_dry_air_max",
                "range_sp_vent_air_max",
                "range_sp_stop_air_max",
            ),
        }
        for key in key_map.get(canonical_mode, ()) + key_map[None]:
            val = cls._temp_celsius(status.get(key))
            if val is not None:
                return val
        return None

    async def _login(self) -> None:
        session = await self._ensure_session()
        payload = await async_cloud_login(session, self._email, self._password, base_url=self._base_url)
        self._token = payload.get("token")
        self._refresh_token = payload.get("refreshToken")
        self._user_id = self._user_id or payload.get("_id")
        if not self._token:
            raise UpdateFailed("Airzone Cloud login did not return a token")

    async def _refresh_access_token(self) -> None:
        if not self._refresh_token:
            await self._login()
            return

        session = await self._ensure_session()
        url = f"{self._base_url}/auth/refreshToken/{self._refresh_token}"
        async with session.get(url, timeout=15) as response:
            text = await response.text()
            payload: dict[str, Any] = {}
            try:
                parsed = await response.json(content_type=None)
                if isinstance(parsed, dict):
                    payload = parsed
            except Exception:
                payload = {}

            if response.status != 200:
                _LOGGER.debug("Cloud token refresh failed: HTTP %s %s", response.status, text)
                await self._login()
                return

            self._token = payload.get("token") or self._token
            self._refresh_token = payload.get("refreshToken") or self._refresh_token
            if not self._token:
                await self._login()

    async def _ensure_authenticated(self) -> None:
        if self._token:
            return
        await self._login()

    async def _cloud_request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        retry_auth: bool = True,
    ) -> dict[str, Any] | list[Any] | None:
        await self._ensure_authenticated()
        session = await self._ensure_session()
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._token}"}

        async with session.request(
            method,
            url,
            params=params,
            json=body,
            headers=headers,
            timeout=20,
        ) as response:
            text = await response.text()
            payload: dict[str, Any] | list[Any] | None = None
            try:
                payload = await response.json(content_type=None)
            except Exception:
                payload = None

            if response.status == 401 and retry_auth:
                await self._refresh_access_token()
                return await self._cloud_request_json(
                    method,
                    path,
                    params=params,
                    body=body,
                    retry_auth=False,
                )

            if response.status >= 400:
                error_id = payload.get("_id") if isinstance(payload, dict) else None
                message = payload.get("msg") if isinstance(payload, dict) else text
                raise CloudApiError(str(error_id or f"http_{response.status}"), str(message or text))

            return payload if payload is not None else {}

    async def _get_installations(self) -> list[dict[str, Any]]:
        first = await self._cloud_request_json("GET", "/installations", params={"items": 10, "page": 0})
        if not isinstance(first, dict):
            return []

        installations = [item for item in first.get("installations", []) if isinstance(item, dict)]
        total = self._to_int(first.get("total")) or len(installations)
        if total <= len(installations):
            return installations

        pages = (total + 9) // 10
        for page in range(1, pages):
            chunk = await self._cloud_request_json("GET", "/installations", params={"items": 10, "page": page})
            if not isinstance(chunk, dict):
                continue
            for item in chunk.get("installations", []):
                if isinstance(item, dict):
                    installations.append(item)
        return installations

    async def _get_installation_detail(self, installation_id: str) -> dict[str, Any] | None:
        payload = await self._cloud_request_json("GET", f"/installations/{installation_id}")
        return payload if isinstance(payload, dict) else None

    async def _get_webserver_status(self, installation_id: str, ws_id: str) -> dict[str, Any] | None:
        payload = await self._cloud_request_json(
            "GET",
            f"/devices/ws/{ws_id}/status",
            params={"installation_id": installation_id},
        )
        return payload if isinstance(payload, dict) else None

    async def _get_device_status(self, installation_id: str, device_id: str) -> dict[str, Any] | None:
        payload = await self._cloud_request_json(
            "GET",
            f"/devices/{device_id}/status",
            params={"installation_id": installation_id},
        )
        return payload if isinstance(payload, dict) else None

    async def _gather_limited(self, coroutines: list[Any], limit: int = 6) -> list[Any]:
        semaphore = asyncio.Semaphore(limit)

        async def _run(coro: Any) -> Any:
            async with semaphore:
                return await coro

        return await asyncio.gather(*[_run(coro) for coro in coroutines], return_exceptions=True)

    def _system_id_for_entry(self, entry: dict[str, Any]) -> int:
        installation_id = str(entry.get("installation_id") or "")
        ws_id = str(entry.get("ws_id") or "")
        system_number = entry.get("system_number")
        if system_number in (None, ""):
            return self._stable_int("cloud-system", installation_id, ws_id, str(entry.get("device_id") or ""))
        return self._stable_int("cloud-system", installation_id, ws_id, str(system_number))

    def _zone_id_for_entry(self, entry: dict[str, Any]) -> int:
        zone_number = self._to_int(entry.get("zone_number"))
        if zone_number is not None and zone_number > 0:
            return zone_number
        return self._stable_int("cloud-zone", str(entry.get("device_id") or ""))

    def _normalize_zone_status(self, entry: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
        mode = self._canonical_mode(status.get("mode"))
        modes = self._canonical_modes(status.get("mode_available"))
        speed_values = [int(v) for v in status.get("speed_values", []) if self._to_int(v) is not None] if isinstance(status.get("speed_values"), list) else []
        zone: dict[str, Any] = {
            "systemID": self._system_id_for_entry(entry),
            "zoneID": self._zone_id_for_entry(entry),
            "name": status.get("name") or entry.get("name") or f"Zone {entry.get('zone_number') or entry.get('device_id')}",
            "on": self._bool_to_int(status.get("power")),
            "mode": mode,
            "modes": modes,
            "sys_modes": modes,
            "roomTemp": self._temp_celsius(status.get("local_temp")),
            "workTemp": self._temp_celsius(status.get("zone_work_temp")),
            "setpoint": self._current_setpoint(status, mode),
            "heatsetpoint": self._temp_celsius(status.get("setpoint_air_heat")),
            "coolsetpoint": self._temp_celsius(status.get("setpoint_air_cool")),
            "minTemp": self._current_min_temp(status, mode),
            "maxTemp": self._current_max_temp(status, mode),
            "double_sp": self._bool_to_int(status.get("double_sp")) or 0,
            "speed": self._to_int(status.get("speed_conf") or status.get("pspeed") or status.get("speed")),
            "speeds": max(len(speed_values) - 1, 0) if speed_values else 0,
            "speed_values": speed_values,
            "sleep": self._to_int(status.get("sleep")),
            "sleep_values": [int(v) for v in status.get("sleep_values", []) if self._to_int(v) is not None] if isinstance(status.get("sleep_values"), list) else [],
            "humidity": self._to_number(status.get("humidity")),
            "manufacturer": "Airzone Cloud",
            "cloud_installation_id": entry.get("installation_id"),
            "cloud_ws_id": entry.get("ws_id"),
            "cloud_device_id": entry.get("device_id"),
            "cloud_device_type": entry.get("device_type"),
            "cloud_mode": self._to_int(status.get("mode")),
            "ws_connected": self._bool_to_int(status.get("ws_connected")),
            "isConnected": self._bool_to_int(status.get("isConnected")),
        }

        for key in (
            "aq_mode_conf",
            "aq_mode_values",
            "aq_active",
            "aqpm1_0",
            "aqpm2_5",
            "aqpm10",
            "sleep_values",
            "usermode_conf",
            "usermode_values",
            "eco_conf",
            "eco_values",
            "timer_values",
            "slats_v_values",
            "slats_h_values",
            "slats_vertical",
            "slats_horizontal",
            "slats_vswing",
            "slats_hswing",
            "erv_mode",
            "erv_mode_values",
            "local_vent",
        ):
            if key in status:
                zone[key] = status.get(key)

        aq_quality = status.get("aq_quality")
        if isinstance(aq_quality, (int, float)):
            zone["aq_quality"] = int(aq_quality)

        return {key: value for key, value in zone.items() if value is not None}

    def _normalize_system_status(self, entry: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
        system: dict[str, Any] = {
            "systemID": self._system_id_for_entry(entry),
            "manufacturer": "Airzone Cloud",
            "mc_connected": self._bool_to_int(status.get("isConnected")),
            "mode": self._canonical_mode(status.get("mode")),
            "modes": self._canonical_modes(status.get("mode_available")),
            "speed": self._to_int(status.get("speed_conf") or status.get("speed")),
            "speed_values": [int(v) for v in status.get("speed_values", []) if self._to_int(v) is not None] if isinstance(status.get("speed_values"), list) else [],
            "cloud_installation_id": entry.get("installation_id"),
            "cloud_ws_id": entry.get("ws_id"),
            "cloud_device_id": entry.get("device_id"),
            "cloud_device_type": entry.get("device_type"),
            "ws_connected": self._bool_to_int(status.get("ws_connected")),
        }

        for key in (
            "timer_values",
            "sleep_values",
            "aqpm1_0",
            "aqpm2_5",
            "aqpm10",
            "aq_present",
            "aq_mode_values",
            "eco_values",
            "usermode_values",
            "ws_sched_available",
            "ws_sched_calendar_available",
            "ws_sched_param_indep",
            "warnings",
            "errors",
        ):
            if key in status:
                system[key] = status.get(key)

        aq_quality = status.get("aq_quality")
        if isinstance(aq_quality, (int, float)):
            system["aq_quality"] = int(aq_quality)

        return {key: value for key, value in system.items() if value is not None}

    def _normalize_energy_meter_status(self, entry: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
        meter: dict[str, Any] = {
            "id": str(entry.get("device_id") or ""),
            "name": status.get("name") or entry.get("name") or "Airzone Energy Meter",
            "manufacturer": "Airzone Cloud",
            "cloud_installation_id": entry.get("installation_id"),
            "cloud_ws_id": entry.get("ws_id"),
            "cloud_device_id": entry.get("device_id"),
            "cloud_device_type": entry.get("device_type"),
            "system_number": entry.get("system_number"),
        }

        candidate_keys = (
            "energy_hour_latest",
            "energy_day_latest",
            "energy_day_current",
            "energy_month_latest",
            "energy_month_current",
            "energy_year_latest",
            "energy_year_current",
            "energy_total",
            "total_energy",
            "energy_accumulated",
            "energy_consumed",
            "consumption",
            "energy_acc",
            "energy_ret",
            "energy1_acc",
            "energy1_ret",
            "energy2_acc",
            "energy2_ret",
            "energy3_acc",
            "energy3_ret",
            "power",
            "active_power",
            "power_latest",
            "power_total",
            "power_p1",
            "power_p2",
            "power_p3",
            "current",
            "current_total",
            "current_p1",
            "current_p2",
            "current_p3",
            "voltage",
            "voltage_total",
            "voltage_p1",
            "voltage_p2",
            "voltage_p3",
        )
        for key in candidate_keys:
            if key in status:
                value = self._to_number(status.get(key))
                if value is not None:
                    meter[key] = value

        for key in (
            "energy_period_end_dt",
            "energy1_period_end_dt",
            "energy2_period_end_dt",
            "energy3_period_end_dt",
        ):
            if key in status and status.get(key):
                meter[key] = status.get(key)

        return {key: value for key, value in meter.items() if value is not None}

    def _iaq_id_for_entry(self, entry: dict[str, Any]) -> int:
        for key in ("iaqsensor_id", "iaq_number", "airqsensor_id"):
            value = self._to_int(entry.get(key))
            if value is not None and value > 0:
                return value
        return self._stable_int("cloud-iaq", str(entry.get("device_id") or ""))

    def _cloud_iaq_should_expose(self, entry: dict[str, Any]) -> bool:
        name = str(entry.get("name") or "").strip().casefold()
        if name and name in self._exclude_iaq_names:
            return False
        if self._cloud_category_enabled(CLOUD_CATEGORY_CLIMATE_ZONES):
            return True
        if self._include_bound_iaqs:
            return True

        # Optional complementary mode: avoid duplicating IAQ sensors that are
        # bound to a system/zone already covered by a separate Local API entry.
        return not (entry.get("system_number") or entry.get("zone_number"))

    def _normalize_iaq_status(self, entry: dict[str, Any], status: dict[str, Any]) -> dict[str, Any]:
        sid = self._system_id_for_entry(entry)
        iid = self._iaq_id_for_entry(entry)
        iaq: dict[str, Any] = {
            "systemID": sid,
            "iaqsensorID": iid,
            "name": status.get("name") or entry.get("name") or "Airzone IAQ sensor",
            "manufacturer": "Airzone Cloud",
            "cloud_installation_id": entry.get("installation_id"),
            "cloud_ws_id": entry.get("ws_id"),
            "cloud_device_id": entry.get("device_id"),
            "cloud_device_type": entry.get("device_type"),
            "system_number": entry.get("system_number"),
            "zone_number": entry.get("zone_number"),
        }

        numeric_map = {
            "iaq_score": ("aq_score", "iaq_score"),
            "co2_value": ("aq_co2", "co2_value", "co2"),
            "tvoc_value": ("aq_tvoc", "tvoc_value", "tvoc"),
            "pressure_value": ("aq_pressure", "pressure_value", "pressure"),
            "pm1_0_value": ("aqpm1_0", "pm1_0_value", "pm1_value"),
            "pm2_5_value": ("aqpm2_5", "pm2_5_value", "pm25_value"),
            "pm10_value": ("aqpm10", "pm10_value"),
            "humidity": ("humidity", "aq_humidity"),
            "temperature": ("temperature", "aq_temperature"),
        }
        for target_key, source_keys in numeric_map.items():
            for source_key in source_keys:
                if source_key not in status:
                    continue
                value = self._to_number(status.get(source_key))
                if value is not None:
                    iaq[target_key] = value
                    break

        aq_quality = status.get("aq_quality")
        if isinstance(aq_quality, str) and aq_quality.strip():
            text = aq_quality.strip().lower()
            iaq["air_quality_text"] = text
            iaq["iaq_quality_text"] = text
        else:
            value = self._to_int(aq_quality)
            if value is not None:
                iaq["iaq_index"] = value

        for source_key, target_key in (
            ("aqi_pm_category", "aqi_pm_category"),
            ("aqi_pm_cat", "aqi_pm_cat"),
            ("aqi_pm_partial", "aqi_pm_partial"),
            ("iaq_index_text", "iaq_index_text"),
            ("iaq_text", "iaq_text"),
            ("needs_ventilation", "needs_ventilation"),
            ("need_ventilation", "need_ventilation"),
        ):
            if source_key in status and status.get(source_key) is not None:
                iaq[target_key] = status.get(source_key)

        return {key: value for key, value in iaq.items() if value is not None}

    @staticmethod
    def _previous_cloud_iaq(
        previous_iaqs: dict[tuple[int, int], dict[str, Any]],
        entry: dict[str, Any],
    ) -> tuple[tuple[int, int], dict[str, Any]] | tuple[None, None]:
        device_id = str(entry.get("device_id") or "")
        if not device_id:
            return None, None
        for key, iaq in previous_iaqs.items():
            if str(iaq.get("cloud_device_id") or "") == device_id:
                return key, iaq
        return None, None

    def _merge_aux_status_into_system(self, systems: dict[int, dict[str, Any]], entry: dict[str, Any], status: dict[str, Any]) -> None:
        sid = self._system_id_for_entry(entry)
        target = systems.setdefault(sid, {"systemID": sid, "manufacturer": "Airzone Cloud"})
        device_type = entry.get("device_type")

        if device_type in {"az_acs", "aidoo_acs"}:
            power = self._bool_to_int(status.get("power"))
            if power is not None:
                target["acs_power"] = power
        elif device_type == "az_energy_clamp":
            energy = self._to_number(status.get("energy_hour_latest"))
            if energy is not None:
                target["energy_consump"] = energy

    def _build_webserver_summary(
        self,
        installations: list[dict[str, Any]],
        ws_payloads: list[dict[str, Any]],
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "cloud": 1,
            "cloud_connected": 1,
            "transport": "cloud",
            "installations": len(installations),
            "webservers": len(ws_payloads),
        }
        if not ws_payloads:
            return summary

        first = ws_payloads[0]
        status = first.get("status") if isinstance(first.get("status"), dict) else {}
        config = first.get("config") if isinstance(first.get("config"), dict) else {}
        if first.get("ws_type"):
            summary["ws_type"] = first.get("ws_type")
        if config.get("ws_fw"):
            summary["ws_firmware"] = config.get("ws_fw")
        if config.get("api_version") is not None:
            summary["api_ver"] = config.get("api_version")
        if config.get("mac"):
            summary["mac"] = config.get("mac")
        if status.get("stat_channel") is not None:
            summary["wifi_channel"] = status.get("stat_channel")
        elif config.get("stat_channel") is not None:
            summary["wifi_channel"] = config.get("stat_channel")
        if status.get("stat_quality") is not None:
            summary["wifi_quality"] = status.get("stat_quality")
        if status.get("stat_rssi") is not None:
            summary["wifi_rssi"] = status.get("stat_rssi")
        if config.get("conn_type"):
            summary["interface"] = config.get("conn_type")
        if config.get("lmachine_fw"):
            summary["lmachine_firmware"] = config.get("lmachine_fw")
        return summary

    async def _async_update_data(self) -> dict[tuple[int, int], dict[str, Any]]:
        try:
            installations = await self._get_installations()
        except CloudApiError as err:
            raise UpdateFailed(f"Cloud installations fetch failed: {err.error_id}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Cloud connection failed: {err}") from err

        detail_results = await self._gather_limited(
            [self._get_installation_detail(str(item.get("installation_id"))) for item in installations if item.get("installation_id")],
            limit=4,
        )

        details_by_installation: dict[str, dict[str, Any]] = {}
        for detail in detail_results:
            if isinstance(detail, Exception):
                _LOGGER.debug("Cloud installation detail fetch failed: %s", detail)
                continue
            if isinstance(detail, dict) and detail.get("installation_id"):
                details_by_installation[str(detail.get("installation_id"))] = detail

        ws_tasks: list[Any] = []
        for item in installations:
            installation_id = item.get("installation_id")
            if not installation_id:
                continue
            for ws_id in item.get("ws_ids", []) or []:
                ws_tasks.append(self._get_webserver_status(str(installation_id), str(ws_id)))
        ws_results = await self._gather_limited(ws_tasks, limit=4)
        ws_payloads = [payload for payload in ws_results if isinstance(payload, dict)]

        inventory_by_device: dict[str, dict[str, Any]] = {}
        for item in installations:
            installation_id = str(item.get("installation_id") or "")
            detail = details_by_installation.get(installation_id) or {}
            for group in detail.get("groups", []) or []:
                if not isinstance(group, dict):
                    continue
                for device in group.get("devices", []) or []:
                    if not isinstance(device, dict):
                        continue
                    device_id = device.get("device_id")
                    if not device_id:
                        continue
                    meta = device.get("meta") if isinstance(device.get("meta"), dict) else {}
                    inventory_by_device[str(device_id)] = {
                        "installation_id": installation_id,
                        "device_id": str(device_id),
                        "device_type": device.get("type"),
                        "name": device.get("name"),
                        "ws_id": device.get("ws_id"),
                        "system_number": meta.get("system_number"),
                        "zone_number": meta.get("zone_number"),
                        "iaqsensor_id": meta.get("iaqsensor_id") or meta.get("iaqsensorID"),
                        "iaq_number": meta.get("iaq_number"),
                        "airqsensor_id": meta.get("airqsensor_id") or meta.get("airqsensorID"),
                    }

        device_entries = [
            entry
            for entry in inventory_by_device.values()
            if entry.get("device_type") in SUPPORTED_STATUS_DEVICE_TYPES
            and self._entry_enabled(entry)
        ]
        device_status_results = await self._gather_limited(
            [
                self._get_device_status(str(entry.get("installation_id")), str(entry.get("device_id")))
                for entry in device_entries
            ],
            limit=6,
        )

        systems: dict[int, dict[str, Any]] = {}
        zones: list[dict[str, Any]] = []
        energy_meters: dict[str, dict[str, Any]] = {}
        iaqs: dict[tuple[int, int], dict[str, Any]] = {}
        previous_energy_meters = dict(self.cloud_energy_meters or {})
        previous_iaqs = dict(self.iaqs or {})

        for entry, status in zip(device_entries, device_status_results, strict=False):
            if isinstance(status, Exception):
                _LOGGER.debug("Cloud device status fetch failed for %s: %s", entry.get("device_id"), status)
                device_id = str(entry.get("device_id") or "")
                device_type = entry.get("device_type")
                if device_type in ENERGY_DEVICE_TYPES and device_id in previous_energy_meters:
                    energy_meters[device_id] = previous_energy_meters[device_id]
                elif device_type in IAQ_DEVICE_TYPES:
                    previous_key, previous_iaq = self._previous_cloud_iaq(previous_iaqs, entry)
                    if previous_key is not None and previous_iaq is not None:
                        iaqs[previous_key] = previous_iaq
                continue
            if not isinstance(status, dict):
                device_id = str(entry.get("device_id") or "")
                device_type = entry.get("device_type")
                if device_type in ENERGY_DEVICE_TYPES and device_id in previous_energy_meters:
                    energy_meters[device_id] = previous_energy_meters[device_id]
                elif device_type in IAQ_DEVICE_TYPES:
                    previous_key, previous_iaq = self._previous_cloud_iaq(previous_iaqs, entry)
                    if previous_key is not None and previous_iaq is not None:
                        iaqs[previous_key] = previous_iaq
                continue

            device_type = entry.get("device_type")
            if device_type in SYSTEM_DEVICE_TYPES:
                sid = self._system_id_for_entry(entry)
                merged = systems.setdefault(sid, {"systemID": sid, "manufacturer": "Airzone Cloud"})
                merged.update(self._normalize_system_status(entry, status))
                continue

            if device_type in ZONE_DEVICE_TYPES:
                zones.append(self._normalize_zone_status(entry, status))
                continue

            if device_type in ENERGY_DEVICE_TYPES:
                meter = self._normalize_energy_meter_status(entry, status)
                meter_id = str(meter.get("id") or entry.get("device_id") or "")
                if meter_id:
                    energy_meters[meter_id] = {**(previous_energy_meters.get(meter_id) or {}), **meter}
                continue

            if device_type in IAQ_DEVICE_TYPES:
                if self._cloud_iaq_should_expose(entry):
                    iaq = self._normalize_iaq_status(entry, status)
                    sid = self._to_int(iaq.get("systemID"))
                    iid = self._to_int(iaq.get("iaqsensorID"))
                    if sid is not None and iid is not None:
                        _previous_key, previous_iaq = self._previous_cloud_iaq(previous_iaqs, entry)
                        iaqs[(sid, iid)] = {**(previous_iaq or {}), **iaq}
                else:
                    _LOGGER.debug(
                        "Skipping cloud IAQ %s in complementary mode because it is bound to system/zone metadata",
                        entry.get("device_id"),
                    )
                continue

            self._merge_aux_status_into_system(systems, entry, status)

        if self._cloud_category_enabled(CLOUD_CATEGORY_CLIMATE_ZONES):
            mapped = self._map_zones(zones)
            if mapped:
                self.data = mapped
                self._hvac_empty_reads = 0
            else:
                self._hvac_empty_reads += 1
                if self.data:
                    mapped = self.data
                    _LOGGER.warning("Cloud update came back empty; keeping last valid state")
                else:
                    raise UpdateFailed("Cloud update returned no valid zones")
        else:
            mapped = {}
            self.data = mapped
            self._hvac_empty_reads = 0

        derived_systems = self._derive_systems_from_zones(zones)
        for sid, payload in derived_systems.items():
            target = systems.setdefault(int(sid), {"systemID": int(sid)})
            for key, value in payload.items():
                target.setdefault(key, value)
        for sid in {sid for (sid, _zid) in mapped.keys()}:
            systems.setdefault(int(sid), {"systemID": int(sid), "manufacturer": "Airzone Cloud"})

        for (sid, _zid), zone in mapped.items():
            system = systems.get(int(sid)) or {}
            if "modes" in system and "sys_modes" not in zone:
                zone["sys_modes"] = system.get("modes")

        self.systems = systems
        self.cloud_energy_meters = energy_meters
        self.webserver = self._build_webserver_summary(installations, ws_payloads)
        self.iaqs = iaqs
        self.transport_hvac = "cloud"
        self.transport_iaq = "cloud"
        self.transport_scheme = "cloud"
        self.version = str(
            self.webserver.get("api_ver")
            or self.webserver.get("ws_firmware")
            or self.version
            or "cloud"
        )

        system_ids = sorted({sid for (sid, _zid) in mapped.keys()} | {sid for (sid, _iid) in iaqs.keys()})
        self.system_profiles = {}
        for sid in system_ids:
            prof = self._determine_system_profile(sid)
            prof["zone_count"] = len([1 for (sys_id, _zid) in mapped.keys() if sys_id == sid])
            prof["iaq_count"] = len([1 for (sys_id, _iid) in iaqs.keys() if sys_id == sid])
            self.system_profiles[sid] = prof

        return mapped

    async def async_set_zone_params(self, system_id: int, zone_id: int, *, request_refresh: bool = True, **kwargs) -> dict | None:
        raise HomeAssistantError("Cloud API write support is not enabled yet in this phase.")

    async def async_set_iaq_params(self, system_id: int, iaq_id: int, **kwargs) -> dict | None:
        raise HomeAssistantError("Cloud API write support is not enabled yet in this phase.")

    async def async_close(self) -> None:
        """The shared Home Assistant session must not be closed by the integration."""
        return None
