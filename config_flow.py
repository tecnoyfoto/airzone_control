import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from .const import DOMAIN, DEFAULT_PORT

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): str,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
})

class AirzoneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flujo de configuración para Airzone Control."""
    
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Primer paso de configuración."""
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
