from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up text entities for Lawn Manager."""
    entities = [
        CustomChemicalTextEntity(hass, entry),
        CustomRateTextEntity(hass, entry),
    ]
    async_add_entities(entities)


class CustomChemicalTextEntity(TextEntity):
    """Text entity for custom chemical name."""

    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Custom Chemical Name"
        self._attr_unique_id = f"{entry.entry_id}_custom_chemical_name"
        self._attr_native_value = ""
        self._attr_icon = "mdi:flask-empty-outline"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Chemical Application",
        }

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()


class CustomRateTextEntity(TextEntity):
    """Text entity for custom rate value.
    
    When Custom Rate Unit is 'Multiplier', this is a multiplier (e.g. 1.0, 2.0).
    When Custom Rate Unit is 'oz per 1,000 sq ft', this is an oz amount.
    When Custom Rate Unit is 'lb per 1,000 sq ft', this is a lb amount.
    """

    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Custom Rate Value"
        self._attr_unique_id = f"{entry.entry_id}_custom_rate_multiplier"
        self._attr_native_value = "1.0"
        self._attr_icon = "mdi:calculator"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Chemical Application",
        }

    @property
    def extra_state_attributes(self):
        return {
            "help": "Enter the rate value. Meaning depends on 'Custom Rate Unit' selection: "
                    "Multiplier (1.0=default, 2.0=double), or an actual amount in oz/lb per 1,000 sq ft."
        }

    async def async_set_value(self, value: str) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
