from __future__ import annotations

from typing import Any, Optional

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

API_BASE = "http://{host}:{port}/api/v1"


async def _get_json(session: aiohttp.ClientSession, url: str) -> dict:
    async with async_timeout.timeout(10):
        async with session.get(url) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"GET {url} -> {resp.status}: {text}")
            try:
                return await resp.json(content_type=None)
            except Exception:
                return {"raw": text}


async def _post_json(session: aiohttp.ClientSession, url: str, json_body: dict) -> dict:
    async with async_timeout.timeout(10):
        async with session.post(url, json=json_body) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise RuntimeError(f"POST {url} -> {resp.status}: {text}")
            try:
                return await resp.json(content_type=None)
            except Exception:
                return {"raw": text}


async def _fetch_device_info(hass: HomeAssistant, host: str, port: int) -> dict:
    """Devuelve {'mac','name','model','version'} usando /webserver; valida /hvac."""
    async with aiohttp.ClientSession() as session:
        # Preferimos /webserver para leer MAC/modelo
        try:
            data = await _get_json(session, API_BASE.format(host=host, port=port) + "/webserver")
        except Exception:
            data = {}

        mac: Optional[str] = (data or {}).get("mac") or (data or {}).get("macAddress")
        name = (data or {}).get("name") or (data or {}).get("hostname") or f"Airzone {host}"
        model = (data or {}).get("product") or (data or {}).get("model") or "Airzone"
        version = (data or {}).get("version") or (data or {}).get("fw")

        # Probamos /hvac para verificar que la API responde
        try:
            await _post_json(
                session,
                API_BASE.format(host=host, port=port) + "/hvac",
                {"systemID": 0, "zoneID": 0},
            )
        except Exception:
            # Si /webserver nos dio MAC lo aceptamos; si no, fallamos
            if not mac:
                raise

        return {"mac": mac, "name": name, "model": model, "version": version}


class AirzoneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flujo de configuración: manual + zeroconf. unique_id = MAC."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_host: Optional[str] = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host: str = user_input[CONF_HOST]
            port: int = user_input[CONF_PORT]
            try:
                info = await _fetch_device_info(self.hass, host, port)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                unique = info.get("mac") or f"{host}:{port}"
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured()
                title = info.get("name") or f"Airzone {host}"
                return self.async_create_entry(
                    title=title,
                    data={CONF_HOST: host, CONF_PORT: port, "info": info},
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_HOST, default=self._discovered_host or DEFAULT_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(int, vol.Range(min=1, max=65535)),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(self, discovery_info: dict[str, Any]) -> FlowResult:
        """mDNS: AZW5GRxxxx / AZPxxxxx..."""
        host = discovery_info.get("host")
        if not host:
            return self.async_abort(reason="unknown")
        self._discovered_host = host

        # Intentamos fijar unique_id ya en discovery (si podemos leer MAC)
        try:
            info = await _fetch_device_info(self.hass, host, DEFAULT_PORT)
            unique = info.get("mac") or f"{host}:{DEFAULT_PORT}"
            await self.async_set_unique_id(unique)
            # Si ya existe, actualizamos datos (host/port) y abortamos
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: host, CONF_PORT: DEFAULT_PORT, "info": info}
            )
        except Exception:
            pass  # seguiremos a formulario

        # Llevamos los datos al formulario para que el usuario confirme
        return await self.async_step_user({CONF_HOST: host, CONF_PORT: DEFAULT_PORT})

    async def async_step_import(self, user_input=None) -> FlowResult:
        return await self.async_step_user(user_input)

    async def async_get_options_flow(self, entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(entry)


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
                    int, vol.Range(min=5, max=300)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
