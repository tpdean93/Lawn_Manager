from homeassistant import config_entries
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("yard_zone"): str,
    vol.Required("location"): str,
    vol.Required("mow_interval", default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input["yard_zone"],
                data={
                    "yard_zone": user_input["yard_zone"],
                    "location": user_input["location"],
                    "mow_interval": user_input["mow_interval"],
                }
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )
