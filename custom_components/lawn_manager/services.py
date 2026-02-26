import logging
from datetime import datetime
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
import uuid

from .const import DOMAIN, STORAGE_VERSION, CHEMICALS, EQUIPMENT_STORAGE_KEY, EQUIPMENT_TYPES

_LOGGER = logging.getLogger(__name__)


def _convert_oz_to_kitchen_measurements(oz):
    """Convert ounces to kitchen measurements for easier measuring."""
    cups = oz / 8.0
    tablespoons = oz * 2.0
    teaspoons = oz * 6.0

    conversions = {}

    if cups >= 0.125:
        if cups >= 1.0:
            conversions["cups"] = f"{round(cups, 2)} cups"
        elif cups >= 0.5:
            conversions["cups"] = f"{round(cups, 3)} cups"
        elif cups >= 0.25:
            try:
                conversions["cups"] = f"1/{int(1/cups)} cup"
            except (ZeroDivisionError, ValueError):
                conversions["cups"] = f"{round(cups, 3)} cups"
        else:
            conversions["cups"] = f"{round(cups, 3)} cups"

    if tablespoons >= 0.5:
        if tablespoons >= 1.0:
            conversions["tablespoons"] = f"{round(tablespoons, 1)} tbsp"
        else:
            conversions["tablespoons"] = f"{round(tablespoons, 2)} tbsp"

    if teaspoons >= 0.5 and tablespoons < 1.0:
        conversions["teaspoons"] = f"{round(teaspoons, 1)} tsp"

    return conversions


async def async_register_services(hass: HomeAssistant) -> None:
    """Register Lawn Manager services."""
    equipment_store = Store(hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)

    async def handle_add_equipment(call: ServiceCall):
        equipment_type = call.data.get("equipment_type", "sprayer")
        brand = call.data.get("brand", "Unknown")
        capacity = call.data.get("capacity", 1.0)
        capacity_unit = call.data.get("capacity_unit", "gallons")

        equipment_id = str(uuid.uuid4())[:8]

        equipment_data = await equipment_store.async_load() or {}

        equipment_data[equipment_id] = {
            "type": equipment_type,
            "brand": brand,
            "capacity": float(capacity),
            "capacity_unit": capacity_unit,
            "created": dt_util.now().strftime("%Y-%m-%d %H:%M:%S"),
            "friendly_name": f"{brand} {capacity} {capacity_unit.rstrip('s')} {equipment_type.title()}"
        }

        await equipment_store.async_save(equipment_data)
        _LOGGER.info("Equipment added: %s", equipment_data[equipment_id]["friendly_name"])

        from homeassistant.helpers.dispatcher import async_dispatcher_send
        async_dispatcher_send(hass, "lawn_manager_equipment_update")

    async def handle_delete_equipment(call: ServiceCall):
        equipment_id = call.data.get("equipment_id")
        if not equipment_id:
            _LOGGER.error("Equipment ID required")
            return

        equipment_data = await equipment_store.async_load() or {}

        if equipment_id in equipment_data:
            equipment_name = equipment_data[equipment_id].get("friendly_name", f"Equipment {equipment_id}")
            del equipment_data[equipment_id]
            await equipment_store.async_save(equipment_data)
            _LOGGER.info("Deleted equipment: %s (ID: %s)", equipment_name, equipment_id)

            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(hass, "lawn_manager_equipment_update")
        else:
            _LOGGER.error("Equipment ID '%s' not found", equipment_id)

    async def handle_calculate_application_rate(call: ServiceCall):
        """Calculate application rates based on equipment and zone."""
        chemical = call.data.get("chemical")
        equipment_name = call.data.get("equipment_name")
        zone = call.data.get("zone")

        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.error("No Lawn Manager config entries found")
            return {"error": "No Lawn Manager config entries found"}

        zone_config = None
        for entry in entries:
            if entry.data.get("yard_zone") == zone:
                zone_config = entry.data
                break

        if not zone_config:
            _LOGGER.error("Zone '%s' not found in config entries", zone)
            available_zones = [e.data.get("yard_zone", "?") for e in entries]
            return {"error": f"Zone '{zone}' not found. Available: {available_zones}"}

        lawn_size_sqft = zone_config.get("lawn_size_sqft", 1000)

        if not equipment_name:
            _LOGGER.error("Equipment name required")
            return {"error": "Equipment name required"}

        # Always load from storage for latest data
        equipment_data = await equipment_store.async_load() or {}
        equipment_id = None
        equipment = None

        for eq_id, eq_info in equipment_data.items():
            if eq_info.get("friendly_name") == equipment_name:
                equipment_id = eq_id
                equipment = eq_info
                break

        if not equipment:
            available_names = [eq_info.get("friendly_name", eq_id) for eq_id, eq_info in equipment_data.items()]
            _LOGGER.error("Equipment '%s' not found. Available: %s", equipment_name, available_names)
            return {"error": f"Equipment '{equipment_name}' not found. Available: {available_names}"}

        if not chemical:
            _LOGGER.error("Chemical required")
            return {"error": "Chemical required"}

        if chemical not in CHEMICALS:
            _LOGGER.error("Chemical '%s' not found", chemical)
            return {"error": f"Chemical '{chemical}' not found"}

        chemical_data = CHEMICALS[chemical]
        equipment_type = equipment["type"]
        chemical_notes = chemical_data.get("notes", "")

        calculation = {
            "chemical": chemical,
            "equipment": equipment["friendly_name"],
            "equipment_type": equipment_type,
            "zone": zone,
            "lawn_size_sqft": lawn_size_sqft,
            "chemical_notes": chemical_notes
        }

        if equipment_type == "sprayer":
            if "liquid_oz_per_1000sqft" in chemical_data:
                liquid_rate_per_1000sqft = chemical_data["liquid_oz_per_1000sqft"]
                total_chemical_needed_oz = (liquid_rate_per_1000sqft * lawn_size_sqft) / 1000

                if "water_gal_per_1000sqft" in chemical_data:
                    water_per_1000sqft = chemical_data["water_gal_per_1000sqft"]
                    total_water_needed_gal = (water_per_1000sqft * lawn_size_sqft) / 1000
                    concentration_per_gallon = liquid_rate_per_1000sqft / water_per_1000sqft
                    total_kitchen_measurements = _convert_oz_to_kitchen_measurements(total_chemical_needed_oz)

                    calculation.update({
                        "total_chemical_needed_oz": round(total_chemical_needed_oz, 3),
                        "total_chemical_kitchen_measurements": total_kitchen_measurements,
                        "total_water_needed_gal": round(total_water_needed_gal, 1),
                        "concentration_per_gallon": round(concentration_per_gallon, 3),
                        "application_rate": f"{liquid_rate_per_1000sqft} oz per 1,000 sq ft",
                        "water_rate": f"{water_per_1000sqft} gal per 1,000 sq ft"
                    })
                else:
                    total_kitchen_measurements = _convert_oz_to_kitchen_measurements(total_chemical_needed_oz)
                    calculation.update({
                        "total_chemical_needed_oz": round(total_chemical_needed_oz, 2),
                        "total_chemical_kitchen_measurements": total_kitchen_measurements,
                        "application_rate": f"{liquid_rate_per_1000sqft} oz per 1,000 sq ft"
                    })

            elif "amount_lb_per_1000sqft" in chemical_data:
                rate_per_1000sqft = chemical_data["amount_lb_per_1000sqft"]
                total_chemical_needed_lb = (rate_per_1000sqft * lawn_size_sqft) / 1000
                total_chemical_needed_oz = total_chemical_needed_lb * 16

                calculation.update({
                    "total_chemical_needed_lb": round(total_chemical_needed_lb, 2),
                    "total_chemical_needed_oz": round(total_chemical_needed_oz, 2),
                    "application_rate": f"{rate_per_1000sqft} lb per 1,000 sq ft (converted)"
                })

            equipment_capacity = equipment["capacity"]
            capacity_unit = equipment["capacity_unit"]

            if capacity_unit in ["gallons", "liters"]:
                if "total_water_needed_gal" in calculation:
                    water_needed = calculation["total_water_needed_gal"]
                else:
                    water_needed = lawn_size_sqft / 1000

                tanks_needed = water_needed / equipment_capacity

                if "total_chemical_needed_oz" in calculation:
                    if "concentration_per_gallon" in calculation:
                        chemical_per_tank_oz = calculation["concentration_per_gallon"] * equipment_capacity
                        kitchen_measurements = _convert_oz_to_kitchen_measurements(chemical_per_tank_oz)
                        concentration_kitchen = _convert_oz_to_kitchen_measurements(calculation["concentration_per_gallon"])

                        mixing_instruction = f"Mix {round(chemical_per_tank_oz, 3)} oz of {chemical} per {equipment_capacity} {capacity_unit} tank"
                        if kitchen_measurements:
                            kitchen_amounts = " or ".join(kitchen_measurements.values())
                            mixing_instruction += f" ({kitchen_amounts})"

                        per_gallon_instruction = f"{round(calculation['concentration_per_gallon'], 3)} oz per gallon"
                        if concentration_kitchen:
                            concentration_amounts = " or ".join(concentration_kitchen.values())
                            per_gallon_instruction += f" ({concentration_amounts} per gallon)"

                        calculation.update({
                            "tanks_needed": round(tanks_needed, 1),
                            "chemical_per_tank_oz": round(chemical_per_tank_oz, 3),
                            "kitchen_measurements_per_tank": kitchen_measurements,
                            "mixing_instructions": f"{mixing_instruction} - {per_gallon_instruction}"
                        })
                    else:
                        chemical_per_tank_oz = calculation["total_chemical_needed_oz"] / tanks_needed if tanks_needed > 0 else 0
                        kitchen_measurements = _convert_oz_to_kitchen_measurements(chemical_per_tank_oz)

                        mixing_instruction = f"Mix {round(chemical_per_tank_oz, 3)} oz of {chemical} per {equipment_capacity} {capacity_unit} tank"
                        if kitchen_measurements:
                            kitchen_amounts = " or ".join(kitchen_measurements.values())
                            mixing_instruction += f" ({kitchen_amounts})"

                        calculation.update({
                            "tanks_needed": round(tanks_needed, 1),
                            "chemical_per_tank_oz": round(chemical_per_tank_oz, 3),
                            "kitchen_measurements_per_tank": kitchen_measurements,
                            "mixing_instructions": mixing_instruction
                        })

        elif equipment_type == "spreader":
            if "amount_lb_per_1000sqft" in chemical_data:
                rate_per_1000sqft = chemical_data["amount_lb_per_1000sqft"]
                total_chemical_needed_lb = (rate_per_1000sqft * lawn_size_sqft) / 1000

                calculation.update({
                    "total_chemical_needed_lb": round(total_chemical_needed_lb, 2),
                    "application_rate": f"{rate_per_1000sqft} lb per 1,000 sq ft"
                })

                equipment_capacity = equipment["capacity"]
                capacity_unit = equipment["capacity_unit"]

                if capacity_unit in ["pounds", "kg"]:
                    loads_needed = total_chemical_needed_lb / equipment_capacity if equipment_capacity > 0 else 0
                    calculation.update({
                        "loads_needed": round(loads_needed, 1),
                        "application_instructions": f"Apply {round(total_chemical_needed_lb, 2)} lb total using {round(loads_needed, 1)} spreader loads"
                    })
                else:
                    calculation["error"] = f"Unsupported capacity unit '{capacity_unit}' for spreader."
            else:
                calculation["error"] = f"No granular rate available for {chemical} with spreader equipment"
        else:
            calculation["error"] = f"Unsupported equipment type '{equipment_type}'."

        _LOGGER.info("Application rate calculated: %s", calculation)
        hass.bus.async_fire(f"{DOMAIN}_rate_calculated", calculation)
        return calculation

    async def handle_get_equipment_options(call: ServiceCall):
        equipment_data = await equipment_store.async_load() or {}

        options = []
        for eq_id, eq_info in equipment_data.items():
            options.append({
                "value": eq_id,
                "label": eq_info.get("friendly_name", f"Equipment {eq_id}")
            })

        return {"equipment_options": options}

    async def handle_get_zone_options(call: ServiceCall):
        entries = hass.config_entries.async_entries(DOMAIN)

        zones = []
        for entry in entries:
            zone = entry.data.get("yard_zone", "Unknown Zone")
            lawn_size = entry.data.get("lawn_size_sqft", 1000)
            zones.append({
                "value": zone,
                "label": f"{zone} ({lawn_size} sq ft)"
            })

        return {"zone_options": zones}

    async def handle_list_calculation_options(call: ServiceCall):
        equipment_data = await equipment_store.async_load() or {}
        equipment_names = []
        for eq_id, eq_info in equipment_data.items():
            friendly_name = eq_info.get("friendly_name", f"Equipment {eq_id}")
            equipment_names.append(friendly_name)

        entries = hass.config_entries.async_entries(DOMAIN)
        zone_options = []
        for entry in entries:
            zone = entry.data.get("yard_zone", "Unknown Zone")
            lawn_size = entry.data.get("lawn_size_sqft", 1000)
            zone_options.append({
                "value": zone,
                "label": f"{zone} ({lawn_size} sq ft)"
            })

        response_data = {
            "equipment_names": equipment_names,
            "zone_options": zone_options,
            "usage": "Copy the exact Equipment Name and Zone Name for calculate_application_rate service"
        }

        return response_data

    async def handle_refresh_equipment_entity(call: ServiceCall):
        from homeassistant.helpers.dispatcher import async_dispatcher_send
        async_dispatcher_send(hass, "lawn_manager_equipment_update")

    async def handle_clear_equipment_storage(call: ServiceCall):
        equipment_data = await equipment_store.async_load() or {}
        _LOGGER.info("Clearing %d equipment entries", len(equipment_data))
        await equipment_store.async_remove()

    # Register all services
    if not hass.services.has_service(DOMAIN, "add_equipment"):
        hass.services.async_register(DOMAIN, "add_equipment", handle_add_equipment)
    if not hass.services.has_service(DOMAIN, "delete_equipment"):
        hass.services.async_register(DOMAIN, "delete_equipment", handle_delete_equipment)
    if not hass.services.has_service(DOMAIN, "get_equipment_options"):
        hass.services.async_register(DOMAIN, "get_equipment_options", handle_get_equipment_options, supports_response=True)
    if not hass.services.has_service(DOMAIN, "get_zone_options"):
        hass.services.async_register(DOMAIN, "get_zone_options", handle_get_zone_options, supports_response=True)
    if not hass.services.has_service(DOMAIN, "list_calculation_options"):
        hass.services.async_register(DOMAIN, "list_calculation_options", handle_list_calculation_options, supports_response=True)
    if not hass.services.has_service(DOMAIN, "refresh_equipment_entity"):
        hass.services.async_register(DOMAIN, "refresh_equipment_entity", handle_refresh_equipment_entity)
    if not hass.services.has_service(DOMAIN, "calculate_application_rate"):
        hass.services.async_register(DOMAIN, "calculate_application_rate", handle_calculate_application_rate, supports_response=True)
    if not hass.services.has_service(DOMAIN, "clear_equipment_storage"):
        hass.services.async_register(DOMAIN, "clear_equipment_storage", handle_clear_equipment_storage)
