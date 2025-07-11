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
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor", "button", "select", "text"])

    return True


async def _register_services(hass: HomeAssistant):
    """Register custom services for Lawn Manager."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def handle_log_mow(call: ServiceCall):
        _LOGGER.info("🔧 log_mow service called")
        data = await store.async_load() or {}
        now = dt_util.now()
        data["last_mow"] = now.strftime("%Y-%m-%d")
        await store.async_save(data)
        _LOGGER.info("✅ Mow logged: %s", data["last_mow"])

        # Notify sensors to update
        async_dispatcher_send(hass, "lawn_manager_update")

    async def handle_log_application(call: ServiceCall):
        """Handle logging a chemical application."""
        selected = call.data.get("chemical_select")
        custom = call.data.get("custom_chemical")
        method = call.data.get("method", "Unknown")

        chemical = custom.strip() if custom else selected

        if not chemical:
            _LOGGER.error("❌ No chemical name provided.")
            return

        _LOGGER.info("🔧 log_application called for %s via %s", chemical, method)

        data = await store.async_load() or {}
        now = dt_util.now().strftime("%Y-%m-%d")

        if "applications" not in data:
            data["applications"] = {}

        if chemical not in CHEMICALS:
            _LOGGER.warning("⚠️ '%s' is not in the predefined chemical list. Logging anyway.", chemical)
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
            "amount_oz_per_1000sqft": amount_oz,
            "method": method,
        }

        await store.async_save(data)
        _LOGGER.info("✅ Application logged for %s on %s via %s", chemical, now, method)

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
