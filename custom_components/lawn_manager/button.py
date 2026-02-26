from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.storage import Store
from homeassistant.helpers.dispatcher import async_dispatcher_send
import logging

from .const import DOMAIN, CHEMICALS, EQUIPMENT_STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entities = [
        LogMowButton(hass, entry),
        LogChemicalButton(hass, entry),
        CalculateRateButton(hass, entry),
    ]
    async_add_entities(entities)


class LogMowButton(ButtonEntity):
    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Log Lawn Activity"
        self._attr_unique_id = f"{entry.entry_id}_log_mow"
        self._attr_icon = "mdi:grass"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Mowing",
        }

    async def async_press(self):
        activity_type_entity = None
        height_of_cut_entity = None
        application_date_entity = None

        for state in self._hass.states.async_all():
            entity_id = state.entity_id
            if entity_id.startswith("select.") and "activity_type_selection" in entity_id:
                activity_type_entity = entity_id
            elif entity_id.startswith("number.") and "height_of_cut" in entity_id:
                height_of_cut_entity = entity_id
            elif entity_id.startswith("date.") and "application_date" in entity_id:
                application_date_entity = entity_id

        activity_type = self._hass.states.get(activity_type_entity) if activity_type_entity else None
        height_of_cut = self._hass.states.get(height_of_cut_entity) if height_of_cut_entity else None
        application_date = self._hass.states.get(application_date_entity) if application_date_entity else None

        activity_type_value = activity_type.state if activity_type else "Regular Maintenance"
        height_of_cut_value = None
        if height_of_cut and height_of_cut.state:
            try:
                height_of_cut_value = float(height_of_cut.state)
            except (ValueError, TypeError):
                pass

        application_date_value = application_date.state if application_date else None

        service_data = {
            "cut_type": activity_type_value,
            "_zone_entry_id": self._entry.entry_id
        }
        if application_date_value:
            service_data["application_date"] = application_date_value
        if height_of_cut_value is not None:
            service_data["height_of_cut"] = height_of_cut_value

        await self._hass.services.async_call(
            DOMAIN, "log_lawn_activity", service_data, blocking=True
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
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Chemical Application",
        }

    async def async_press(self):
        chemical_select_entity = None
        custom_chemical_entity = None
        method_select_entity = None
        equipment_select_entity = None
        rate_override_entity = None
        custom_rate_entity = None
        custom_rate_unit_entity = None
        application_date_entity = None

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
            elif entity_id.startswith("select.") and "custom_rate_unit" in entity_id:
                custom_rate_unit_entity = entity_id
            elif entity_id.startswith("date.") and "application_date" in entity_id:
                application_date_entity = entity_id

        chemical_select = self._hass.states.get(chemical_select_entity) if chemical_select_entity else None
        custom_chemical = self._hass.states.get(custom_chemical_entity) if custom_chemical_entity else None
        method_select = self._hass.states.get(method_select_entity) if method_select_entity else None
        equipment_select = self._hass.states.get(equipment_select_entity) if equipment_select_entity else None
        rate_override = self._hass.states.get(rate_override_entity) if rate_override_entity else None
        custom_rate = self._hass.states.get(custom_rate_entity) if custom_rate_entity else None
        custom_rate_unit = self._hass.states.get(custom_rate_unit_entity) if custom_rate_unit_entity else None
        application_date = self._hass.states.get(application_date_entity) if application_date_entity else None

        # Determine application method
        if equipment_select and equipment_select.state != "None":
            equipment_type = equipment_select.attributes.get("equipment_type", "sprayer")
            method = equipment_type.title()
        elif method_select:
            method = method_select.state
        else:
            method = "Sprayer"

        selected_chemical = chemical_select.state if chemical_select else None
        custom_chemical_value = custom_chemical.state if custom_chemical else ""
        rate_override_value = rate_override.state if rate_override else "Default"
        custom_rate_value = custom_rate.state if custom_rate else "1.0"
        custom_rate_unit_value = custom_rate_unit.state if custom_rate_unit else "Multiplier (1.0x = default rate)"
        application_date_value = application_date.state if application_date else None

        if selected_chemical == "Custom" and custom_chemical_value.strip():
            chemical_to_use = custom_chemical_value.strip()
        elif selected_chemical and selected_chemical != "Custom":
            chemical_to_use = selected_chemical
        else:
            _LOGGER.error("No chemical selected or custom chemical name provided")
            return

        service_data = {
            "chemical_select": chemical_to_use if selected_chemical != "Custom" else None,
            "custom_chemical": chemical_to_use if selected_chemical == "Custom" else None,
            "method": method,
            "rate_override": rate_override_value,
            "custom_rate": custom_rate_value,
            "custom_rate_unit": custom_rate_unit_value,
            "application_date": application_date_value,
            "_zone_entry_id": self._entry.entry_id
        }

        await self._hass.services.async_call(
            DOMAIN, "log_application",
            service_data,
            blocking=True
        )


class CalculateRateButton(ButtonEntity):
    """Button to calculate application rate directly from controls."""

    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Calculate Application Rate"
        self._attr_unique_id = f"{entry.entry_id}_calculate_rate"
        self._attr_icon = "mdi:calculator-variant"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Chemical Application",
        }

    async def async_press(self):
        """Calculate application rate from current control selections."""
        chemical_select_entity = None
        custom_chemical_entity = None
        equipment_select_entity = None

        for state in self._hass.states.async_all():
            entity_id = state.entity_id
            if entity_id.startswith("select.") and "chemical_selection" in entity_id:
                chemical_select_entity = entity_id
            elif entity_id.startswith("text.") and "custom_chemical_name" in entity_id:
                custom_chemical_entity = entity_id
            elif entity_id.startswith("select.") and "equipment_select" in entity_id:
                equipment_select_entity = entity_id

        chemical_select = self._hass.states.get(chemical_select_entity) if chemical_select_entity else None
        custom_chemical = self._hass.states.get(custom_chemical_entity) if custom_chemical_entity else None
        equipment_select = self._hass.states.get(equipment_select_entity) if equipment_select_entity else None

        selected_chemical = chemical_select.state if chemical_select else None
        custom_chemical_value = custom_chemical.state if custom_chemical else ""

        if selected_chemical == "Custom" and custom_chemical_value.strip():
            chemical = custom_chemical_value.strip()
        elif selected_chemical and selected_chemical != "Custom":
            chemical = selected_chemical
        else:
            _LOGGER.error("No chemical selected for rate calculation")
            return

        equipment_name = None
        if equipment_select and equipment_select.state != "None":
            equipment_name = equipment_select.state

        if not equipment_name:
            _LOGGER.error("No equipment selected for rate calculation")
            return

        zone = self._entry.data.get("yard_zone", "Unknown")

        service_data = {
            "chemical": chemical,
            "equipment_name": equipment_name,
            "zone": zone,
        }

        _LOGGER.info("Calculating application rate: %s", service_data)

        result = await self._hass.services.async_call(
            DOMAIN, "calculate_application_rate",
            service_data,
            blocking=True,
            return_response=True,
        )

        if result:
            # Store the calculation result in a sensor via dispatcher
            async_dispatcher_send(
                self._hass,
                f"lawn_manager_rate_calculated_{self._entry.entry_id}",
                result
            )
            _LOGGER.info("Application rate calculated: %s", result)
