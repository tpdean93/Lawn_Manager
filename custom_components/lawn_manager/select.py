from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging

from .const import DOMAIN, CHEMICALS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.warning("Setting up Lawn Manager select entities - DEBUG")
    
    # Get chemical options from CHEMICALS constant
    chemical_options = list(CHEMICALS.keys()) + ["Custom"]
    method_options = ["Sprayer", "Spreader", "Hand Application", "Other"]
    
    _LOGGER.warning(f"Chemical options: {chemical_options}")
    _LOGGER.warning(f"Method options: {method_options}")
    
    entities = [
        LawnChemicalSelect(hass, entry, chemical_options),
        LawnMethodSelect(hass, entry, method_options),
    ]
    
    _LOGGER.warning(f"Adding {len(entities)} select entities")
    async_add_entities(entities)

class LawnChemicalSelect(SelectEntity):
    def __init__(self, hass, entry, options):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Chemical Selection"
        self._attr_unique_id = f"{entry.entry_id}_chemical_select"
        _LOGGER.warning(f"Creating chemical select entity with unique_id: {self._attr_unique_id}")
        self._attr_options = options
        self._attr_current_option = options[0]  # Default to first option
        self._attr_icon = "mdi:flask-outline"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    async def async_select_option(self, option: str) -> None:
        """Select new option."""
        self._attr_current_option = option
        self.async_write_ha_state()

class LawnMethodSelect(SelectEntity):
    def __init__(self, hass, entry, options):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Application Method"
        self._attr_unique_id = f"{entry.entry_id}_method_select"
        self._attr_options = options
        self._attr_current_option = options[0]  # Default to first option
        self._attr_icon = "mdi:spray"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    async def async_select_option(self, option: str) -> None:
        """Select new option."""
        self._attr_current_option = option
        self.async_write_ha_state() 
