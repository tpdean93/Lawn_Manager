from homeassistant.components.date import DateEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util
from datetime import date, timedelta
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.warning("Setting up Lawn Manager date entities - DEBUG")
    
    entities = [
        LawnApplicationDateEntity(hass, entry),
    ]
    
    _LOGGER.warning(f"Adding {len(entities)} date entities")
    async_add_entities(entities)

class LawnApplicationDateEntity(DateEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Date"
        self._attr_unique_id = f"{entry.entry_id}_application_date"
        # Default to today's date
        self._attr_native_value = dt_util.now().date()
        self._attr_icon = "mdi:calendar"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    @property
    def extra_state_attributes(self):
        return {
            "help": "Select the date when the chemical was actually applied",
            "note": "Cannot select future dates or dates more than 1 year ago"
        }

    async def async_set_value(self, value: date) -> None:
        """Set the date value with validation."""
        today = dt_util.now().date()
        
        # Validate date is not in the future
        if value > today:
            _LOGGER.warning("Cannot set application date to future date: %s", value)
            return
        
        # Validate date is not more than 1 year ago
        one_year_ago = today - timedelta(days=365)
        if value < one_year_ago:
            _LOGGER.warning("Cannot set application date more than 1 year ago: %s", value)
            return
        
        self._attr_native_value = value
        self.async_write_ha_state() 
