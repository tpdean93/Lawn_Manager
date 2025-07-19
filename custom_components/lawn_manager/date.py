from homeassistant.components.date import DateEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging
from datetime import date

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up date entities for Lawn Manager."""
    _LOGGER.warning(f"🔍 Setting up Lawn Manager date entities for entry {entry.entry_id}")
    
    entities = [
        ApplicationDateEntity(hass, entry),
    ]
    
    _LOGGER.warning(f"🔍 Adding {len(entities)} date entities")
    async_add_entities(entities)

class ApplicationDateEntity(DateEntity):
    """Date entity for application date."""
    
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "📅 Application Date"
        self._attr_unique_id = f"{entry.entry_id}_application_date"
        self._attr_native_value = date.today()  # Default to today
        self._attr_icon = "mdi:calendar"
        _LOGGER.warning(f"🔍 Created application date entity: {self._attr_unique_id}")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    async def async_set_value(self, value: date) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()
        _LOGGER.warning(f"🔍 Application date set to: {value}") 
