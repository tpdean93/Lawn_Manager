from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import async_dispatcher_send
import logging

from .const import DOMAIN, CHEMICALS

_LOGGER = logging.getLogger(__name__)
STORAGE_KEY = "lawn_manager_data"
STORAGE_VERSION = 1


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Lawn Manager integration from configuration.yaml (legacy use)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Lawn Manager from a config entry."""
    _LOGGER.info("Setting up Lawn Manager entry: %s", entry.title)

    # Register services
    await _register_services(hass)

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor", "button", "select", "text", "date"])

    return True


async def _register_services(hass: HomeAssistant):
    """Register custom services for Lawn Manager."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def handle_log_mow(call: ServiceCall):
        _LOGGER.info("🔧 log_mow service called")
        application_date = call.data.get("application_date")
        
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
                    _LOGGER.error("❌ Cannot log mow for future date: %s", application_date)
                    return
                
                # Check if date is more than 1 year ago
                one_year_ago = today - timedelta(days=365)
                if provided_date < one_year_ago:
                    _LOGGER.error("❌ Cannot log mow for date more than 1 year ago: %s", application_date)
                    return
                
                mow_date_str = application_date
            except ValueError:
                _LOGGER.error("❌ Invalid date format: %s. Using today's date.", application_date)
                mow_date_str = dt_util.now().strftime("%Y-%m-%d")
        else:
            mow_date_str = dt_util.now().strftime("%Y-%m-%d")
        
        data["last_mow"] = mow_date_str
        await store.async_save(data)
        _LOGGER.info("✅ Mow logged: %s", data["last_mow"])

        # Notify sensors to update
        async_dispatcher_send(hass, "lawn_manager_update")

    async def handle_log_application(call: ServiceCall):
        """Handle logging a chemical application."""
        selected = call.data.get("chemical_select")
        custom = call.data.get("custom_chemical")
        method = call.data.get("method", "Unknown")
        rate_override = call.data.get("rate_override", "Default")
        custom_rate = call.data.get("custom_rate", "1.0")
        application_date = call.data.get("application_date")

        chemical = custom.strip() if custom else selected

        if not chemical:
            _LOGGER.error("❌ No chemical name provided.")
            return

        _LOGGER.info("🔧 log_application called for %s via %s with rate override: %s, custom_rate: %s, date: %s", chemical, method, rate_override, custom_rate, application_date)

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

        if "applications" not in data:
            data["applications"] = {}

        # Get default rates
        if chemical not in CHEMICALS:
            _LOGGER.warning("⚠️ '%s' is not in the predefined chemical list. Logging anyway.", chemical)
            interval = 30
            default_amount_lb = 1.0
        else:
            interval = CHEMICALS[chemical]["interval_days"]
            default_amount_lb = CHEMICALS[chemical]["amount_lb_per_1000sqft"]

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

        # Calculate final amounts
        applied_amount_lb = default_amount_lb * rate_multiplier
        applied_amount_oz = round(applied_amount_lb * 16, 2)
        
        _LOGGER.info("🔍 CALCULATION DEBUG: default_amount_lb=%s, rate_multiplier=%s, applied_amount_lb=%s, applied_amount_oz=%s", 
                    default_amount_lb, rate_multiplier, applied_amount_lb, applied_amount_oz)

        data["applications"][chemical] = {
            "last_applied": application_date_str,
            "interval_days": interval,
            "default_amount_lb_per_1000sqft": default_amount_lb,
            "default_amount_oz_per_1000sqft": round(default_amount_lb * 16, 2),
            "applied_amount_lb_per_1000sqft": applied_amount_lb,
            "applied_amount_oz_per_1000sqft": applied_amount_oz,
            "rate_multiplier": rate_multiplier,
            "rate_description": rate_description,
            "method": method,
        }

        await store.async_save(data)
        _LOGGER.info("🔍 STORED DATA: %s", data["applications"][chemical])
        _LOGGER.info("✅ Application logged for %s on %s via %s at %s rate (%.1fx)", chemical, application_date_str, method, rate_description, rate_multiplier)

        # Notify sensors to update
        async_dispatcher_send(hass, "lawn_manager_update")

    async def handle_reload(call: ServiceCall):
        """Reload the Lawn Manager integration from a service call."""
        _LOGGER.info("🔁 Reloading Lawn Manager integration...")
        entry = next((e for e in hass.config_entries.async_entries(DOMAIN)), None)
        if entry:
            await hass.config_entries.async_reload(entry.entry_id)

    async def handle_remove_entry(call: ServiceCall):
        """Handle removal of a config entry by purging stored data."""
        store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        await store.async_remove()
        _LOGGER.info("✅ Lawn Manager data purged.")

    # Register services if not already registered
    if not hass.services.has_service(DOMAIN, "log_mow"):
        hass.services.async_register(DOMAIN, "log_mow", handle_log_mow)

    if not hass.services.has_service(DOMAIN, "log_application"):
        hass.services.async_register(DOMAIN, "log_application", handle_log_application)

    if not hass.services.has_service(DOMAIN, "reload"):
        hass.services.async_register(DOMAIN, "reload", handle_reload)

    if not hass.services.has_service(DOMAIN, "remove_entry"):
        hass.services.async_register(DOMAIN, "remove_entry", handle_remove_entry)


async def async_remove_entry(hass, entry):
    """Handle removal of a config entry by purging stored data."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    await store.async_remove()
