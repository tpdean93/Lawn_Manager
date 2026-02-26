from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up number entities for Lawn Manager."""
    entities = [
        HeightOfCutNumber(hass, entry),
    ]
    async_add_entities(entities)


class HeightOfCutNumber(NumberEntity):
    """Number entity for height of cut."""

    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Height of Cut"
        self._attr_unique_id = f"{entry.entry_id}_height_of_cut"
        self._attr_native_min_value = 0.125
        self._attr_native_max_value = 6.0
        self._attr_native_step = 0.125
        self._attr_native_unit_of_measurement = "inches"
        self._attr_native_value = 2.0
        self._attr_icon = "mdi:ruler"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Mowing",
        }

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
