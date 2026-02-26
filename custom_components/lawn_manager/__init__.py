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
    return True


async def _store_equipment_from_config(hass: HomeAssistant, entry: ConfigEntry):
    """Store equipment from config flow into equipment storage."""
    if "equipment_list" not in entry.data:
        return

    equipment_store = Store(hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
    equipment_data = await equipment_store.async_load() or {}

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
    async_dispatcher_send(hass, "lawn_manager_equipment_update")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.info("Setting up Lawn Manager entry: %s", entry.title)

    await _store_equipment_from_config(hass, entry)

    await _register_services(hass)

    from .services import async_register_services
    await async_register_services(hass)

    storage_key = get_storage_key(entry.entry_id)
    store = Store(hass, 1, storage_key)
    data = await store.async_load() or {}

    if not data:
        data = {
            "last_mow": None,
            "mowing_history": [],
            "applications": {}
        }
        await store.async_save(data)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await asyncio.sleep(0.2)
    async_dispatcher_send(hass, f"lawn_manager_update_{entry.entry_id}")

    _LOGGER.info("Lawn Manager setup complete for %s", entry.title)
    return True


async def _register_services(hass: HomeAssistant):

    async def handle_log_lawn_activity(call: ServiceCall):
        application_date = call.data.get("application_date")
        cut_type = call.data.get("cut_type", "Regular Maintenance")
        height_of_cut = call.data.get("height_of_cut")
        zone_entry_id = call.data.get("_zone_entry_id") or call.data.get("zone")

        if not zone_entry_id:
            _LOGGER.error("No zone entry ID provided")
            return

        entries = hass.config_entries.async_entries(DOMAIN)
        zone_exists = any(entry.entry_id == zone_entry_id for entry in entries)
        if not zone_exists:
            _LOGGER.error("Invalid zone ID: %s", zone_entry_id)
            return

        zone_storage_key = get_storage_key(zone_entry_id)
        store = Store(hass, STORAGE_VERSION, zone_storage_key)
        data = await store.async_load() or {}

        if application_date:
            try:
                from datetime import datetime, timedelta
                provided_date = datetime.strptime(application_date, "%Y-%m-%d").date()
                today = dt_util.now().date()

                if provided_date > today:
                    _LOGGER.error("Cannot log lawn activity for future date: %s", application_date)
                    return

                one_year_ago = today - timedelta(days=365)
                if provided_date < one_year_ago:
                    _LOGGER.error("Cannot log lawn activity for date more than 1 year ago: %s", application_date)
                    return

                mow_date_str = application_date
            except ValueError:
                mow_date_str = dt_util.now().strftime("%Y-%m-%d")
        else:
            mow_date_str = dt_util.now().strftime("%Y-%m-%d")

        data["last_mow"] = mow_date_str

        if "mowing_history" not in data:
            data["mowing_history"] = []

        mow_record = {
            "date": mow_date_str,
            "cut_type": cut_type,
            "timestamp": dt_util.now().isoformat()
        }

        if height_of_cut is not None:
            mow_record["height_of_cut_inches"] = float(height_of_cut)

        data["mowing_history"].append(mow_record)
        if len(data["mowing_history"]) > 50:
            data["mowing_history"] = data["mowing_history"][-50:]

        await store.async_save(data)
        _LOGGER.info("Lawn Activity logged: %s (%s%s)", mow_date_str, cut_type,
                    f" at {height_of_cut}\"" if height_of_cut else "")

        signal_name = f"lawn_manager_update_{zone_entry_id}"
        async_dispatcher_send(hass, signal_name)

    async def handle_log_application(call: ServiceCall):
        selected = call.data.get("chemical_select")
        custom = call.data.get("custom_chemical")
        method = call.data.get("method", "Unknown")
        rate_override = call.data.get("rate_override", "Default")
        custom_rate = call.data.get("custom_rate", "1.0")
        custom_rate_unit = call.data.get("custom_rate_unit", "Multiplier (1.0x = default rate)")
        application_date = call.data.get("application_date")
        zone_entry_id = call.data.get("_zone_entry_id")

        chemical = custom.strip() if custom else selected

        if not chemical:
            _LOGGER.error("No chemical name provided.")
            return

        if not zone_entry_id:
            _LOGGER.error("No zone entry ID provided")
            return

        zone_storage_key = get_storage_key(zone_entry_id)
        store = Store(hass, STORAGE_VERSION, zone_storage_key)
        data = await store.async_load() or {}

        if application_date:
            try:
                from datetime import datetime, timedelta
                provided_date = datetime.strptime(application_date, "%Y-%m-%d").date()
                today = dt_util.now().date()

                if provided_date > today:
                    _LOGGER.error("Cannot log application for future date: %s", application_date)
                    return

                one_year_ago = today - timedelta(days=365)
                if provided_date < one_year_ago:
                    _LOGGER.error("Cannot log application for date more than 1 year ago: %s", application_date)
                    return

                application_date_str = application_date
            except ValueError:
                application_date_str = dt_util.now().strftime("%Y-%m-%d")
        else:
            application_date_str = dt_util.now().strftime("%Y-%m-%d")

        if "applications" not in data:
            data["applications"] = {}
        elif isinstance(data["applications"], list):
            applications = {app.get("chemical_name", f"Chemical {i}"): app
                          for i, app in enumerate(data["applications"]) if isinstance(app, dict)}
            data["applications"] = applications

        entries = hass.config_entries.async_entries(DOMAIN)
        zone_config = None
        for entry in entries:
            if entry.entry_id == zone_entry_id:
                zone_config = entry.data
                break

        if not zone_config:
            _LOGGER.error("Zone configuration not found for entry ID: %s", zone_entry_id)
            return

        lawn_size_sqft = zone_config.get("lawn_size_sqft", 1000)
        yard_zone = zone_config.get("yard_zone", "Unknown Zone")

        if chemical not in CHEMICALS:
            _LOGGER.warning("'%s' is not in the predefined chemical list. Logging anyway.", chemical)
            interval = 30
            default_amount_lb = 1.0
            default_amount_oz = 16.0
            is_liquid_application = False
        else:
            chemical_data = CHEMICALS[chemical]
            interval = chemical_data["interval_days"]
            is_liquid_application = (method.lower() == "sprayer" and "liquid_oz_per_1000sqft" in chemical_data)

            if is_liquid_application:
                default_amount_oz_per_1000 = chemical_data["liquid_oz_per_1000sqft"]
                default_amount_lb_per_1000 = default_amount_oz_per_1000 / 16.0
                default_amount_lb = default_amount_lb_per_1000
                default_amount_oz = default_amount_oz_per_1000
            else:
                default_amount_lb_per_1000 = chemical_data.get("amount_lb_per_1000sqft", 1.0)
                default_amount_lb = default_amount_lb_per_1000
                default_amount_oz = round(default_amount_lb * 16, 2)

        # Handle rate override with custom rate unit support
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
                if not custom_rate or custom_rate.strip() == "":
                    rate_multiplier = 1.0
                    rate_description = "Custom (1.0x)"
                else:
                    rate_value = float(custom_rate)

                    if "oz per" in custom_rate_unit:
                        if default_amount_oz > 0:
                            rate_multiplier = rate_value / default_amount_oz
                        else:
                            rate_multiplier = 1.0
                        rate_description = f"Custom ({rate_value} oz/1000sqft)"
                    elif "lb per" in custom_rate_unit:
                        # User specified actual lb per 1000 sqft
                        if default_amount_lb > 0:
                            rate_multiplier = rate_value / default_amount_lb
                        else:
                            rate_multiplier = 1.0
                        rate_description = f"Custom ({rate_value} lb/1000sqft)"
                    elif "ml per" in custom_rate_unit:
                        oz_equiv = rate_value / 29.5735
                        if default_amount_oz > 0:
                            rate_multiplier = oz_equiv / default_amount_oz
                        else:
                            rate_multiplier = 1.0
                        rate_description = f"Custom ({rate_value} ml/1000sqft)"
                    else:
                        # Default: treat as multiplier
                        rate_multiplier = rate_value
                        rate_description = f"Custom ({rate_multiplier}x)"
            except ValueError:
                _LOGGER.error("Invalid custom rate value: %s. Using default.", custom_rate)
                rate_multiplier = 1.0
                rate_description = "Default (Invalid Custom)"
        else:
            rate_multiplier = 1.0
            rate_description = "Default"

        if is_liquid_application:
            applied_amount_oz_per_1000 = default_amount_oz * rate_multiplier
            applied_amount_lb_per_1000 = applied_amount_oz_per_1000 / 16.0
            total_chemical_needed_oz = (applied_amount_oz_per_1000 * lawn_size_sqft) / 1000
            total_chemical_needed_lb = total_chemical_needed_oz / 16.0
        else:
            applied_amount_lb_per_1000 = default_amount_lb * rate_multiplier
            applied_amount_oz_per_1000 = round(applied_amount_lb_per_1000 * 16, 2)
            total_chemical_needed_lb = (applied_amount_lb_per_1000 * lawn_size_sqft) / 1000
            total_chemical_needed_oz = total_chemical_needed_lb * 16

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

        # Also append to application_history list for full activity tracking
        if "application_history" not in data:
            data["application_history"] = []
        data["application_history"].append({
            "chemical": chemical,
            "date": application_date_str,
            "method": method,
            "rate_description": rate_description,
            "detail": f"{rate_description} via {method}",
            "timestamp": dt_util.now().isoformat(),
        })
        if len(data["application_history"]) > 50:
            data["application_history"] = data["application_history"][-50:]

        await store.async_save(data)

        _LOGGER.info("Application logged: %s in %s on %s via %s at %s rate (%.1fx) - %.3f oz needed",
                    chemical, yard_zone, application_date_str, method, rate_description, rate_multiplier, total_chemical_needed_oz)

        signal_name = f"lawn_manager_update_{zone_entry_id}"
        async_dispatcher_send(hass, signal_name)

    async def handle_reload(call: ServiceCall):
        _LOGGER.info("Reloading Lawn Manager integration...")
        entry = next((e for e in hass.config_entries.async_entries(DOMAIN)), None)
        if entry:
            await hass.config_entries.async_reload(entry.entry_id)

    if not hass.services.has_service(DOMAIN, "log_lawn_activity"):
        hass.services.async_register(DOMAIN, "log_lawn_activity", handle_log_lawn_activity)

    if not hass.services.has_service(DOMAIN, "log_application"):
        hass.services.async_register(DOMAIN, "log_application", handle_log_application)

    if not hass.services.has_service(DOMAIN, "reload"):
        hass.services.async_register(DOMAIN, "reload", handle_reload)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok


async def async_remove_entry(hass, entry):
    zone_storage_key = get_storage_key(entry.entry_id)
    main_store = Store(hass, STORAGE_VERSION, zone_storage_key)
    await main_store.async_remove()

    equipment_store = Store(hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
    equipment_data = await equipment_store.async_load() or {}
    if equipment_data:
        await equipment_store.async_remove()

    _LOGGER.info("Config entry removed - all Lawn Manager data cleaned up.")
