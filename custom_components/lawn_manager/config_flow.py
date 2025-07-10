import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, DEFAULT_GRASS_TYPES, DEFAULT_ZONES

class LawnManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lawn Manager."""

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Lawn Manager", data=user_input)

        schema = vol.Schema({
            vol.Required("grass_type", default="Warm Season"): vol.In(DEFAULT_GRASS_TYPES),
            vol.Optional("zones", default=DEFAULT_ZONES): vol.All(vol.Coerce(list)),
        })
        return self.async_show_form(step_id="user", data_schema=schema)
