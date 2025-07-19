from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
import logging

from .const import DOMAIN, CHEMICALS, GRASS_TYPE_LIST
from homeassistant.helpers.storage import Store
from .const import STORAGE_VERSION, EQUIPMENT_STORAGE_KEY

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up select entities for Lawn Manager."""
    _LOGGER.warning(f"🔍 Setting up Lawn Manager select entities for entry {entry.entry_id} - DEBUG")
    
    # Check if entities already exist
    existing_entities = []
    for state in hass.states.async_all():
        if entry.entry_id in state.entity_id and state.entity_id.startswith("select."):
            existing_entities.append(state.entity_id)
    
    _LOGGER.warning(f"🔍 Found existing select entities: {existing_entities}")
    
    # Get chemical options from CHEMICALS constant
    chemical_options = list(CHEMICALS.keys()) + ["Custom"]
    
    # Application method options (static)
    method_options = ["Sprayer", "Spreader", "Hand Application", "Other"]
    
    # Load equipment for equipment selector
    equipment_store = Store(hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
    equipment_data = await equipment_store.async_load() or {}
    
    # Create equipment options - put actual equipment first, then None as fallback
    equipment_options = []
    for eq_id, eq_info in equipment_data.items():
        equipment_options.append(eq_info.get("friendly_name", f"Equipment {eq_id}"))
    
    # Add None as fallback option (will only be default if no equipment exists)
    equipment_options.append("None")
    
    _LOGGER.warning(f"Chemical options: {chemical_options}")
    _LOGGER.warning(f"Method options: {method_options}")
    _LOGGER.warning(f"Equipment options: {equipment_options}")
    
    # Rate override options
    rate_options = ["Default", "Light (50%)", "Heavy (150%)", "Extra Heavy (200%)", "Custom"]
    
    # Cut type options for mowing
    cut_type_options = ["Regular Maintenance", "Scalp", "First Cut of Season", "Pre-Winter Cut", "HOC Reset", "Aerate", "Dethatch"]
    
    # Base entities (always created)
    entities = []
    
    # Create activity type select first
    activity_type_select = LawnCutTypeSelect(hass, entry, cut_type_options)
    _LOGGER.warning(f"🔍 Creating activity type select: {activity_type_select._attr_unique_id}")
    entities.append(activity_type_select)
    
    # Create other entities
    entities.extend([
        LawnChemicalSelect(hass, entry, chemical_options),
        LawnRateOverrideSelect(hass, entry, rate_options),
    ])
    
    # Log all entity IDs for debugging
    for entity in entities:
        _LOGGER.warning(f"🔍 Created entity: {entity._attr_unique_id} ({entity._attr_name})")
        # Check if entity already exists in states
        existing_state = hass.states.get(f"select.lawn_manager_{entity._attr_unique_id}")
        _LOGGER.warning(f"✓ Entity state exists: {existing_state is not None}")
    
    # Conditional method/equipment selection  
    has_actual_equipment = len(equipment_options) > 1 or (len(equipment_options) == 1 and equipment_options[0] != "None")
    if has_actual_equipment:
        # If equipment is available, use Equipment Selection instead of Application Method
        _LOGGER.warning(f"Equipment available ({len(equipment_options)-1} items), adding Equipment Selection entity")
        entities.append(LawnEquipmentSelect(hass, entry, equipment_options, equipment_data))
    else:
        # If no equipment, use manual Application Method selection
        _LOGGER.warning("No equipment available, adding Application Method entity")
        entities.append(LawnMethodSelect(hass, entry, method_options))
    
    _LOGGER.warning(f"Adding {len(entities)} select entities")
    async_add_entities(entities)

class LawnChemicalSelect(SelectEntity):
    def __init__(self, hass, entry, options):
        self._hass = hass
        self._entry = entry
        self._attr_name = "🧪 Chemical Selection"
        self._attr_unique_id = f"{entry.entry_id}_chemical_selection"
        _LOGGER.warning(f"Creating chemical select entity with unique_id: {self._attr_unique_id}")
        self._attr_options = options
        self._attr_current_option = options[0]  # Default to first option
        self._attr_icon = "mdi:flask-outline"
        self._attr_entity_category = None  # Main control

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
        self._attr_name = "🧪 Application Rate"
        self._attr_unique_id = f"{entry.entry_id}_application_rate"
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

class LawnEquipmentSelect(SelectEntity):
    """Select entity for choosing equipment."""
    
    def __init__(self, hass, entry, options, equipment_data):
        self._hass = hass
        self._entry = entry
        self._equipment_data = equipment_data
        self._attr_name = "Equipment Selection"
        self._attr_unique_id = f"{entry.entry_id}_equipment_select"
        self._attr_options = options
        self._attr_current_option = options[0] if options else "None"
        self._attr_icon = "mdi:tools"
        self._unsub_dispatcher = None

    async def async_added_to_hass(self):
        """Subscribe to equipment updates when entity is added."""
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, "lawn_manager_equipment_update", self._handle_equipment_update
        )

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
        
        # Reset selection if current option no longer exists
        if self._attr_current_option not in new_options:
            self._attr_current_option = "None"
        
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

class LawnCutTypeSelect(SelectEntity):
    """Select entity for choosing cut type."""
    
    def __init__(self, hass, entry, options):
        self._hass = hass
        self._entry = entry
        self._attr_name = "🌿 Activity Type Selection"
        self._attr_unique_id = f"{entry.entry_id}_activity_type_selection"
        self._attr_options = options
        self._attr_current_option = options[0]  # Default to "Regular Maintenance"
        self._attr_icon = "mdi:content-cut"
        self._attr_entity_category = None  # Main control

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    @property
    def extra_state_attributes(self):
        return {
            "help": "Select the type of lawn activity being performed",
            "scalp_note": "Scalp = Very low cut to remove thatch",
            "maintenance_note": "Regular Maintenance = Normal weekly mowing",
            "hoc_reset_note": "HOC Reset = Adjusting mower height settings",
            "aerate_note": "Aerate = Core aeration to improve soil compaction",
            "dethatch_note": "Dethatch = Removing thatch buildup from lawn"
        }

    async def async_select_option(self, option: str) -> None:
        """Select new cut type option."""
        self._attr_current_option = option
        self.async_write_ha_state() 
