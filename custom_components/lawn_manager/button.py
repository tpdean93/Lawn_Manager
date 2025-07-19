from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging
import asyncio

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.info(f"Setting up Lawn Manager button entities for zone {entry.entry_id}")
    
    # Log all existing entities for this zone
    zone_entities = []
    for state in hass.states.async_all():
        if entry.entry_id in state.entity_id:
            zone_entities.append(state.entity_id)
    
    _LOGGER.warning(f"🔍 Existing entities for zone {entry.entry_id}: {zone_entities}")
    
    entities = [
        LogMowButton(hass, entry),
        LogChemicalButton(hass, entry),
    ]
    async_add_entities(entities)

class LogMowButton(ButtonEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "🌿 Log Lawn Activity"
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
        _LOGGER.warning("🌿 Log Lawn Activity button pressed - Starting comprehensive entity search...")
        _LOGGER.warning(f"🔍 Button zone ID: {self._entry.entry_id}")
        
        # First, let's see ALL entities that might be relevant
        all_selects = []
        all_numbers = []
        all_dates = []
        
        for state in self._hass.states.async_all():
            entity_id = state.entity_id
            if entity_id.startswith("select."):
                all_selects.append(entity_id)
            elif entity_id.startswith("number."):
                all_numbers.append(entity_id)
            elif entity_id.startswith("date."):
                all_dates.append(entity_id)
        
        _LOGGER.warning(f"📋 Found {len(all_selects)} select entities: {all_selects}")
        _LOGGER.warning(f"📋 Found {len(all_numbers)} number entities: {all_numbers}")
        _LOGGER.warning(f"📋 Found {len(all_dates)} date entities: {all_dates}")
        
        # Find entities by searching through all states (EXACTLY like chemical button)
        activity_type_entity = None
        height_of_cut_entity = None
        application_date_entity = None
        
        # Search for our entities in all states (NO ZONE CHECK - like chemical button)
        for state in self._hass.states.async_all():
            entity_id = state.entity_id
            if entity_id.startswith("select.") and "activity_type_selection" in entity_id:
                activity_type_entity = entity_id
                _LOGGER.warning(f"✅ Found activity type: {entity_id} = {state.state}")
            elif entity_id.startswith("number.") and "height_of_cut" in entity_id:
                height_of_cut_entity = entity_id
                _LOGGER.warning(f"✅ Found HOC: {entity_id} = {state.state}")
            elif entity_id.startswith("date.") and "application_date" in entity_id:
                application_date_entity = entity_id
                _LOGGER.warning(f"✅ Found date: {entity_id} = {state.state}")
        
        _LOGGER.warning(f"🔍 Entity search complete - Activity: {activity_type_entity}, HOC: {height_of_cut_entity}, Date: {application_date_entity}")
        
        # Get entity states
        activity_type = self._hass.states.get(activity_type_entity) if activity_type_entity else None
        height_of_cut = self._hass.states.get(height_of_cut_entity) if height_of_cut_entity else None
        application_date = self._hass.states.get(application_date_entity) if application_date_entity else None
        
        # Get values with defaults
        activity_type_value = activity_type.state if activity_type else "Regular Maintenance"
        height_of_cut_value = None
        if height_of_cut and height_of_cut.state:
            try:
                height_of_cut_value = float(height_of_cut.state)
            except (ValueError, TypeError):
                _LOGGER.error(f"Could not convert HOC '{height_of_cut.state}' to float")
        
        application_date_value = application_date.state if application_date else None
        
        _LOGGER.warning(f"📊 Final values to log:")
        _LOGGER.warning(f"  - Activity: {activity_type_value}")
        _LOGGER.warning(f"  - HOC: {height_of_cut_value}")
        _LOGGER.warning(f"  - Date: {application_date_value}")
        
        # Call the service
        service_data = {
            "cut_type": activity_type_value,
            "_zone_entry_id": self._entry.entry_id
        }
        if application_date_value:
            service_data["application_date"] = application_date_value
        if height_of_cut_value is not None:
            service_data["height_of_cut"] = height_of_cut_value
        
        _LOGGER.warning(f"📞 Calling service with: {service_data}")
        
        await self._hass.services.async_call(
            DOMAIN, "log_lawn_activity", service_data, blocking=True
        )

class LogChemicalButton(ButtonEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "🧪 Log Chemical Application"
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
        
        # Find entities by searching through all states (like the original working version)
        chemical_select_entity = None
        custom_chemical_entity = None
        method_select_entity = None
        equipment_select_entity = None
        rate_override_entity = None
        custom_rate_entity = None
        application_date_entity = None
        
        # Search for our entities in all states (original approach)
        for state in self._hass.states.async_all():
            entity_id = state.entity_id
            if entity_id.startswith("select.") and "chemical_selection" in entity_id:
                chemical_select_entity = entity_id
            elif entity_id.startswith("text.") and "custom_chemical_name" in entity_id:
                custom_chemical_entity = entity_id
            elif entity_id.startswith("select.") and "application_method" in entity_id:
                method_select_entity = entity_id
            elif entity_id.startswith("select.") and "equipment_select" in entity_id:
                equipment_select_entity = entity_id
            elif entity_id.startswith("select.") and "application_rate" in entity_id:
                rate_override_entity = entity_id
            elif entity_id.startswith("text.") and "custom_rate_multiplier" in entity_id:
                custom_rate_entity = entity_id
            elif entity_id.startswith("date.") and "application_date" in entity_id:
                application_date_entity = entity_id
        
        _LOGGER.warning(f"Found entities: Chemical={chemical_select_entity}, Custom={custom_chemical_entity}, Method={method_select_entity}, Equipment={equipment_select_entity}, Rate={rate_override_entity}, CustomRate={custom_rate_entity}, Date={application_date_entity}")
        
        # Get current values
        chemical_select = self._hass.states.get(chemical_select_entity) if chemical_select_entity else None
        custom_chemical = self._hass.states.get(custom_chemical_entity) if custom_chemical_entity else None
        method_select = self._hass.states.get(method_select_entity) if method_select_entity else None
        equipment_select = self._hass.states.get(equipment_select_entity) if equipment_select_entity else None
        rate_override = self._hass.states.get(rate_override_entity) if rate_override_entity else None
        custom_rate = self._hass.states.get(custom_rate_entity) if custom_rate_entity else None
        application_date = self._hass.states.get(application_date_entity) if application_date_entity else None
        
        _LOGGER.warning(f"Entity states - Chemical: {chemical_select.state if chemical_select else 'NOT FOUND'}, Custom: {custom_chemical.state if custom_chemical else 'NOT FOUND'}, Method: {method_select.state if method_select else 'NOT FOUND'}, Equipment: {equipment_select.state if equipment_select else 'NOT FOUND'}, Rate: {rate_override.state if rate_override else 'NOT FOUND'}, CustomRate: {custom_rate.state if custom_rate else 'NOT FOUND'}, Date: {application_date.state if application_date else 'NOT FOUND'}")
        
        # Determine application method
        if equipment_select and equipment_select.state != "None":
            # Get method from equipment type
            equipment_type = equipment_select.attributes.get("equipment_type", "sprayer")
            method = equipment_type.title()  # "sprayer" -> "Sprayer", "spreader" -> "Spreader"
            _LOGGER.warning(f"Using method from equipment: {method}")
        elif method_select:
            # Use manual method selection
            method = method_select.state
            _LOGGER.warning(f"Using manual method selection: {method}")
        else:
            # Fallback
            method = "Sprayer"
            _LOGGER.warning(f"Using fallback method: {method}")
        
        # Determine which chemical to use
        selected_chemical = chemical_select.state if chemical_select else None
        custom_chemical_value = custom_chemical.state if custom_chemical else ""
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
        
        # Call the service with the selected values (include zone info for proper data isolation)
        service_data = {
            "chemical_select": chemical_to_use if selected_chemical != "Custom" else None,
            "custom_chemical": chemical_to_use if selected_chemical == "Custom" else None,
            "method": method,
            "rate_override": rate_override_value,
            "custom_rate": custom_rate_value,
            "application_date": application_date_value,
            "_zone_entry_id": self._entry.entry_id  # Add zone context for proper data isolation
        }
        
        _LOGGER.warning(f"Calling service with data: {service_data}")
        
        await self._hass.services.async_call(
            DOMAIN, "log_application",
            service_data,
            blocking=True
        ) 
