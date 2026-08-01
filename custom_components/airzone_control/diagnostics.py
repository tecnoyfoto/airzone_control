"""Diagnostics support for Airzone Control."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from ipaddress import IPv4Address, IPv6Address
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import AirzoneCoordinator

TO_REDACT = {
    "ip",
    "host",
    "hostname",
    "url",
    "base_url",
    "email",
    "token",
    "access_token",
    "refresh_token",
    "password",
    "user_id",
    "installation_id",
    "device_id",
    "ws_id",
    "cloud_installation_id",
    "cloud_device_id",
    "cloud_ws_id",
    "ssid",
    "mac",
    "mac_address",
    "serial",
    "serial_number",
    "unique_id",
    "title",
    "name",
    "location",
    "address",
    "latitude",
    "longitude",
}

_NORMALIZED_REDACT_KEYS = {
    "".join(char for char in key.casefold() if char.isalnum()) for key in TO_REDACT
}
_REDACTED = "**REDACTED**"


def _jsonable(obj: Any) -> Any:
    """Best-effort conversion to JSON-serializable structures."""
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()

    if isinstance(obj, timedelta):
        return obj.total_seconds()

    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, (IPv4Address, IPv6Address)):
        return str(obj)

    if isinstance(obj, Mapping):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            try:
                key = str(k)
            except Exception:
                key = repr(k)
            out[key] = _jsonable(v)
        return out

    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]

    try:
        return str(obj)
    except Exception:
        return repr(obj)


def _redact_api_data(obj: Any) -> Any:
    """Recursively redact API data using case-insensitive key matching."""
    if isinstance(obj, Mapping):
        redacted: dict[str, Any] = {}
        for raw_key, value in obj.items():
            key = str(raw_key)
            normalized_key = "".join(
                char for char in key.casefold() if char.isalnum()
            )
            redacted[key] = (
                _REDACTED
                if normalized_key in _NORMALIZED_REDACT_KEYS
                else _redact_api_data(value)
            )
        return redacted

    if isinstance(obj, list):
        return [_redact_api_data(value) for value in obj]

    return obj


def _mapping_values(obj: Any) -> Any:
    """Drop dynamic mapping keys which may themselves contain identifiers."""
    if isinstance(obj, Mapping):
        return list(obj.values())
    return obj


async def async_get_config_entry_diagnostics(hass: HomeAssistant, config_entry):
    """Return diagnostics for a config entry."""
    bundle = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: AirzoneCoordinator = bundle["coordinator"]

    data = {
        "entry": async_redact_data(
            {
                "title": config_entry.title,
                "data": dict(config_entry.data),
                "options": dict(config_entry.options),
                "unique_id": config_entry.unique_id,
                "version": config_entry.version,
                "minor_version": config_entry.minor_version,
            },
            TO_REDACT,
        ),
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(getattr(coordinator, "update_interval", "")),
            "connection_type": getattr(coordinator, "connection_type", "unknown"),
            "transport_scheme": getattr(coordinator, "transport_scheme", None),
            "transport_hvac": getattr(coordinator, "transport_hvac", None),
            "transport_iaq": getattr(coordinator, "transport_iaq", None),
            "transport_webserver": getattr(
                coordinator,
                "transport_webserver",
                None,
            ),
            "iaq_update_success": getattr(
                coordinator,
                "iaq_update_success",
                True,
            ),
            "webserver_update_success": getattr(
                coordinator,
                "webserver_update_success",
                True,
            ),
        },
        "api_data": _redact_api_data(
            _jsonable(
                {
                    "zones": _mapping_values(
                        getattr(coordinator, "data", None)
                    ),
                    "systems": _mapping_values(
                        getattr(coordinator, "systems", None)
                    ),
                    "iaqs": _mapping_values(
                        getattr(coordinator, "iaqs", None)
                    ),
                    "webserver": getattr(coordinator, "webserver", None),
                    "cloud_energy_meters": _mapping_values(
                        getattr(
                            coordinator,
                            "cloud_energy_meters",
                            None,
                        )
                    ),
                }
            )
        ),
    }

    return _jsonable(data)
