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


def _get_weather_entities(hass):
    """Get standard weather.* entities for conditions (cloudy, rainy, etc.)."""
    entities = []
    for entity_id in hass.states.async_entity_ids("weather"):
        state = hass.states.get(entity_id)
        if state:
            friendly_name = state.attributes.get("friendly_name", entity_id)
            entities.append((entity_id, friendly_name))
    return entities


def _get_rain_sensor_entities(hass):
    """Find rain/precipitation sensor entities from weather station devices."""
    from homeassistant.helpers import entity_registry as er, device_registry as dr

    entities = []
    try:
        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)
    except Exception:
        return entities

    # Find weather station devices
    weather_device_ids = set()
    for device in dev_reg.devices.values():
        searchable = " ".join([
            (device.name or ""), (device.name_by_user or ""),
            (device.manufacturer or ""), (device.model or ""),
        ]).lower()
        if "weather" in searchable:
            weather_device_ids.add(device.id)

    # Find rain/precipitation sensors on those devices
    for entry in ent_reg.entities.values():
        if entry.device_id not in weather_device_ids:
            continue
        if entry.domain != "sensor" or entry.disabled:
            continue

        eid_lower = entry.entity_id.lower()
        name_lower = (entry.original_name or entry.name or "").lower()
        dev_class = entry.original_device_class or entry.device_class or ""

        is_rain = (
            dev_class in ("precipitation", "precipitation_intensity")
            or "rain" in eid_lower or "rain" in name_lower
            or "precip" in eid_lower
        )
        # Skip cumulative rain totals, only want current/hourly
        is_cumulative = any(x in eid_lower for x in ["daily", "weekly", "monthly", "yearly", "total", "event"])

        if is_rain and not is_cumulative:
            friendly_name = entry.original_name or entry.name or entry.entity_id
            device = dev_reg.async_get(entry.device_id)
            dev_name = (device.name_by_user or device.name or "") if device else ""
            label = f"{dev_name}: {friendly_name}" if dev_name else friendly_name
            entities.append((entry.entity_id, label))

    return entities


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
                "rain_sensor": user_input.get("rain_sensor"),
                "grass_type": user_input.get("grass_type", "Bermuda"),
            }

            if self.user_data["grass_type"] == "Custom":
                return await self.async_step_custom_grass()
            return await self.async_step_equipment()

        weather_entities = _get_weather_entities(self.hass)
        rain_sensors = _get_rain_sensor_entities(self.hass)

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

        if rain_sensors:
            rain_options = [("", "None (use forecast data)")] + rain_sensors
            schema_dict[vol.Optional("rain_sensor", default="")] = vol.In({k: v for k, v in rain_options})

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={"step": "Step 1 of 3: Basic Configuration"}
        )

    async def async_step_custom_grass(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            self.user_data["custom_grass_name"] = user_input["custom_grass_name"]
            self.user_data["custom_grass_season"] = user_input["custom_grass_season"]
            self.user_data["grass_type"] = f"Custom: {user_input['custom_grass_name']} ({user_input['custom_grass_season']})"
            return await self.async_step_equipment()

        return self.async_show_form(
            step_id="custom_grass",
            data_schema=vol.Schema({
                vol.Required("custom_grass_name"): str,
                vol.Required("custom_grass_season"): vol.In({
                    "warm": "Warm Season", "cool": "Cool Season",
                    "transition": "Transition Zone (Both)"
                })
            }),
            errors=errors,
            description_placeholders={"example": "Examples: Kikuyu, Buffalo Grass, Seashore Paspalum, etc."}
        )

    async def async_step_equipment(self, user_input=None) -> FlowResult:
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
                    self.equipment_list.append({
                        "id": equipment_id,
                        "type": user_input["equipment_type"],
                        "brand": user_input["brand"],
                        "capacity": float(user_input["capacity"]),
                        "capacity_unit": user_input["capacity_unit"],
                        "friendly_name": f"{user_input['brand']} {user_input['capacity']} {user_input['capacity_unit'].rstrip('s')} {user_input['equipment_type'].title()}"
                    })
                    return await self.async_step_equipment()
            elif action == "continue":
                return await self.async_step_final()
            elif action == "add_new":
                return await self.async_step_add_equipment()

        # Simplified view for zones with existing equipment
        if has_existing and not self.equipment_list:
            equip_names = [eq_info.get('friendly_name', eq_id) for eq_id, eq_info in existing_equipment.items()]
            equip_text = "Your equipment:\n" + "".join(f"  - {n}\n" for n in equip_names)
            equip_text += "\nEquipment is shared across all zones."
            return self.async_show_form(
                step_id="equipment",
                data_schema=vol.Schema({
                    vol.Required("action", default="continue"): vol.In({
                        "continue": "Use existing equipment - Continue",
                        "add_new": "Add more equipment",
                    }),
                }),
                errors=errors,
                description_placeholders={"step": "Step 2 of 3: Equipment Setup", "equipment_list": equip_text}
            )

        # Full add form
        equipment_list_text = ""
        if existing_equipment:
            equipment_list_text += "Existing equipment:\n"
            for eq_id, eq_info in existing_equipment.items():
                equipment_list_text += f"  - {eq_info.get('friendly_name', eq_id)}\n"
        equipment_list_text += "New equipment:\n"
        if self.equipment_list:
            for eq in self.equipment_list:
                equipment_list_text += f"  - {eq['friendly_name']}\n"
        else:
            equipment_list_text += "  None added yet\n"

        return self.async_show_form(
            step_id="equipment",
            data_schema=vol.Schema({
                vol.Optional("equipment_type"): vol.In(EQUIPMENT_TYPES),
                vol.Optional("brand"): str,
                vol.Optional("capacity"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1000)),
                vol.Optional("capacity_unit"): vol.In(CAPACITY_UNITS),
                vol.Required("action"): vol.In({
                    "add_equipment": "Add this equipment and continue adding",
                    "continue": "Done adding equipment / Continue",
                }),
            }),
            errors=errors,
            description_placeholders={"step": "Step 2 of 3: Equipment Setup", "equipment_list": equipment_list_text}
        )

    async def async_step_add_equipment(self, user_input=None) -> FlowResult:
        return await self.async_step_equipment()

    async def async_step_final(self, user_input=None) -> FlowResult:
        if user_input is not None:
            final_data = self.user_data.copy()
            final_data["equipment_list"] = self.equipment_list
            return self.async_create_entry(title=self.user_data["yard_zone"], data=final_data)

        mow_interval = self.user_data['mow_interval']
        mow_label = MOW_INTERVAL_OPTIONS.get(mow_interval, f"Every {mow_interval} days")
        summary = (
            f"Zone: {self.user_data['yard_zone']}\n"
            f"Location: {self.user_data['location']}\n"
            f"Lawn Size: {self.user_data['lawn_size_sqft']} sq ft\n"
            f"Mowing Schedule: {mow_label}\n"
            f"Grass Type: {self.user_data.get('grass_type', 'Bermuda')}\n"
            f"Equipment: {len(self.equipment_list)} new items\n"
        )
        for eq in self.equipment_list:
            summary += f"  - {eq['friendly_name']}\n"

        return self.async_show_form(
            step_id="final",
            data_schema=vol.Schema({vol.Required("confirm", default=True): bool}),
            description_placeholders={"step": "Step 3 of 3: Confirmation", "summary": summary}
        )


class OptionsFlow(config_entries.OptionsFlow):
    """Handle reconfigure options for a zone."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Show reconfigure form with all editable settings."""
        if user_input is not None:
            mow_interval = user_input.get("mow_interval", "7")
            if isinstance(mow_interval, str):
                mow_interval = int(mow_interval)

            new_data = {**self.config_entry.data}
            new_data["location"] = user_input.get("location", new_data.get("location", ""))
            new_data["mow_interval"] = mow_interval
            new_data["lawn_size_sqft"] = user_input.get("lawn_size_sqft", new_data.get("lawn_size_sqft", 1000))
            new_data["grass_type"] = user_input.get("grass_type", new_data.get("grass_type", "Bermuda"))
            new_data["weather_entity"] = user_input.get("weather_entity", new_data.get("weather_entity", ""))
            new_data["rain_sensor"] = user_input.get("rain_sensor", new_data.get("rain_sensor", ""))

            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        current = self.config_entry.data
        weather_entities = _get_weather_entities(self.hass)
        rain_sensors = _get_rain_sensor_entities(self.hass)

        schema_dict = {
            vol.Required("location", default=current.get("location", "")): str,
            vol.Required("mow_interval", default=str(current.get("mow_interval", 7))): vol.In(
                {str(k): v for k, v in MOW_INTERVAL_OPTIONS.items()}
            ),
            vol.Required("lawn_size_sqft", default=current.get("lawn_size_sqft", 1000)): vol.All(
                vol.Coerce(int), vol.Range(min=100, max=100000)
            ),
            vol.Required("grass_type", default=current.get("grass_type", "Bermuda")): vol.In(GRASS_TYPE_LIST),
        }

        if weather_entities:
            weather_options = [("", "None")] + weather_entities
            schema_dict[vol.Optional("weather_entity", default=current.get("weather_entity", ""))] = vol.In(
                {k: v for k, v in weather_options}
            )

        if rain_sensors:
            rain_options = [("", "None (use forecast data)")] + rain_sensors
            schema_dict[vol.Optional("rain_sensor", default=current.get("rain_sensor", ""))] = vol.In(
                {k: v for k, v in rain_options}
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"zone_name": current.get("yard_zone", "Zone")}
        )
