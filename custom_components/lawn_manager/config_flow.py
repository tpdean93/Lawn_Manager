from homeassistant import config_entries
import voluptuous as vol
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.storage import Store
import uuid

from .const import DOMAIN, GRASS_TYPE_LIST, EQUIPMENT_TYPES, EQUIPMENT_BRANDS, CAPACITY_UNITS, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.user_data = {}
        self.equipment_list = []

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}

        if user_input is not None:
            # Store basic configuration data
            self.user_data = {
                "yard_zone": user_input["yard_zone"],
                "location": user_input["location"],
                "mow_interval": user_input["mow_interval"],
                "lawn_size_sqft": user_input["lawn_size_sqft"],
                "weather_entity": user_input.get("weather_entity"),
                "grass_type": user_input.get("grass_type", "Bermuda"),
            }
            # Move to equipment collection step
            return await self.async_step_equipment()

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
            vol.Required("lawn_size_sqft", default=1000): vol.All(vol.Coerce(int), vol.Range(min=100, max=100000)),
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
            errors=errors,
            description_placeholders={
                "step": "Step 1 of 3: Basic Configuration"
            }
        )

    async def async_step_equipment(self, user_input=None) -> FlowResult:
        """Handle equipment collection step."""
        errors = {}
        
        # Check if equipment already exists (from other zones)
        equipment_store = Store(self.hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
        existing_equipment = await equipment_store.async_load() or {}

        if user_input is not None:
            action = user_input.get("action")
            
            if action == "add_equipment":
                # Validate equipment fields when adding
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
                    # Add equipment to list
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
                    
                    # Show form again to add more equipment
                    return await self.async_step_equipment()
            elif action == "continue":
                # Skip validation when continuing without adding equipment
                return await self.async_step_final()

        # Build equipment form with conditional requirements
        equipment_schema = vol.Schema({
            vol.Optional("equipment_type"): vol.In(EQUIPMENT_TYPES),
            vol.Optional("brand"): str,
            vol.Optional("capacity"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1000)),
            vol.Optional("capacity_unit"): vol.In(CAPACITY_UNITS),
            vol.Required("action"): vol.In({
                "add_equipment": "Add this equipment and continue adding",
                "continue": "Skip adding equipment / Continue to next step"
            }),
        })

        # Create description showing current equipment
        equipment_list_text = ""
        
        # Show existing equipment from other zones if any
        if existing_equipment:
            equipment_list_text += "🔧 Equipment Available (shared across ALL zones):\n"
            for eq_id, eq_info in existing_equipment.items():
                equipment_list_text += f"• {eq_info.get('friendly_name', f'Equipment {eq_id}')}\n"
            equipment_list_text += "\n💡 TIP: Equipment is shared across all lawn zones. You can skip adding equipment and use what's already available!\n\n"
        
        equipment_list_text += "📦 Equipment being added in this setup:\n"
        if self.equipment_list:
            for eq in self.equipment_list:
                equipment_list_text += f"• {eq['friendly_name']}\n"
        else:
            equipment_list_text += "• None added yet\n"
        
        equipment_list_text += "\n📝 To add equipment: Fill out all fields above, then select 'Add this equipment'\n"
        equipment_list_text += "⏭️  To skip: Just select 'Skip adding equipment' (use existing equipment or add later)"

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
            # Create the integration entry with all collected data
            final_data = self.user_data.copy()
            final_data["equipment_list"] = self.equipment_list
            
            # Show restart prompt after successful setup
            return self.async_create_entry(
                title=self.user_data["yard_zone"],
                data=final_data
            )

        # Show final confirmation
        summary = f"Zone: {self.user_data['yard_zone']}\n"
        summary += f"Location: {self.user_data['location']}\n"
        summary += f"Lawn Size: {self.user_data['lawn_size_sqft']} sq ft\n"
        summary += f"Equipment: {len(self.equipment_list)} items\n"
        
        if self.equipment_list:
            for eq in self.equipment_list:
                summary += f"• {eq['friendly_name']}\n"
        
        summary += "\n⚠️  IMPORTANT: After setup completes, restart Home Assistant to enable equipment dropdowns in services!"

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
