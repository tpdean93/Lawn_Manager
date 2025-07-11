from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.warning("Setting up Lawn Manager text entities - DEBUG")
    
    entities = [
        LawnCustomChemicalText(hass, entry),
    ]
    
    _LOGGER.warning(f"Adding {len(entities)} text entities")
    async_add_entities(entities)

class LawnCustomChemicalText(TextEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Custom Chemical Name"
        self._attr_unique_id = f"{entry.entry_id}_custom_chemical"
        self._attr_native_max = 50
        self._attr_native_min = 0
        self._attr_native_value = ""
        self._attr_icon = "mdi:pencil"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        self._attr_native_value = value
        self.async_write_ha_state() 
