from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.info("Setting up Lawn Manager button entities")
    entities = [
        LogMowButton(hass, entry),
        LogChemicalButton(hass, entry),
    ]
    async_add_entities(entities)

class LogMowButton(ButtonEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Log Mow"
        self._attr_unique_id = f"{entry.entry_id}_log_mow"
        self._attr_icon = "mdi:grass"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    async def async_press(self):
        _LOGGER.info("Log Mow button pressed")
        
        # Find the application date entity
        application_date_entity = None
        for state in self._hass.states.async_all():
            entity_id = state.entity_id
            if entity_id.startswith("date.") and "application_date" in entity_id:
                application_date_entity = entity_id
                break
        
        # Get the selected date
        application_date = self._hass.states.get(application_date_entity) if application_date_entity else None
        application_date_value = application_date.state if application_date else None
        
        _LOGGER.info("Log Mow using date: %s", application_date_value)
        
        # Call the service with the selected date
        service_data = {}
        if application_date_value:
            service_data["application_date"] = application_date_value
        
        await self._hass.services.async_call(
            DOMAIN, "log_mow", service_data, blocking=True
        )

class LogChemicalButton(ButtonEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Log Chemical Application"
        self._attr_unique_id = f"{entry.entry_id}_log_chemical"
        self._attr_icon = "mdi:flask-outline"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    async def async_press(self):
        _LOGGER.warning("Log Chemical Application button pressed - DEBUG")
        
        # Find entities by searching through all states
        chemical_select_entity = None
        custom_chemical_entity = None
        method_select_entity = None
        rate_override_entity = None
        custom_rate_entity = None
        application_date_entity = None
        
        # Search for our entities in all states
        for state in self._hass.states.async_all():  # ✅ Iterate through State objects
            entity_id = state.entity_id  # ✅ Get entity_id from State object
            if entity_id.startswith("select.") and "chemical_selection" in entity_id:
                chemical_select_entity = entity_id
            elif entity_id.startswith("text.") and "custom_chemical_name" in entity_id:
                custom_chemical_entity = entity_id
            elif entity_id.startswith("select.") and "application_method" in entity_id:
                method_select_entity = entity_id
            elif entity_id.startswith("select.") and "application_rate" in entity_id:
                rate_override_entity = entity_id
            elif entity_id.startswith("text.") and "custom_rate_multiplier" in entity_id:
                custom_rate_entity = entity_id
            elif entity_id.startswith("date.") and "application_date" in entity_id:
                application_date_entity = entity_id
        
        _LOGGER.warning(f"Found entities: Chemical={chemical_select_entity}, Custom={custom_chemical_entity}, Method={method_select_entity}, Rate={rate_override_entity}, CustomRate={custom_rate_entity}, Date={application_date_entity}")
        
        # Get current values
        chemical_select = self._hass.states.get(chemical_select_entity) if chemical_select_entity else None
        custom_chemical = self._hass.states.get(custom_chemical_entity) if custom_chemical_entity else None
        method_select = self._hass.states.get(method_select_entity) if method_select_entity else None
        rate_override = self._hass.states.get(rate_override_entity) if rate_override_entity else None
        custom_rate = self._hass.states.get(custom_rate_entity) if custom_rate_entity else None
        application_date = self._hass.states.get(application_date_entity) if application_date_entity else None
        
        _LOGGER.warning(f"Entity states - Chemical: {chemical_select.state if chemical_select else 'NOT FOUND'}, Custom: {custom_chemical.state if custom_chemical else 'NOT FOUND'}, Method: {method_select.state if method_select else 'NOT FOUND'}, Rate: {rate_override.state if rate_override else 'NOT FOUND'}, CustomRate: {custom_rate.state if custom_rate else 'NOT FOUND'}, Date: {application_date.state if application_date else 'NOT FOUND'}")
        
        # Determine which chemical to use
        selected_chemical = chemical_select.state if chemical_select else None
        custom_chemical_value = custom_chemical.state if custom_chemical else ""
        method = method_select.state if method_select else "Sprayer"
        rate_override_value = rate_override.state if rate_override else "Default"
        custom_rate_value = custom_rate.state if custom_rate else "1.0"
        application_date_value = application_date.state if application_date else None
        
        _LOGGER.warning(f"Processed values - Selected: {selected_chemical}, Custom: {custom_chemical_value}, Method: {method}, Rate: {rate_override_value}, CustomRate: {custom_rate_value}, Date: {application_date_value}")
        
        # Use custom chemical if "Custom" is selected and custom field has value
        if selected_chemical == "Custom" and custom_chemical_value.strip():
            chemical_to_use = custom_chemical_value.strip()
        elif selected_chemical and selected_chemical != "Custom":
            chemical_to_use = selected_chemical
        else:
            # No valid chemical selected
            _LOGGER.error("No chemical selected or custom chemical name provided")
            return
        
        _LOGGER.warning(f"Final chemical to use: {chemical_to_use}")
        
        # Call the service with the selected values
        service_data = {
            "chemical_select": chemical_to_use if selected_chemical != "Custom" else None,
            "custom_chemical": chemical_to_use if selected_chemical == "Custom" else None,
            "method": method,
            "rate_override": rate_override_value,
            "custom_rate": custom_rate_value,
            "application_date": application_date_value
        }
        
        _LOGGER.warning(f"Calling service with data: {service_data}")
        
        await self._hass.services.async_call(
            DOMAIN, "log_application",
            service_data,
            blocking=True
        ) 
