from homeassistant import config_entries
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.storage import Store
import uuid

from .const import DOMAIN, GRASS_TYPE_LIST, EQUIPMENT_TYPES, EQUIPMENT_BRANDS, CAPACITY_UNITS, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY

def _scan_weather_entities(hass):
    """Scan for all weather entities including AWN and other weather stations."""
    weather_entities = []
    seen_ids = set()

    for entity_id in hass.states.async_entity_ids("weather"):
        state = hass.states.get(entity_id)
        if state and entity_id not in seen_ids:
            friendly_name = state.attributes.get("friendly_name", entity_id)
            weather_entities.append((entity_id, friendly_name))
            seen_ids.add(entity_id)

    station_keywords = ["awn", "ambient", "weatherstation", "weather_station",
                        "tempest", "weatherflow", "acurite", "ecowitt", "weewx"]
    for entity_id in hass.states.async_entity_ids("sensor"):
        if entity_id in seen_ids:
            continue
        state = hass.states.get(entity_id)
        if not state:
            continue

        eid_lower = entity_id.lower()
        name_lower = (state.attributes.get("friendly_name", "") or "").lower()
        matched = any(kw in eid_lower or kw in name_lower for kw in station_keywords)
        if not matched:
            continue

        attrs = state.attributes
        has_weather_data = (
            attrs.get("temperature") is not None
            or attrs.get("humidity") is not None
            or "temp" in eid_lower
            or "weather" in eid_lower
            or "condition" in eid_lower
        )
        if has_weather_data:
            friendly_name = attrs.get("friendly_name", entity_id)
            weather_entities.append((entity_id, f"Station: {friendly_name}"))
            seen_ids.add(entity_id)

    return weather_entities


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
        self.user_data = {}
        self.equipment_list = []

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)

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

        weather_entities = self._get_weather_entities()

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

    def _get_weather_entities(self):
        return _scan_weather_entities(self.hass)

    async def async_step_custom_grass(self, user_input=None) -> FlowResult:
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
        """Handle equipment step. For zones with existing equipment, show a simple skip/add choice first."""
        errors = {}

        equipment_store = Store(self.hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
        existing_equipment = await equipment_store.async_load() or {}
        has_existing = bool(existing_equipment)

        if user_input is not None:
            action = user_input.get("action")

            if action == "add_equipment":
                if not user_input.get("equipment_type"):
                    errors["equipment_type"] = "Equipment type is required"
                if not user_input.get("brand"):
                    errors["brand"] = "Brand is required"
                if not user_input.get("capacity_unit"):
                    errors["capacity_unit"] = "Capacity unit is required"

                try:
                    capacity = float(user_input["capacity"])
                    if capacity < 0.1:
                        errors["capacity"] = "Capacity must be at least 0.1"
                except (ValueError, TypeError):
                    errors["capacity"] = "Capacity is required"

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
            elif action == "add_new":
                return await self.async_step_add_equipment()

        # If equipment already exists, show simplified choice
        if has_existing and not self.equipment_list:
            equip_names = [eq_info.get('friendly_name', eq_id) for eq_id, eq_info in existing_equipment.items()]
            equip_text = "Your equipment:\n"
            for name in equip_names:
                equip_text += f"  - {name}\n"
            equip_text += "\nEquipment is shared across all zones."

            schema = vol.Schema({
                vol.Required("action", default="continue"): vol.In({
                    "continue": "Use existing equipment - Continue",
                    "add_new": "Add more equipment",
                }),
            })
            return self.async_show_form(
                step_id="equipment",
                data_schema=schema,
                errors=errors,
                description_placeholders={
                    "step": "Step 2 of 3: Equipment Setup",
                    "equipment_list": equip_text,
                }
            )

        # No existing equipment or user chose to add more - show full form
        action_options = {
            "add_equipment": "Add this equipment and continue adding",
            "continue": "Done adding equipment / Continue to next step",
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
            equipment_list_text += "Existing equipment:\n"
            for eq_id, eq_info in existing_equipment.items():
                equipment_list_text += f"  - {eq_info.get('friendly_name', f'Equipment {eq_id}')}\n"
            equipment_list_text += "\n"

        equipment_list_text += "New equipment being added:\n"
        if self.equipment_list:
            for eq in self.equipment_list:
                equipment_list_text += f"  - {eq['friendly_name']}\n"
        else:
            equipment_list_text += "  None added yet\n"

        return self.async_show_form(
            step_id="equipment",
            data_schema=equipment_schema,
            errors=errors,
            description_placeholders={
                "step": "Step 2 of 3: Equipment Setup",
                "equipment_list": equipment_list_text
            }
        )

    async def async_step_add_equipment(self, user_input=None) -> FlowResult:
        """Show full equipment add form after user chose to add more."""
        return await self.async_step_equipment()

    async def async_step_final(self, user_input=None) -> FlowResult:
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


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for reconfiguring a zone."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Show the main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "zone_settings": "Change Zone Settings (mow interval, lawn size, location)",
                "weather": "Change Weather Source",
                "grass": "Change Grass Type",
            }
        )

    async def async_step_zone_settings(self, user_input=None) -> FlowResult:
        """Allow changing zone settings."""
        if user_input is not None:
            mow_interval = user_input.get("mow_interval", self.config_entry.data.get("mow_interval", 7))
            if isinstance(mow_interval, str):
                mow_interval = int(mow_interval)

            new_data = {**self.config_entry.data}
            new_data["location"] = user_input.get("location", new_data.get("location", ""))
            new_data["mow_interval"] = mow_interval
            new_data["lawn_size_sqft"] = user_input.get("lawn_size_sqft", new_data.get("lawn_size_sqft", 1000))

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
                title=new_data.get("yard_zone", self.config_entry.title),
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        current = self.config_entry.data
        current_interval = str(current.get("mow_interval", 7))

        data_schema = vol.Schema({
            vol.Required("location", default=current.get("location", "")): str,
            vol.Required("mow_interval", default=current_interval): vol.In(
                {str(k): v for k, v in MOW_INTERVAL_OPTIONS.items()}
            ),
            vol.Required("lawn_size_sqft", default=current.get("lawn_size_sqft", 1000)): vol.All(
                vol.Coerce(int), vol.Range(min=100, max=100000)
            ),
        })

        return self.async_show_form(
            step_id="zone_settings",
            data_schema=data_schema,
            description_placeholders={
                "zone_name": current.get("yard_zone", "Zone"),
            }
        )

    async def async_step_weather(self, user_input=None) -> FlowResult:
        """Allow changing weather source."""
        if user_input is not None:
            new_data = {**self.config_entry.data}
            new_data["weather_entity"] = user_input.get("weather_entity", "")

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        weather_entities = _scan_weather_entities(self.hass)

        weather_options = [("", "None")] + weather_entities
        current_weather = self.config_entry.data.get("weather_entity", "")

        data_schema = vol.Schema({
            vol.Optional("weather_entity", default=current_weather): vol.In(
                {k: v for k, v in weather_options}
            ),
        })

        return self.async_show_form(
            step_id="weather",
            data_schema=data_schema,
        )

    async def async_step_grass(self, user_input=None) -> FlowResult:
        """Allow changing grass type."""
        if user_input is not None:
            new_data = {**self.config_entry.data}
            new_data["grass_type"] = user_input.get("grass_type", "Bermuda")

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)

            return self.async_create_entry(title="", data={})

        current_grass = self.config_entry.data.get("grass_type", "Bermuda")

        data_schema = vol.Schema({
            vol.Required("grass_type", default=current_grass): vol.In(GRASS_TYPE_LIST),
        })

        return self.async_show_form(
            step_id="grass",
            data_schema=data_schema,
        )
