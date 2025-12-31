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
    "token",
    "access_token",
    "refresh_token",
    "password",
    "ssid",
    "mac",
    "mac_address",
    "serial",
    "serial_number",
    "unique_id",
}


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
        },
        "api_data": _jsonable(getattr(coordinator, "data", None)),
    }

    return _jsonable(data)
