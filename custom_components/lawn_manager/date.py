from homeassistant.components.date import DateEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging
from datetime import date

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up date entities for Lawn Manager."""
    entities = [
        ApplicationDateEntity(hass, entry),
    ]
    async_add_entities(entities)


class ApplicationDateEntity(DateEntity):
    """Date entity for application date - set to today or a past date to back-log activities."""

    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Activity Date"
        self._attr_unique_id = f"{entry.entry_id}_application_date"
        self._attr_native_value = date.today()
        self._attr_icon = "mdi:calendar"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
        }

    async def async_set_value(self, value: date) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
