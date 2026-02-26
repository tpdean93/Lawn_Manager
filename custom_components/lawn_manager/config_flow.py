from homeassistant import config_entries
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.storage import Store
import uuid

from .const import DOMAIN, GRASS_TYPE_LIST, EQUIPMENT_TYPES, EQUIPMENT_BRANDS, CAPACITY_UNITS, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY

MOW_INTERVAL_OPTIONS = {
    3: "Every 3 days (aggressive growth)",
    5: "Every 5 days (active growth)",
    7: "Weekly (7 days) - Most common",
    10: "Every 10 days (moderate growth)",
    14: "Bi-weekly (14 days)",
    21: "Every 3 weeks (slow growth / dormant)",
    30: "Monthly (minimal maintenance)",
}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.user_data = {}
        self.equipment_list = []

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            mow_interval = user_input["mow_interval"]
            if isinstance(mow_interval, str):
                mow_interval = int(mow_interval)

            self.user_data = {
                "yard_zone": user_input["yard_zone"],
                "location": user_input["location"],
                "mow_interval": mow_interval,
                "lawn_size_sqft": user_input["lawn_size_sqft"],
                "weather_entity": user_input.get("weather_entity"),
                "grass_type": user_input.get("grass_type", "Bermuda"),
            }

            if self.user_data["grass_type"] == "Custom":
                return await self.async_step_custom_grass()

            return await self.async_step_equipment()

        weather_entities = []
        for entity_id in self.hass.states.async_entity_ids("weather"):
            state = self.hass.states.get(entity_id)
            if state:
                friendly_name = state.attributes.get("friendly_name", entity_id)
                weather_entities.append((entity_id, friendly_name))

        # Also look for AWN (Ambient Weather Network) weather stations
        for entity_id in self.hass.states.async_entity_ids("sensor"):
            state = self.hass.states.get(entity_id)
            if state and ("awn" in entity_id.lower() or "ambient" in entity_id.lower()):
                attrs = state.attributes
                if attrs.get("temperature") is not None or "weather" in entity_id.lower():
                    friendly_name = attrs.get("friendly_name", entity_id)
                    weather_entities.append((entity_id, f"AWN: {friendly_name}"))

        # Also look for Weather Station entities (various integrations)
        for entity_id in self.hass.states.async_entity_ids("weather"):
            if entity_id not in [w[0] for w in weather_entities]:
                state = self.hass.states.get(entity_id)
                if state:
                    friendly_name = state.attributes.get("friendly_name", entity_id)
                    weather_entities.append((entity_id, friendly_name))

        schema_dict = {
            vol.Required("yard_zone"): str,
            vol.Required("location"): str,
            vol.Required("mow_interval", default="7"): vol.In(
                {str(k): v for k, v in MOW_INTERVAL_OPTIONS.items()}
            ),
            vol.Required("lawn_size_sqft", default=1000): vol.All(vol.Coerce(int), vol.Range(min=100, max=100000)),
            vol.Required("grass_type", default="Bermuda"): vol.In(GRASS_TYPE_LIST),
        }

        if weather_entities:
            weather_options = [("", "None")] + weather_entities
            schema_dict[vol.Optional("weather_entity", default="")] = vol.In({k: v for k, v in weather_options})

        data_schema = vol.Schema(schema_dict)

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "step": "Step 1 of 3: Basic Configuration"
            }
        )

    async def async_step_custom_grass(self, user_input=None) -> FlowResult:
        """Handle custom grass type configuration."""
        errors = {}

        if user_input is not None:
            self.user_data["custom_grass_name"] = user_input["custom_grass_name"]
            self.user_data["custom_grass_season"] = user_input["custom_grass_season"]
            self.user_data["grass_type"] = f"Custom: {user_input['custom_grass_name']} ({user_input['custom_grass_season']})"
            return await self.async_step_equipment()

        data_schema = vol.Schema({
            vol.Required("custom_grass_name"): str,
            vol.Required("custom_grass_season"): vol.In({
                "warm": "Warm Season",
                "cool": "Cool Season",
                "transition": "Transition Zone (Both)"
            })
        })

        return self.async_show_form(
            step_id="custom_grass",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "example": "Examples: Kikuyu, Buffalo Grass, Seashore Paspalum, etc."
            }
        )

    async def async_step_equipment(self, user_input=None) -> FlowResult:
        """Handle equipment collection step."""
        errors = {}

        equipment_store = Store(self.hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
        existing_equipment = await equipment_store.async_load() or {}

        has_existing = bool(existing_equipment)

        if user_input is not None:
            action = user_input.get("action")

            if action == "add_equipment":
                if not user_input.get("equipment_type"):
                    errors["equipment_type"] = "Equipment type is required when adding equipment"
                if not user_input.get("brand"):
                    errors["brand"] = "Brand is required when adding equipment"
                if not user_input.get("capacity_unit"):
                    errors["capacity_unit"] = "Capacity unit is required when adding equipment"

                try:
                    capacity = float(user_input["capacity"])
                    if capacity < 0.1:
                        errors["capacity"] = "Capacity must be at least 0.1"
                except (ValueError, TypeError):
                    errors["capacity"] = "Capacity is required when adding equipment"

                if not errors:
                    equipment_id = str(uuid.uuid4())[:8]
                    equipment = {
                        "id": equipment_id,
                        "type": user_input["equipment_type"],
                        "brand": user_input["brand"],
                        "capacity": float(user_input["capacity"]),
                        "capacity_unit": user_input["capacity_unit"],
                        "friendly_name": f"{user_input['brand']} {user_input['capacity']} {user_input['capacity_unit'].rstrip('s')} {user_input['equipment_type'].title()}"
                    }
                    self.equipment_list.append(equipment)
                    return await self.async_step_equipment()
            elif action == "continue":
                return await self.async_step_final()

        if has_existing:
            action_options = {
                "add_equipment": "Add additional equipment",
                "continue": "Use existing equipment / Continue to next step"
            }
        else:
            action_options = {
                "add_equipment": "Add this equipment and continue adding",
                "continue": "Skip adding equipment / Continue to next step"
            }

        equipment_schema = vol.Schema({
            vol.Optional("equipment_type"): vol.In(EQUIPMENT_TYPES),
            vol.Optional("brand"): str,
            vol.Optional("capacity"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1000)),
            vol.Optional("capacity_unit"): vol.In(CAPACITY_UNITS),
            vol.Required("action"): vol.In(action_options),
        })

        equipment_list_text = ""

        if existing_equipment:
            equipment_list_text += "Your existing equipment (shared across ALL zones):\n"
            for eq_id, eq_info in existing_equipment.items():
                equipment_list_text += f"  - {eq_info.get('friendly_name', f'Equipment {eq_id}')}\n"
            equipment_list_text += "\nThis equipment is already available for all zones. You can add more below if needed.\n\n"

        equipment_list_text += "New equipment being added in this setup:\n"
        if self.equipment_list:
            for eq in self.equipment_list:
                equipment_list_text += f"  - {eq['friendly_name']}\n"
        else:
            equipment_list_text += "  None added yet\n"

        if has_existing:
            equipment_list_text += "\nYou already have equipment set up. Select 'Use existing equipment' to continue, or add more."
        else:
            equipment_list_text += "\nTo add equipment: Fill out all fields above, then select 'Add this equipment'"
            equipment_list_text += "\nTo skip: Just select 'Skip adding equipment'"

        return self.async_show_form(
            step_id="equipment",
            data_schema=equipment_schema,
            errors=errors,
            description_placeholders={
                "step": "Step 2 of 3: Equipment Setup",
                "equipment_list": equipment_list_text
            }
        )

    async def async_step_final(self, user_input=None) -> FlowResult:
        """Handle final confirmation and setup."""
        if user_input is not None:
            final_data = self.user_data.copy()
            final_data["equipment_list"] = self.equipment_list

            return self.async_create_entry(
                title=self.user_data["yard_zone"],
                data=final_data
            )

        mow_interval = self.user_data['mow_interval']
        mow_label = MOW_INTERVAL_OPTIONS.get(mow_interval, f"Every {mow_interval} days")

        summary = f"Zone: {self.user_data['yard_zone']}\n"
        summary += f"Location: {self.user_data['location']}\n"
        summary += f"Lawn Size: {self.user_data['lawn_size_sqft']} sq ft\n"
        summary += f"Mowing Schedule: {mow_label}\n"
        summary += f"Grass Type: {self.user_data.get('grass_type', 'Bermuda')}\n"
        summary += f"Equipment: {len(self.equipment_list)} new items\n"

        if self.equipment_list:
            for eq in self.equipment_list:
                summary += f"  - {eq['friendly_name']}\n"

        summary += "\nIMPORTANT: After setup completes, restart Home Assistant to enable equipment dropdowns in services!"

        return self.async_show_form(
            step_id="final",
            data_schema=vol.Schema({
                vol.Required("confirm", default=True): bool,
            }),
            description_placeholders={
                "step": "Step 3 of 3: Confirmation",
                "summary": summary
            }
        )
