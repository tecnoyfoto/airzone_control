import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector
from .const import DOMAIN, DEFAULT_PORT

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
})

class AirzoneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flujo de configuración para Airzone Control."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Primer paso de configuración manual."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Airzone Control",
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors
        )

    async def async_step_zeroconf(self, discovery_info=None):
        """
        Intento de detección por mDNS:
        discovery_info puede traer keys como 'hostname', 'port', etc.
        """
        if not discovery_info:
            return self.async_abort(reason="no_discovery_info")

        # Extrae info: p. ej. hostname = "azw5gryyyy.local"
        host = discovery_info.get("hostname", "")
        port = discovery_info.get("port", 3000)

        # Comprobamos si ya hay una instancia configurada con ese host
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()

        # Proponemos auto-config
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=host): str,
                vol.Required(CONF_PORT, default=port): int,
            }),
        )
