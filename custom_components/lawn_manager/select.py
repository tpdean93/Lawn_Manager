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
    chemical_options = list(CHEMICALS.keys()) + ["Custom"]
    method_options = ["Sprayer", "Spreader", "Hand Application", "Other"]

    equipment_store = Store(hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
    equipment_data = await equipment_store.async_load() or {}

    equipment_options = []
    for eq_id, eq_info in equipment_data.items():
        equipment_options.append(eq_info.get("friendly_name", f"Equipment {eq_id}"))
    equipment_options.append("None")

    rate_options = ["Default", "Light (50%)", "Heavy (150%)", "Extra Heavy (200%)", "Custom"]
    cut_type_options = ["Regular Maintenance", "Scalp", "First Cut of Season", "Pre-Winter Cut", "HOC Reset", "Aerate", "Dethatch"]

    entities = []

    # --- Mowing Controls ---
    activity_type_select = LawnCutTypeSelect(hass, entry, cut_type_options)
    entities.append(activity_type_select)

    # --- Chemical Application Controls ---
    entities.extend([
        LawnChemicalSelect(hass, entry, chemical_options),
        LawnRateOverrideSelect(hass, entry, rate_options),
    ])

    # Equipment or method selection
    has_actual_equipment = len(equipment_options) > 1 or (len(equipment_options) == 1 and equipment_options[0] != "None")
    if has_actual_equipment:
        entities.append(LawnEquipmentSelect(hass, entry, equipment_options, equipment_data))
    else:
        entities.append(LawnMethodSelect(hass, entry, method_options))

    # --- Chemical Application Rate Unit for Custom ---
    entities.append(LawnCustomRateUnitSelect(hass, entry))

    async_add_entities(entities)


class LawnChemicalSelect(SelectEntity):
    def __init__(self, hass, entry, options):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Chemical Selection"
        self._attr_unique_id = f"{entry.entry_id}_chemical_selection"
        self._attr_options = options
        self._attr_current_option = options[0]
        self._attr_icon = "mdi:flask-outline"
        self._attr_entity_category = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Chemical Application",
        }

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


class LawnRateOverrideSelect(SelectEntity):
    def __init__(self, hass, entry, options):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Application Rate"
        self._attr_unique_id = f"{entry.entry_id}_application_rate"
        self._attr_options = options
        self._attr_current_option = options[0]
        self._attr_icon = "mdi:gauge"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Chemical Application",
        }

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


class LawnCustomRateUnitSelect(SelectEntity):
    """Select entity for choosing custom rate units (oz or lb per 1000sqft)."""

    def __init__(self, hass, entry):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Custom Rate Unit"
        self._attr_unique_id = f"{entry.entry_id}_custom_rate_unit"
        self._attr_options = [
            "Multiplier (1.0x = default rate)",
            "oz per 1,000 sq ft",
            "lb per 1,000 sq ft",
            "ml per 1,000 sq ft",
        ]
        self._attr_current_option = self._attr_options[0]
        self._attr_icon = "mdi:scale-balance"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Chemical Application",
        }

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self.async_write_ha_state()


class LawnMethodSelect(SelectEntity):
    def __init__(self, hass, entry, options):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Application Method"
        self._attr_unique_id = f"{entry.entry_id}_method_select"
        self._attr_options = options
        self._attr_current_option = options[0]
        self._attr_icon = "mdi:spray"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Chemical Application",
        }

    async def async_select_option(self, option: str) -> None:
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
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, "lawn_manager_equipment_update", self._handle_equipment_update
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    async def _handle_equipment_update(self):
        equipment_store = Store(self._hass, STORAGE_VERSION, EQUIPMENT_STORAGE_KEY)
        equipment_data = await equipment_store.async_load() or {}
        self._equipment_data = equipment_data

        new_options = []
        for eq_id, eq_info in equipment_data.items():
            new_options.append(eq_info.get("friendly_name", f"Equipment {eq_id}"))
        new_options.append("None")

        self._attr_options = new_options
        if self._attr_current_option not in new_options:
            self._attr_current_option = new_options[0] if len(new_options) > 1 else "None"

        self.async_write_ha_state()

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
        if self._attr_current_option == "None" or not self._equipment_data:
            return {}

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
        self._attr_current_option = option
        self.async_write_ha_state()


class LawnCutTypeSelect(SelectEntity):
    """Select entity for choosing cut type."""

    def __init__(self, hass, entry, options):
        self._hass = hass
        self._entry = entry
        self._attr_name = "Activity Type Selection"
        self._attr_unique_id = f"{entry.entry_id}_activity_type_selection"
        self._attr_options = options
        self._attr_current_option = options[0]
        self._attr_icon = "mdi:content-cut"
        self._attr_entity_category = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get("yard_zone", "Lawn Manager"),
            "manufacturer": "Lawn Manager",
            "model": "Mowing",
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
        self._attr_current_option = option
        self.async_write_ha_state()
