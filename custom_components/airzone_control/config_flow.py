from __future__ import annotations

from typing import Any

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    DEFAULT_HOST,
    DEFAULT_PORT,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
)

# Rutas candidatas de la Local API según variantes vistas en campo
CANDIDATE_PREFIXES: list[str] = ["", "/api/v1", "/airzone/local/api/v1", "/lapi/v1"]

# ---- utilidades de prueba de conectividad ----

async def _probe_one(hass: HomeAssistant, host: str, port: int, prefix: str) -> bool:
    """Devuelve True si el Airzone responde en esta combinación host/port/prefix."""
    base = f"http://{host}:{port}{prefix}"
    timeout = 6
    try:
        async with aiohttp.ClientSession() as s:
            # /webserver (GET y POST)
            try:
                with async_timeout.timeout(timeout):
                    async with s.get(f"{base}/webserver", timeout=timeout) as r:
                        if r.status == 200:
                            return True
            except Exception:
                pass
            try:
                with async_timeout.timeout(timeout):
                    async with s.post(f"{base}/webserver", json={}, timeout=timeout) as r:
                        if r.status == 200:
                            return True
            except Exception:
                pass
            # /hvac (GET broadcast y POST broadcast)
            try:
                with async_timeout.timeout(timeout):
                    async with s.get(f"{base}/hvac", params={"systemid": 0, "zoneid": 0}, timeout=timeout) as r:
                        if r.status == 200:
                            return True
            except Exception:
                pass
            try:
                with async_timeout.timeout(timeout):
                    async with s.post(f"{base}/hvac", json={"systemID": 0, "zoneID": 0}, timeout=timeout) as r:
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
            return pref
    return None


# ---- Config Flow ----

class AirzoneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str = ""
        self._port: int = DEFAULT_PORT
        self._prefix: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = (user_input.get(CONF_HOST) or "").strip()
            port = int(user_input.get(CONF_PORT) or DEFAULT_PORT)

            if not host:
                errors["base"] = "no_host"
            else:
                # Auto-detección de prefijo de API
                prefix = await _autodetect_prefix(self.hass, host, port)
                if not prefix:
                    # Guardamos host/port y vamos a selector manual de prefijo
                    self._host = host
                    self._port = port
                    return await self.async_step_prefix()
                else:
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
                    }
                    return self.async_create_entry(title=f"Airzone ({host})", data=data, options=options)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_prefix(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Paso manual para seleccionar el prefijo cuando la auto-detección falla."""
        errors: dict[str, str] = {}

        if user_input is not None:
            pref = user_input.get("api_prefix") or ""
            ok = await _probe_one(self.hass, self._host, self._port, pref)
            if not ok:
                errors["base"] = "cannot_connect"
            else:
                self._prefix = pref
                unique = f"{self._host}:{self._port}"
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()

                data = {
                    CONF_HOST: self._host,
                    CONF_PORT: self._port,
                    "api_prefix": pref,
                }
                options = {
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                }
                return self.async_create_entry(title=f"Airzone ({self._host})", data=data, options=options)

        schema = vol.Schema(
            {
                vol.Required(
                    "api_prefix",
                    default=CANDIDATE_PREFIXES[0],
                ): vol.In(CANDIDATE_PREFIXES),
            }
        )
        return self.async_show_form(step_id="prefix", data_schema=schema, errors=errors)

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        # Soporte básico para YAML si alguien lo usa.
        return await self.async_step_user(user_input)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {
            CONF_SCAN_INTERVAL: self._entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=defaults[CONF_SCAN_INTERVAL]): vol.All(
                    int, vol.Range(min=2, max=300)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
