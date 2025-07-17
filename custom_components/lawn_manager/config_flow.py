from homeassistant import config_entries
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.storage import Store

from .const import DOMAIN, GRASS_TYPE_LIST


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
                    "weather_entity": user_input.get("weather_entity"),
                    "grass_type": user_input.get("grass_type", "Bermuda"),
                }
            )

        # Get available weather entities
        weather_entities = []
        for entity_id in self.hass.states.async_entity_ids("weather"):
            state = self.hass.states.get(entity_id)
            if state:
                friendly_name = state.attributes.get("friendly_name", entity_id)
                weather_entities.append((entity_id, friendly_name))

        # Build schema
        schema_dict = {
            vol.Required("yard_zone"): str,
            vol.Required("location"): str,
            vol.Required("mow_interval", default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            vol.Required("grass_type", default="Bermuda"): vol.In(GRASS_TYPE_LIST),
        }

        # Add weather entity selector if weather entities are available
        if weather_entities:
            weather_options = [("", "None")] + weather_entities
            schema_dict[vol.Optional("weather_entity", default="")] = vol.In({k: v for k, v in weather_options})

        data_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )
