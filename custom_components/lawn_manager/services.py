import logging
from datetime import datetime
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION, CHEMICALS

_LOGGER = logging.getLogger(__name__)

async def async_register_services(hass: HomeAssistant) -> None:
    """Register Lawn Manager services."""
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

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

    hass.services.async_register(DOMAIN, "log_mow", handle_log_mow)
    hass.services.async_register(DOMAIN, "log_application", handle_log_application)
