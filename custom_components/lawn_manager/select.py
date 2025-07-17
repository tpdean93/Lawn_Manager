from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging

from .const import DOMAIN, CHEMICALS, GRASS_TYPE_LIST
from homeassistant.helpers.storage import Store
from .const import STORAGE_VERSION, EQUIPMENT_STORAGE_KEY

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    _LOGGER.warning("Setting up Lawn Manager select entities - DEBUG")
    
    # Get chemical options from CHEMICALS constant
    chemical_options = list(CHEMICALS.keys()) + ["Custom"]
    
    # Application method options (static)
    method_options = ["Sprayer", "Spreader", "Hand Application", "Other"]
    
    # Load equipment for equipment selector
    equipment_store = Store(hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
    equipment_data = await equipment_store.async_load() or {}
    
    # Create equipment options
    equipment_options = ["None"]
    for eq_id, eq_info in equipment_data.items():
        equipment_options.append(eq_info.get("friendly_name", f"Equipment {eq_id}"))
    
    _LOGGER.warning(f"Chemical options: {chemical_options}")
    _LOGGER.warning(f"Method options: {method_options}")
    _LOGGER.warning(f"Equipment options: {equipment_options}")
    
    # Rate override options
    rate_options = ["Default", "Light (50%)", "Heavy (150%)", "Extra Heavy (200%)", "Custom"]
    
    # Create entities in strict order to ensure Equipment/Method selection appears first
    entities = []
    
    # FIRST: Equipment/Method selection (use "00_" prefix for sorting)
    if len(equipment_options) > 1:  # More than just "None"
        # If equipment is available, use Equipment Selection
        _LOGGER.warning(f"Equipment available ({len(equipment_options)-1} items), adding Equipment Selection entity")
        # Default to first actual equipment (skip "None") - ensure it's not "None"
        default_equipment = equipment_options[1] if len(equipment_options) > 1 else "None"
        _LOGGER.warning(f"Setting Equipment Selection default to: {default_equipment}")
        entities.append(LawnEquipmentSelect(hass, entry, equipment_options, equipment_data, default_equipment))
    else:
        # If no equipment, use manual Application Method selection
        _LOGGER.warning("No equipment available, adding Application Method entity")
        entities.append(LawnMethodSelect(hass, entry, method_options))
    
    # Add other entities AFTER equipment/method selection (these will sort after due to higher prefixes)
    entities.extend([
        LawnChemicalSelect(hass, entry, chemical_options),
        LawnRateOverrideSelect(hass, entry, rate_options),
    ])
    
    _LOGGER.warning(f"Adding {len(entities)} select entities in order: {[entity._attr_name for entity in entities]}")
    async_add_entities(entities)

class LawnChemicalSelect(SelectEntity):
    def __init__(self, hass, entry, options):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Chemical Selection"
        self._attr_unique_id = f"bbb_chemical_{entry.entry_id}"
        _LOGGER.warning(f"Creating chemical select entity with unique_id: {self._attr_unique_id}")
        self._attr_options = options
        # Default to first actual chemical (not "None" or "Custom")
        default_chemical = None
        for option in options:
            if option not in ["None", "Custom"]:
                default_chemical = option
                break
        self._attr_current_option = default_chemical or options[0]  # Fallback to first if no good option
        _LOGGER.warning(f"Chemical Selection defaulted to: {self._attr_current_option}")
        self._attr_icon = "mdi:flask-outline"

    async def async_added_to_hass(self):
        """Ensure proper default selection when entity is first added."""
        # If current selection is "None" or "Custom", default to first actual chemical
        if self._attr_current_option in ["None", "Custom"]:
            for option in self._attr_options:
                if option not in ["None", "Custom"]:
                    self._attr_current_option = option
                    _LOGGER.warning(f"Chemical Selection entity added - defaulted to: {self._attr_current_option}")
                    self.async_write_ha_state()
                    break

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

class LawnRateOverrideSelect(SelectEntity):
    def __init__(self, hass, entry, options):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Application Rate"
        self._attr_unique_id = f"ccc_rate_{entry.entry_id}"
        self._attr_options = options
        self._attr_current_option = options[0]  # Default to "Default"
        self._attr_icon = "mdi:gauge"

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
        self._attr_unique_id = f"aaa_method_{entry.entry_id}"
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

class LawnEquipmentSelect(SelectEntity):
    """Select entity for choosing equipment."""
    
    def __init__(self, hass, entry, options, equipment_data, default_equipment):
        self._hass = hass
        self._entry = entry
        self._equipment_data = equipment_data
        self._attr_name = "Equipment Selection"
        self._attr_unique_id = f"aaa_equipment_{entry.entry_id}"
        self._attr_entity_category = None  # Force as main control entity # Changed unique_id to sort early
        self._attr_options = options
        self._attr_current_option = default_equipment
        self._attr_icon = "mdi:tools"
        self._unsub_dispatcher = None

    async def async_added_to_hass(self):
        """Subscribe to equipment updates when entity is added."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, "lawn_manager_equipment_update", self._handle_equipment_update
        )
        
        # Ensure proper default selection when entity is first added
        if len(self._attr_options) > 1 and self._attr_current_option == "None":
            self._attr_current_option = self._attr_options[1]  # First actual equipment
            _LOGGER.warning(f"Equipment Selection entity added - defaulted to: {self._attr_current_option}")
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self):
        """Unsubscribe from updates when entity is removed."""
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    async def _handle_equipment_update(self):
        """Handle equipment update signal by reloading equipment options."""
        # Reload equipment data
        equipment_store = Store(self._hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
        equipment_data = await equipment_store.async_load() or {}
        self._equipment_data = equipment_data
        
        # Rebuild options
        new_options = ["None"]
        for eq_id, eq_info in equipment_data.items():
            new_options.append(eq_info.get("friendly_name", f"Equipment {eq_id}"))
        
        # Update options
        self._attr_options = new_options
        
        # Always default to first actual equipment if available (not "None")
        if len(new_options) > 1:
            # If current selection is "None" or not in new options, default to first equipment
            if self._attr_current_option == "None" or self._attr_current_option not in new_options:
                self._attr_current_option = new_options[1]  # First actual equipment
                _LOGGER.warning(f"Equipment Selection defaulted to: {self._attr_current_option}")
        else:
            # No equipment available, reset to "None"
            self._attr_current_option = "None"
            _LOGGER.warning("No equipment available, Equipment Selection set to None")
        
        # Update the entity
        self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    @property
    def extra_state_attributes(self):
        """Return equipment details for the selected equipment."""
        if self._attr_current_option == "None" or not self._equipment_data:
            return {}
        
        # Find the selected equipment by friendly name
        for eq_id, eq_data in self._equipment_data.items():
            friendly_name = eq_data.get("friendly_name", f"Equipment {eq_id}")
            if friendly_name == self._attr_current_option:
                return {
                    "equipment_id": eq_id,
                    "equipment_type": eq_data.get("type"),
                    "brand": eq_data.get("brand"),
                    "capacity": eq_data.get("capacity"),
                    "capacity_unit": eq_data.get("capacity_unit"),
                    "full_details": eq_data
                }
        return {}

    async def async_select_option(self, option: str) -> None:
        """Select new equipment option."""
        self._attr_current_option = option
        self.async_write_ha_state() 
