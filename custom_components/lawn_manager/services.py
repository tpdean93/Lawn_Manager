import logging
from datetime import datetime
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
import uuid

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, CHEMICALS, EQUIPMENT_STORAGE_KEY, EQUIPMENT_TYPES

_LOGGER = logging.getLogger(__name__)

def _convert_oz_to_kitchen_measurements(oz):
    """Convert ounces to kitchen measurements for easier measuring."""
    # Conversion factors
    cups = oz / 8.0  # 8 oz = 1 cup
    tablespoons = oz * 2.0  # 1 oz = 2 tablespoons
    teaspoons = oz * 6.0  # 1 oz = 6 teaspoons
    
    conversions = {}
    
    # Add conversions based on practical amounts
    if cups >= 0.125:  # 1/8 cup or more
        if cups >= 1.0:
            conversions["cups"] = f"{round(cups, 2)} cups"
        elif cups >= 0.5:
            conversions["cups"] = f"{round(cups, 3)} cups"
        elif cups >= 0.25:
            conversions["cups"] = f"1/{int(1/cups)} cup"  # Show as fraction
        else:
            conversions["cups"] = f"{round(cups, 3)} cups"
    
    if tablespoons >= 0.5:  # 1/2 tablespoon or more
        if tablespoons >= 1.0:
            conversions["tablespoons"] = f"{round(tablespoons, 1)} tbsp"
        else:
            conversions["tablespoons"] = f"{round(tablespoons, 2)} tbsp"
    
    if teaspoons >= 0.5 and tablespoons < 1.0:  # Show teaspoons for small amounts
        conversions["teaspoons"] = f"{round(teaspoons, 1)} tsp"
    
    return conversions

async def async_register_services(hass: HomeAssistant) -> None:
    """Register Lawn Manager services."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    equipment_store = Store(hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)

    async def handle_log_mow(call: ServiceCall):
        """Handle log_mow service."""
        _LOGGER.info("🔧 log_mow called")
        data = await store.async_load() or {}
        now = dt_util.now().strftime("%Y-%m-%d")
        data["last_mow"] = now
        await store.async_save(data)
        _LOGGER.info("✅ Mow logged: %s", now)

    async def handle_log_application(call: ServiceCall):
        """Handle log_application service."""
        chemical = call.data.get("chemical")
        _LOGGER.info("🔧 log_application called for %s", chemical)

        data = await store.async_load() or {}
        now = dt_util.now().strftime("%Y-%m-%d")

        if "applications" not in data:
            data["applications"] = {}

        if chemical not in CHEMICALS:
            _LOGGER.warning("⚠️ Chemical '%s' not recognized — defaulting", chemical)
            interval = 30
            amount_lb = 1.0
            amount_oz = 16.0
        else:
            interval = CHEMICALS[chemical]["interval_days"]
            amount_lb = CHEMICALS[chemical]["amount_lb_per_1000sqft"]
            amount_oz = round(amount_lb * 16, 2)

        data["applications"][chemical] = {
            "last_applied": now,
            "interval_days": interval,
            "amount_lb_per_1000sqft": amount_lb,
            "amount_oz_per_1000sqft": amount_oz
        }

        await store.async_save(data)
        _LOGGER.info("✅ Application logged for %s on %s", chemical, now)

    async def handle_add_equipment(call: ServiceCall):
        """Add new equipment to inventory."""
        equipment_type = call.data.get("equipment_type", "sprayer")
        brand = call.data.get("brand", "Unknown")
        capacity = call.data.get("capacity", 1.0)
        capacity_unit = call.data.get("capacity_unit", "gallons")
        
        _LOGGER.info("🔧 add_equipment called: %s %s %s %s", equipment_type, brand, capacity, capacity_unit)
        
        # Generate unique ID for equipment
        equipment_id = str(uuid.uuid4())[:8]
        
        # Load existing equipment data
        equipment_data = await equipment_store.async_load() or {}
        
        # Add new equipment
        equipment_data[equipment_id] = {
            "type": equipment_type,
            "brand": brand,
            "capacity": float(capacity),
            "capacity_unit": capacity_unit,
            "created": dt_util.now().strftime("%Y-%m-%d %H:%M:%S"),
            "friendly_name": f"{brand} {capacity} {capacity_unit.rstrip('s')} {equipment_type.title()}"
        }
        
        await equipment_store.async_save(equipment_data)
        _LOGGER.info("✅ Equipment added: %s", equipment_data[equipment_id]["friendly_name"])
        
        # Trigger sensor update
        from homeassistant.helpers.dispatcher import async_dispatcher_send
        async_dispatcher_send(hass, "lawn_manager_equipment_update")

    async def handle_delete_equipment(call: ServiceCall):
        """Delete equipment by ID."""
        equipment_id = call.data.get("equipment_id")
        if not equipment_id:
            _LOGGER.error("❌ Equipment ID required")
            return
            
        equipment_data = await equipment_store.async_load() or {}
        
        if equipment_id in equipment_data:
            equipment_name = equipment_data[equipment_id].get("friendly_name", f"Equipment {equipment_id}")
            del equipment_data[equipment_id]
            await equipment_store.async_save(equipment_data)
            _LOGGER.info("✅ Deleted equipment: %s (ID: %s)", equipment_name, equipment_id)
            
            # Send equipment update signal
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(hass, "lawn_manager_equipment_update")
        else:
            _LOGGER.error("❌ Equipment ID '%s' not found", equipment_id)

    async def handle_calculate_application_rate(call: ServiceCall):
        """Calculate application rates based on equipment and zone."""
        chemical = call.data.get("chemical")
        equipment_name = call.data.get("equipment_name")
        zone = call.data.get("zone")
        
        # Find the config entry for the specified zone
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            _LOGGER.error("❌ No Lawn Manager config entries found")
            return
            
        # Find the matching zone config
        zone_config = None
        for entry in entries:
            if entry.data.get("yard_zone") == zone:
                zone_config = entry.data
                break
                
        if not zone_config:
            _LOGGER.error("❌ Zone '%s' not found in config entries", zone)
            return
            
        lawn_size_sqft = zone_config.get("lawn_size_sqft", 1000)
        
        # Find equipment by friendly name
        if not equipment_name:
            _LOGGER.error("❌ Equipment name required")
            return
            
        equipment_data = await equipment_store.async_load() or {}
        equipment_id = None
        equipment = None
        
        # Search for equipment by friendly name
        for eq_id, eq_info in equipment_data.items():
            if eq_info.get("friendly_name") == equipment_name:
                equipment_id = eq_id
                equipment = eq_info
                break
                
        if not equipment:
            _LOGGER.error("❌ Equipment '%s' not found. Available equipment:", equipment_name)
            for eq_id, eq_info in equipment_data.items():
                _LOGGER.error("   - %s", eq_info.get("friendly_name", f"Equipment {eq_id}"))
            return
        
        _LOGGER.info("🔧 calculate_application_rate called: %s, equipment: %s (ID: %s), zone: %s, lawn: %d sqft", 
                    chemical, equipment_name, equipment_id, zone, lawn_size_sqft)
        
        if not chemical:
            _LOGGER.error("❌ Chemical required")
            return
            
        # Get chemical data
        if chemical not in CHEMICALS:
            _LOGGER.error("❌ Chemical '%s' not found", chemical)
            return
            
        chemical_data = CHEMICALS[chemical]
        
        # Determine primary application method and calculate rates
        equipment_type = equipment["type"]
        chemical_notes = chemical_data.get("notes", "")
        
        # Initialize calculation data
        calculation = {
            "chemical": chemical,
            "equipment": equipment["friendly_name"],
            "equipment_type": equipment_type,
            "zone": zone,
            "lawn_size_sqft": lawn_size_sqft,
            "chemical_notes": chemical_notes
        }
        
        # Calculate based on equipment type and available chemical data
        if equipment_type == "sprayer":
            # Prefer liquid rates for sprayers
            if "liquid_oz_per_1000sqft" in chemical_data:
                # Use liquid application rate
                liquid_rate_per_1000sqft = chemical_data["liquid_oz_per_1000sqft"]
                total_chemical_needed_oz = (liquid_rate_per_1000sqft * lawn_size_sqft) / 1000
                
                # Special handling for T-Nex with water requirements
                if "water_gal_per_1000sqft" in chemical_data:
                    water_per_1000sqft = chemical_data["water_gal_per_1000sqft"]
                    total_water_needed_gal = (water_per_1000sqft * lawn_size_sqft) / 1000
                    
                    # For T-Nex: calculate concentration per gallon for easier mixing
                    concentration_per_gallon = liquid_rate_per_1000sqft / water_per_1000sqft
                    
                    # Add kitchen measurements for total chemical needed
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
                    # Add kitchen measurements for total chemical needed
                    total_kitchen_measurements = _convert_oz_to_kitchen_measurements(total_chemical_needed_oz)
                    
                    calculation.update({
                        "total_chemical_needed_oz": round(total_chemical_needed_oz, 2),
                        "total_chemical_kitchen_measurements": total_kitchen_measurements,
                        "application_rate": f"{liquid_rate_per_1000sqft} oz per 1,000 sq ft"
                    })
                    
            elif "amount_lb_per_1000sqft" in chemical_data:
                # Fall back to granular rate converted to liquid
                rate_per_1000sqft = chemical_data["amount_lb_per_1000sqft"]
                total_chemical_needed_lb = (rate_per_1000sqft * lawn_size_sqft) / 1000
                total_chemical_needed_oz = total_chemical_needed_lb * 16
                
                calculation.update({
                    "total_chemical_needed_lb": round(total_chemical_needed_lb, 2),
                    "total_chemical_needed_oz": round(total_chemical_needed_oz, 2),
                    "application_rate": f"{rate_per_1000sqft} lb per 1,000 sq ft (converted)"
                })
            
            # Calculate tank mixing for sprayers
            equipment_capacity = equipment["capacity"]
            capacity_unit = equipment["capacity_unit"]
            
            if capacity_unit in ["gallons", "liters"]:
                # Calculate tank requirements
                if "total_water_needed_gal" in calculation:
                    # Use specific water requirement (like T-Nex)
                    water_needed = calculation["total_water_needed_gal"]
                else:
                    # Default: 1 gallon per 1000 sqft
                    water_needed = lawn_size_sqft / 1000
                
                tanks_needed = water_needed / equipment_capacity
                
                if "total_chemical_needed_oz" in calculation:
                    if "concentration_per_gallon" in calculation:
                        # Use concentration for chemicals like T-Nex
                        chemical_per_tank_oz = calculation["concentration_per_gallon"] * equipment_capacity
                        
                        # Add kitchen measurements for easier measuring
                        kitchen_measurements = _convert_oz_to_kitchen_measurements(chemical_per_tank_oz)
                        concentration_kitchen = _convert_oz_to_kitchen_measurements(calculation["concentration_per_gallon"])
                        
                        # Build mixing instruction with kitchen measurements
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
                        # Standard calculation for other chemicals
                        chemical_per_tank_oz = calculation["total_chemical_needed_oz"] / tanks_needed if tanks_needed > 0 else 0
                        
                        # Add kitchen measurements
                        kitchen_measurements = _convert_oz_to_kitchen_measurements(chemical_per_tank_oz)
                        
                        # Build mixing instruction with kitchen measurements
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
            # Use granular rates for spreaders
            if "amount_lb_per_1000sqft" in chemical_data:
                rate_per_1000sqft = chemical_data["amount_lb_per_1000sqft"]
                total_chemical_needed_lb = (rate_per_1000sqft * lawn_size_sqft) / 1000
                
                calculation.update({
                    "total_chemical_needed_lb": round(total_chemical_needed_lb, 2),
                    "application_rate": f"{rate_per_1000sqft} lb per 1,000 sq ft"
                })
                
                # Calculate spreader loads
                equipment_capacity = equipment["capacity"]
                capacity_unit = equipment["capacity_unit"]
                
                if capacity_unit in ["pounds", "kg"]:
                    loads_needed = total_chemical_needed_lb / equipment_capacity if equipment_capacity > 0 else 0
                    
                    calculation.update({
                        "loads_needed": round(loads_needed, 1),
                        "application_instructions": f"Apply {round(total_chemical_needed_lb, 2)} lb total using {round(loads_needed, 1)} spreader loads"
                    })
                else:
                    calculation["error"] = f"Unsupported capacity unit '{capacity_unit}' for spreader. Expected pounds or kg."
            else:
                calculation["error"] = f"No granular rate available for {chemical} with spreader equipment"
        else:
            calculation["error"] = f"Unsupported equipment type '{equipment_type}'. Expected sprayer or spreader."
        
        _LOGGER.info("✅ Application rate calculated: %s", calculation)
        
        # Fire event with calculation results
        hass.bus.async_fire(f"{DOMAIN}_rate_calculated", calculation)
        
        # Return calculation results as response
        return calculation

    async def handle_get_equipment_options(call: ServiceCall):
        """Get equipment options for dropdown."""
        equipment_data = await equipment_store.async_load() or {}
        
        options = []
        for eq_id, eq_info in equipment_data.items():
            options.append({
                "value": eq_id,
                "label": eq_info.get("friendly_name", f"Equipment {eq_id}")
            })
        
        _LOGGER.info("📋 Equipment options: %s", options)
        return {"equipment_options": options}

    async def handle_get_zone_options(call: ServiceCall):
        """Get zone options for dropdown."""
        entries = hass.config_entries.async_entries(DOMAIN)
        
        zones = []
        for entry in entries:
            zone = entry.data.get("yard_zone", "Unknown Zone")
            lawn_size = entry.data.get("lawn_size_sqft", 1000)
            zones.append({
                "value": zone,
                "label": f"{zone} ({lawn_size} sq ft)"
            })
        
        _LOGGER.info("📋 Zone options: %s", zones)
        return {"zone_options": zones}

    async def handle_list_calculation_options(call: ServiceCall):
        """List all available equipment and zones for calculation service."""
        
        # Get equipment
        equipment_data = await equipment_store.async_load() or {}
        equipment_names = []
        for eq_id, eq_info in equipment_data.items():
            friendly_name = eq_info.get("friendly_name", f"Equipment {eq_id}")
            equipment_names.append(friendly_name)
        
        # Get zones
        entries = hass.config_entries.async_entries(DOMAIN)
        zone_names = []
        for entry in entries:
            zone = entry.data.get("yard_zone", "Unknown Zone")
            zone_names.append(zone)
        
        # Return response data
        response_data = {
            "equipment_names": equipment_names,
            "zone_names": zone_names,
            "usage": "Copy the exact Equipment Name and Zone Name for calculate_application_rate service"
        }
        
        _LOGGER.info("📋 Available options: Equipment=%s, Zones=%s", equipment_names, zone_names)
        return response_data

    async def handle_refresh_equipment_entity(call: ServiceCall):
        """Force refresh the Equipment Selection entity and rebuild entities as needed."""
        _LOGGER.info("🔄 Refreshing Equipment Selection entity...")
        
        # Send equipment update signal to refresh all equipment-related entities
        from homeassistant.helpers.dispatcher import async_dispatcher_send
        async_dispatcher_send(hass, "lawn_manager_equipment_update")
        
        # Also trigger entity reload to switch between Method/Equipment entities
        _LOGGER.info("💡 Note: To switch between Application Method and Equipment Selection entities, reload the integration")
        _LOGGER.info("✅ Equipment update signal sent")

    async def handle_clear_equipment_storage(call: ServiceCall):
        """Clear all equipment storage - for debugging only."""
        equipment_data = await equipment_store.async_load() or {}
        _LOGGER.info("Clearing %d equipment entries", len(equipment_data))
        await equipment_store.async_remove()
        _LOGGER.info("✅ Equipment storage cleared")

    # Register all services
    hass.services.async_register(DOMAIN, "log_mow", handle_log_mow)
    hass.services.async_register(DOMAIN, "log_application", handle_log_application)
    hass.services.async_register(DOMAIN, "add_equipment", handle_add_equipment)
    hass.services.async_register(DOMAIN, "delete_equipment", handle_delete_equipment)
    hass.services.async_register(DOMAIN, "get_equipment_options", handle_get_equipment_options, supports_response=True)
    hass.services.async_register(DOMAIN, "get_zone_options", handle_get_zone_options, supports_response=True)
    hass.services.async_register(DOMAIN, "list_calculation_options", handle_list_calculation_options, supports_response=True)
    hass.services.async_register(DOMAIN, "refresh_equipment_entity", handle_refresh_equipment_entity)
    hass.services.async_register(DOMAIN, "calculate_application_rate", handle_calculate_application_rate, supports_response=True)
    hass.services.async_register(DOMAIN, "clear_equipment_storage", handle_clear_equipment_storage)
