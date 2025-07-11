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
        LawnCustomRateText(hass, entry),
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

class LawnCustomRateText(TextEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Custom Rate Multiplier"
        self._attr_unique_id = f"{entry.entry_id}_custom_rate"
        self._attr_native_max = 10
        self._attr_native_min = 0
        self._attr_native_value = ""
        self._attr_icon = "mdi:scale"

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
            "help": "Enter multiplier: 1.0 = default rate, 2.0 = double rate, 0.5 = half rate",
            "examples": "0.5 (half), 1.0 (default), 1.5 (1.5x), 2.0 (double)"
        }

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        self._attr_native_value = value
        self.async_write_ha_state() 
