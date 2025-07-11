from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entities = [
        LogMowButton(hass, entry),
        LogChemicalButton(hass, entry),
    ]
    async_add_entities(entities)

class LogMowButton(ButtonEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._attr_name = "Log Mow"
        self._attr_unique_id = f"{entry.entry_id}_log_mow"

    async def async_press(self):
        await self._hass.services.async_call(
            DOMAIN, "log_mow", {}, blocking=True
        )

class LogChemicalButton(ButtonEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._attr_name = "Log Chemical Application (Default)"
        self._attr_unique_id = f"{entry.entry_id}_log_chemical"

    async def async_press(self):
        # This uses a default chemical for demonstration. You can enhance this to prompt for input.
        await self._hass.services.async_call(
            DOMAIN, "log_application",
            {"chemical_select": "Fertilizer", "method": "Sprayer"},
            blocking=True
        ) 
