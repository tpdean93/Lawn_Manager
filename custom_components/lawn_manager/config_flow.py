from homeassistant import config_entries
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CHEMICALS

CHEMICAL_OPTIONS = list(CHEMICALS.keys())
METHOD_OPTIONS = ["Sprayer", "Spreader"]

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required("yard_zone"): str,
    vol.Required("location"): str,
    vol.Required("mow_interval", default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
    vol.Optional("chemical"): vol.In(CHEMICAL_OPTIONS),
    vol.Optional("custom_chemical"): str,
    vol.Required("method", default="Sprayer"): vol.In(METHOD_OPTIONS),
})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            chemical = user_input.get("chemical")
            custom_chemical = user_input.get("custom_chemical")

            # Validation: require one or the other
            if not chemical and not custom_chemical:
                errors["chemical"] = "required"
                errors["custom_chemical"] = "required"
            else:
                # Prefer custom if provided
                if custom_chemical:
                    user_input["chemical"] = custom_chemical

                return self.async_create_entry(
                    title=user_input["yard_zone"],
                    data={
                        "yard_zone": user_input["yard_zone"],
                        "location": user_input["location"],
                        "mow_interval": user_input["mow_interval"],
                        "chemical": user_input["chemical"],
                        "method": user_input["method"]
                    }
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )
