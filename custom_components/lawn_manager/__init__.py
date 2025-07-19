from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import async_dispatcher_send
import asyncio
import logging

from .const import DOMAIN, CHEMICALS, EQUIPMENT_STORAGE_KEY, get_storage_key, PLATFORMS

_LOGGER = logging.getLogger(__name__)
STORAGE_KEY = "lawn_manager_data"
STORAGE_VERSION = 1


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Lawn Manager integration from configuration.yaml (legacy use)."""
    return True


async def _update_services_yaml_with_user_data(hass: HomeAssistant, entry: ConfigEntry):
    """Update services.yaml with user's specific equipment and zones."""
    import os
    import yaml
    
    # Get all lawn manager entries to collect all zones
    entries = hass.config_entries.async_entries(DOMAIN)
    
    # Collect all equipment from this entry
    equipment_options = []
    if "equipment_list" in entry.data:
        for equipment in entry.data["equipment_list"]:
            equipment_options.append(equipment["friendly_name"])
    
    # Collect all zones from all entries
    zone_options = []
    for config_entry in entries:
        zone = config_entry.data.get("yard_zone", "Unknown Zone")
        if zone not in zone_options:
            zone_options.append(zone)
    
    # Only update if we have user data
    if not equipment_options and not zone_options:
        return
        
    # Path to services.yaml
    services_yaml_path = os.path.join(os.path.dirname(__file__), "services.yaml")
    
    def _update_services_file():
        """Update services file synchronously in executor."""
        try:
            # Read current services.yaml
            with open(services_yaml_path, 'r', encoding='utf-8') as file:
                services_data = yaml.safe_load(file)
            
            # Update calculate_application_rate service if it exists
            if "calculate_application_rate" in services_data:
                fields = services_data["calculate_application_rate"].get("fields", {})
                
                # Update equipment field if we have equipment
                if equipment_options and "equipment_name" in fields:
                    fields["equipment_name"]["selector"] = {
                        "select": {
                            "options": equipment_options,
                            "custom_value": True
                        }
                    }
                    _LOGGER.info("Updated services.yaml with %d equipment options", len(equipment_options))
                
                # Update zone field if we have zones
                if zone_options and "zone" in fields:
                    fields["zone"]["selector"] = {
                        "select": {
                            "options": zone_options,
                            "custom_value": True
                        }
                    }
                    _LOGGER.info("Updated services.yaml with %d zone options", len(zone_options))
            
            # Write updated services.yaml
            with open(services_yaml_path, 'w', encoding='utf-8') as file:
                yaml.dump(services_data, file, default_flow_style=False, sort_keys=False, allow_unicode=True)
                
            _LOGGER.info("✅ Services.yaml updated with user-specific options")
            return True
            
        except Exception as e:
            _LOGGER.warning("Failed to update services.yaml: %s", e)
            return False
    
    # Run the file operations in executor to avoid blocking
    await hass.async_add_executor_job(_update_services_file)


async def _store_equipment_from_config(hass: HomeAssistant, entry: ConfigEntry):
    """Store equipment from config flow into equipment storage."""
    if "equipment_list" not in entry.data:
        return
        
    equipment_store = Store(hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
    equipment_data = await equipment_store.async_load() or {}
    
    # Add each equipment from config flow
    for equipment in entry.data["equipment_list"]:
        equipment_id = equipment["id"]
        equipment_data[equipment_id] = {
            "type": equipment["type"],
            "brand": equipment["brand"],
            "capacity": equipment["capacity"],
            "capacity_unit": equipment["capacity_unit"],
            "friendly_name": equipment["friendly_name"],
            "created": dt_util.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "config_flow"
        }
        _LOGGER.info("Stored equipment from config: %s", equipment["friendly_name"])
    
    await equipment_store.async_save(equipment_data)
    
    # Trigger equipment update signal
    async_dispatcher_send(hass, "lawn_manager_equipment_update")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lawn Manager from a config entry."""
    _LOGGER.info("Setting up Lawn Manager entry: %s", entry.title)

    # Store equipment from config flow if provided
    await _store_equipment_from_config(hass, entry)
    
    # Update services.yaml with user's equipment and zones if provided
    await _update_services_yaml_with_user_data(hass, entry)

    # Register services
    await _register_services(hass)
    
    # Register equipment services from services.py
    from .services import async_register_services
    await async_register_services(hass)

    # Ensure storage is initialized with default data before loading entities
    storage_key = get_storage_key(entry.entry_id)
    store = Store(hass, 1, storage_key)
    data = await store.async_load() or {}
    
    # Initialize default data structure if first time
    if not data:
        data = {
            "last_mow": None,
            "mowing_history": [],
            "applications": {}  # Changed from list to dictionary
        }
        await store.async_save(data)
        _LOGGER.info("✅ Initialized storage for new zone: %s", entry.title)

    # Forward setup to all platforms
    _LOGGER.info("🔧 Setting up platforms for %s: %s", entry.title, PLATFORMS)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _LOGGER.info("✅ All platforms setup complete for %s", entry.title)
    except Exception as err:
        _LOGGER.error("❌ Failed to set up platforms: %s", err)
        raise
    
    # Small delay to ensure all platforms are ready
    await asyncio.sleep(0.2)
    
    # Trigger initial update signal to ensure all entities get their data
    async_dispatcher_send(hass, f"lawn_manager_update_{entry.entry_id}")
    
    _LOGGER.info("✅ Lawn Manager setup complete for %s", entry.title)
    return True


async def _register_services(hass: HomeAssistant):
    """Register custom services for Lawn Manager."""

    async def handle_log_lawn_activity(call: ServiceCall):
        """Handle logging a lawn activity."""
        application_date = call.data.get("application_date")
        cut_type = call.data.get("cut_type", "Regular Maintenance")
        height_of_cut = call.data.get("height_of_cut")
        zone_entry_id = call.data.get("_zone_entry_id") or call.data.get("zone")
        
        _LOGGER.warning("🔍 SERVICE - Received: cut_type=%s, height_of_cut=%s, zone=%s", 
                       cut_type, height_of_cut, zone_entry_id)
        
        if not zone_entry_id:
            _LOGGER.error("❌ No zone entry ID provided - cannot determine which zone to update")
            _LOGGER.error("ℹ️ When using the service directly, you must provide the _zone_entry_id parameter")
            _LOGGER.error("ℹ️ Your zone ID can be found in Configuration > Integrations > Lawn Manager > Configure")
            return
            
        # Verify zone exists
        entries = hass.config_entries.async_entries(DOMAIN)
        zone_exists = any(entry.entry_id == zone_entry_id for entry in entries)
        if not zone_exists:
            _LOGGER.error("❌ Invalid zone ID: %s - zone not found", zone_entry_id)
            _LOGGER.error("ℹ️ Available zones:")
            for entry in entries:
                _LOGGER.error("  - %s (%s)", entry.title, entry.entry_id)
            return
            
        # Use zone-specific storage
        zone_storage_key = get_storage_key(zone_entry_id)
        store = Store(hass, STORAGE_VERSION, zone_storage_key)
        data = await store.async_load() or {}
        
        # Use provided date or default to today
        if application_date:
            # Validate the date (same validation as chemical application)
            try:
                from datetime import datetime, timedelta
                provided_date = datetime.strptime(application_date, "%Y-%m-%d").date()
                today = dt_util.now().date()
                
                # Check if date is in the future
                if provided_date > today:
                    _LOGGER.error("❌ Cannot log lawn activity for future date: %s", application_date)
                    return
                
                # Check if date is more than 1 year ago
                one_year_ago = today - timedelta(days=365)
                if provided_date < one_year_ago:
                    _LOGGER.error("❌ Cannot log lawn activity for date more than 1 year ago: %s", application_date)
                    return
                
                mow_date_str = application_date
            except ValueError:
                _LOGGER.error("❌ Invalid date format: %s. Using today's date.", application_date)
                mow_date_str = dt_util.now().strftime("%Y-%m-%d")
        else:
            mow_date_str = dt_util.now().strftime("%Y-%m-%d")
        
        # Store enhanced mowing data
        data["last_mow"] = mow_date_str
        
        # Initialize mowing_history if it doesn't exist
        if "mowing_history" not in data:
            data["mowing_history"] = []
        
        # Create detailed mowing record
        mow_record = {
            "date": mow_date_str,
            "cut_type": cut_type,
            "timestamp": dt_util.now().isoformat()
        }
        
        # Add height of cut if provided
        if height_of_cut is not None:
            mow_record["height_of_cut_inches"] = float(height_of_cut)
        
        # Add to history (keep last 50 records to prevent storage bloat)
        data["mowing_history"].append(mow_record)
        if len(data["mowing_history"]) > 50:
            data["mowing_history"] = data["mowing_history"][-50:]
        
        await store.async_save(data)
        _LOGGER.info("✅ Lawn Activity logged: %s (%s%s)", mow_date_str, cut_type, 
                    f" at {height_of_cut}\"" if height_of_cut else "")

        # Notify sensors to update with zone-specific signal
        signal_name = f"lawn_manager_update_{zone_entry_id}"
        async_dispatcher_send(hass, signal_name)
        _LOGGER.info("✅ Sent update signal for zone: %s", zone_entry_id)

    async def handle_log_application(call: ServiceCall):
        """Handle logging a chemical application."""
        selected = call.data.get("chemical_select")
        custom = call.data.get("custom_chemical")
        method = call.data.get("method", "Unknown")
        rate_override = call.data.get("rate_override", "Default")
        custom_rate = call.data.get("custom_rate", "1.0")
        application_date = call.data.get("application_date")
        zone_entry_id = call.data.get("_zone_entry_id")

        chemical = custom.strip() if custom else selected

        if not chemical:
            _LOGGER.error("❌ No chemical name provided.")
            return
            
        if not zone_entry_id:
            _LOGGER.error("❌ No zone entry ID provided - cannot determine which zone to update")
            return

        _LOGGER.info("🔧 log_application called for %s via %s with rate override: %s, custom_rate: %s, date: %s, zone: %s", chemical, method, rate_override, custom_rate, application_date, zone_entry_id)

        # Use zone-specific storage
        zone_storage_key = get_storage_key(zone_entry_id)
        store = Store(hass, STORAGE_VERSION, zone_storage_key)
        data = await store.async_load() or {}
        
        # Use provided date or default to today
        if application_date:
            # application_date comes as a string in YYYY-MM-DD format
            # Validate the date
            try:
                from datetime import datetime, timedelta
                provided_date = datetime.strptime(application_date, "%Y-%m-%d").date()
                today = dt_util.now().date()
                
                # Check if date is in the future
                if provided_date > today:
                    _LOGGER.error("❌ Cannot log application for future date: %s", application_date)
                    return
                
                # Check if date is more than 1 year ago
                one_year_ago = today - timedelta(days=365)
                if provided_date < one_year_ago:
                    _LOGGER.error("❌ Cannot log application for date more than 1 year ago: %s", application_date)
                    return
                
                application_date_str = application_date
            except ValueError:
                _LOGGER.error("❌ Invalid date format: %s. Using today's date.", application_date)
                application_date_str = dt_util.now().strftime("%Y-%m-%d")
        else:
            application_date_str = dt_util.now().strftime("%Y-%m-%d")

        # Ensure applications is a dictionary
        if "applications" not in data:
            data["applications"] = {}
        elif isinstance(data["applications"], list):
            # Convert old list format to dictionary
            _LOGGER.warning("Converting old applications list format to dictionary")
            applications = {app.get("chemical_name", f"Chemical {i}"): app 
                          for i, app in enumerate(data["applications"]) if isinstance(app, dict)}
            data["applications"] = applications

        # Get zone configuration for lawn size
        entries = hass.config_entries.async_entries(DOMAIN)
        zone_config = None
        for entry in entries:
            if entry.entry_id == zone_entry_id:
                zone_config = entry.data
                break
                
        if not zone_config:
            _LOGGER.error("❌ Zone configuration not found for entry ID: %s", zone_entry_id)
            return
            
        lawn_size_sqft = zone_config.get("lawn_size_sqft", 1000)
        yard_zone = zone_config.get("yard_zone", "Unknown Zone")

        # Get default rates and determine application method
        if chemical not in CHEMICALS:
            _LOGGER.warning("⚠️ '%s' is not in the predefined chemical list. Logging anyway.", chemical)
            interval = 30
            default_amount_lb = 1.0
            default_amount_oz = 16.0
            is_liquid_application = False
        else:
            chemical_data = CHEMICALS[chemical]
            interval = chemical_data["interval_days"]
            
            # Determine if this is liquid or granular application based on method and available data
            is_liquid_application = (method.lower() == "sprayer" and "liquid_oz_per_1000sqft" in chemical_data)
            
            if is_liquid_application:
                # Use liquid application rates
                default_amount_oz_per_1000 = chemical_data["liquid_oz_per_1000sqft"]
                default_amount_lb_per_1000 = default_amount_oz_per_1000 / 16.0  # Convert to lb equivalent
                default_amount_lb = default_amount_lb_per_1000
                default_amount_oz = default_amount_oz_per_1000
                _LOGGER.info("🧪 Using LIQUID application: %s oz per 1000 sqft", default_amount_oz_per_1000)
            else:
                # Use granular application rates
                default_amount_lb_per_1000 = chemical_data.get("amount_lb_per_1000sqft", 1.0)
                default_amount_lb = default_amount_lb_per_1000
                default_amount_oz = round(default_amount_lb * 16, 2)
                _LOGGER.info("🌾 Using GRANULAR application: %s lb per 1000 sqft", default_amount_lb_per_1000)

        # Calculate actual applied rate based on override
        if rate_override == "Default":
            rate_multiplier = 1.0
            rate_description = "Default"
        elif rate_override == "Light (50%)":
            rate_multiplier = 0.5
            rate_description = "Light (50%)"
        elif rate_override == "Heavy (150%)":
            rate_multiplier = 1.5
            rate_description = "Heavy (150%)"
        elif rate_override == "Extra Heavy (200%)":
            rate_multiplier = 2.0
            rate_description = "Extra Heavy (200%)"
        elif rate_override == "Custom":
            try:
                # If custom_rate is empty, default to 1.0
                if not custom_rate or custom_rate.strip() == "":
                    rate_multiplier = 1.0
                    rate_description = "Custom (1.0x)"
                else:
                    rate_multiplier = float(custom_rate)
                    rate_description = f"Custom ({rate_multiplier}x)"
            except ValueError:
                _LOGGER.error("❌ Invalid custom rate value: %s. Using default.", custom_rate)
                rate_multiplier = 1.0
                rate_description = "Default (Invalid Custom)"
        else:
            rate_multiplier = 1.0
            rate_description = "Default"

        # Calculate final amounts per 1000 sqft based on rate override
        if is_liquid_application:
            # For liquid applications, work in ounces
            applied_amount_oz_per_1000 = default_amount_oz * rate_multiplier
            applied_amount_lb_per_1000 = applied_amount_oz_per_1000 / 16.0
            
            # Calculate total amounts needed for this zone
            total_chemical_needed_oz = (applied_amount_oz_per_1000 * lawn_size_sqft) / 1000
            total_chemical_needed_lb = total_chemical_needed_oz / 16.0
        else:
            # For granular applications, work in pounds
            applied_amount_lb_per_1000 = default_amount_lb * rate_multiplier
            applied_amount_oz_per_1000 = round(applied_amount_lb_per_1000 * 16, 2)
            
            # Calculate total amounts needed for this zone
            total_chemical_needed_lb = (applied_amount_lb_per_1000 * lawn_size_sqft) / 1000
            total_chemical_needed_oz = total_chemical_needed_lb * 16
        
        _LOGGER.info("🔍 CALCULATION DEBUG: %s application for %s sqft", 
                    "LIQUID" if is_liquid_application else "GRANULAR", lawn_size_sqft)
        _LOGGER.info("🔍 Per 1000 sqft: %.3f oz (%.4f lb) at %s rate (%.1fx)", 
                    applied_amount_oz_per_1000, applied_amount_lb_per_1000, rate_description, rate_multiplier)
        _LOGGER.info("🔍 Total needed: %.3f oz (%.4f lb)", total_chemical_needed_oz, total_chemical_needed_lb)

        # Store the application data with all calculated amounts
        application_data = {
            "last_applied": application_date_str,
            "interval_days": interval,
            "default_amount_lb_per_1000sqft": default_amount_lb,
            "default_amount_oz_per_1000sqft": default_amount_oz,
            "applied_amount_lb_per_1000sqft": round(applied_amount_lb_per_1000, 4),
            "applied_amount_oz_per_1000sqft": round(applied_amount_oz_per_1000, 3),
            "rate_multiplier": rate_multiplier,
            "rate_description": rate_description,
            "method": method,
            "application_type": "liquid" if is_liquid_application else "granular",
            "lawn_size_sqft": lawn_size_sqft,
            "total_chemical_needed_oz": round(total_chemical_needed_oz, 3),
            "total_chemical_needed_lb": round(total_chemical_needed_lb, 4),
            "yard_zone": yard_zone
        }
        
        data["applications"][chemical] = application_data

        await store.async_save(data)
        _LOGGER.info("🔍 STORED DATA: %s", data["applications"][chemical])
        _LOGGER.info("✅ Application logged: %s in %s on %s via %s at %s rate (%.1fx) - %.3f oz needed", 
                    chemical, yard_zone, application_date_str, method, rate_description, rate_multiplier, total_chemical_needed_oz)

        # Notify sensors to update with zone-specific signal
        signal_name = f"lawn_manager_update_{zone_entry_id}"
        async_dispatcher_send(hass, signal_name)
        _LOGGER.info("✅ Sent update signal for zone: %s", zone_entry_id)

    async def handle_reload(call: ServiceCall):
        """Reload the Lawn Manager integration from a service call."""
        _LOGGER.info("🔁 Reloading Lawn Manager integration...")
        entry = next((e for e in hass.config_entries.async_entries(DOMAIN)), None)
        if entry:
            await hass.config_entries.async_reload(entry.entry_id)

    # Register services if not already registered
    if not hass.services.has_service(DOMAIN, "log_lawn_activity"):  # New name
        hass.services.async_register(DOMAIN, "log_lawn_activity", handle_log_lawn_activity)

    if not hass.services.has_service(DOMAIN, "log_application"):
        hass.services.async_register(DOMAIN, "log_application", handle_log_application)

    if not hass.services.has_service(DOMAIN, "reload"):
        hass.services.async_register(DOMAIN, "reload", handle_reload)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("🔄 Unloading Lawn Manager entry: %s", entry.title)
    
    # Unload all platforms
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    
    if unload_ok:
        _LOGGER.info("✅ Successfully unloaded Lawn Manager entry: %s", entry.title)
    else:
        _LOGGER.error("❌ Failed to unload Lawn Manager entry: %s", entry.title)
    
    return unload_ok


async def async_remove_entry(hass, entry):
    """Handle removal of a config entry by purging stored data."""
    # Remove zone-specific storage
    zone_storage_key = get_storage_key(entry.entry_id)
    main_store = Store(hass, STORAGE_VERSION, zone_storage_key)
    await main_store.async_remove()
    
    # Remove equipment storage
    equipment_store = Store(hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
    equipment_data = await equipment_store.async_load() or {}
    if equipment_data:
        _LOGGER.info("Removing %d equipment entries during config entry removal", len(equipment_data))
        await equipment_store.async_remove()
    
    # Restore original services.yaml by removing dynamic modifications
    await _restore_original_services_yaml(hass)
    
    _LOGGER.info("✅ Config entry removed - all Lawn Manager data, equipment, and services.yaml modifications cleaned up.")


async def _restore_original_services_yaml(hass: HomeAssistant):
    """Restore services.yaml to original state by removing dynamic modifications."""
    import os
    import yaml
    
    # Path to services.yaml
    services_yaml_path = os.path.join(os.path.dirname(__file__), "services.yaml")
    
    def _restore_services_file():
        """Restore services file synchronously in executor."""
        try:
            # Read current services.yaml
            with open(services_yaml_path, 'r', encoding='utf-8') as file:
                services = yaml.safe_load(file)
            
            # Restore calculate_application_rate to original text field format
            if 'calculate_application_rate' in services:
                services['calculate_application_rate']['fields']['equipment_name'] = {
                    "name": "Equipment Name",
                    "description": "Enter the exact equipment name from list_calculation_options (e.g., 'Ryobi 4 Gallon Sprayer')",
                    "required": True,
                    "selector": {
                        "text": None
                    }
                }
                services['calculate_application_rate']['fields']['zone'] = {
                    "name": "Zone Name", 
                    "description": "Enter the exact zone name from list_calculation_options (e.g., 'Front Yard')",
                    "required": True,
                    "selector": {
                        "text": None
                    }
                }
            
            # Write back the restored services.yaml
            with open(services_yaml_path, 'w', encoding='utf-8') as file:
                yaml.dump(services, file, default_flow_style=False, sort_keys=False, allow_unicode=True)
            
            _LOGGER.info("✅ services.yaml restored to original text field format")
            return True
            
        except Exception as e:
            _LOGGER.error("❌ Failed to restore services.yaml: %s", e)
            return False
    
    # Run the file operations in executor to avoid blocking
    await hass.async_add_executor_job(_restore_services_file)
    
