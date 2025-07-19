from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up text entities for Lawn Manager."""
    _LOGGER.warning(f"🔍 Setting up Lawn Manager text entities for entry {entry.entry_id}")
    
    entities = [
        CustomChemicalTextEntity(hass, entry),
        CustomRateTextEntity(hass, entry),
    ]
    
    _LOGGER.warning(f"🔍 Adding {len(entities)} text entities")
    async_add_entities(entities)

class CustomChemicalTextEntity(TextEntity):
    """Text entity for custom chemical name."""
    
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "🧪 Custom Chemical Name"
        self._attr_unique_id = f"{entry.entry_id}_custom_chemical_name"
        self._attr_native_value = ""
        self._attr_icon = "mdi:flask-empty-outline"
        _LOGGER.warning(f"🔍 Created custom chemical text entity: {self._attr_unique_id}")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    async def async_set_value(self, value: str) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state()

class CustomRateTextEntity(TextEntity):
    """Text entity for custom rate multiplier."""
    
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "🧪 Custom Rate Multiplier"
        self._attr_unique_id = f"{entry.entry_id}_custom_rate_multiplier"
        self._attr_native_value = "1.0"
        self._attr_icon = "mdi:calculator"
        _LOGGER.warning(f"🔍 Created custom rate text entity: {self._attr_unique_id}")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    async def async_set_value(self, value: str) -> None:
        """Update the current value."""
        self._attr_native_value = value
        self.async_write_ha_state() 
