from datetime import datetime, timedelta
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, DEFAULT_MOW_INTERVAL

_LOGGER = logging.getLogger(__name__)
STORAGE_KEY = "lawn_manager_data"
STORAGE_VERSION = 1


class LawnManagerSensorManager:
    def __init__(self, hass, entry, async_add_entities):
        self.hass = hass
        self.entry = entry
        self.async_add_entities = async_add_entities
        self.known_chemicals = set()
        self.chemical_sensors = {}
        self.mow_sensor = None
        self._unsub_dispatcher = None

    async def async_setup(self):
        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        data = await store.async_load() or {}
        config = self.entry.data
        yard_zone = config.get("yard_zone", "Lawn")
        location = config.get("location", "Unknown")
        mow_interval = config.get("mow_interval", DEFAULT_MOW_INTERVAL)

        # Add core mow tracking sensors (always created)
        self.mow_sensor = LawnMowSensor(self.entry.entry_id, yard_zone, location, mow_interval, store)
        self.mow_due_sensor = LawnMowDueSensor(self.entry.entry_id, yard_zone, location, mow_interval, store)
        entities = [self.mow_sensor, self.mow_due_sensor]

        # Add chemical sensors
        for chem_name, chem_data in data.get("applications", {}).items():
            self.known_chemicals.add(chem_name)
            sensor = ChemicalApplicationSensor(self.entry.entry_id, chem_name, chem_data)
            self.chemical_sensors[chem_name] = sensor
            entities.append(sensor)

        self.async_add_entities(entities, update_before_add=True)

        # Listen for updates
        self._unsub_dispatcher = async_dispatcher_connect(self.hass, "lawn_manager_update", self._handle_update_signal)

    async def _handle_update_signal(self):
        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        data = await store.async_load() or {}
        current_chems = set(data.get("applications", {}).keys())
        new_chems = current_chems - self.known_chemicals
        removed_chems = self.known_chemicals - current_chems
        new_entities = []

        # Add new chemical sensors
        for chem_name in new_chems:
            chem_data = data["applications"][chem_name]
            sensor = ChemicalApplicationSensor(self.entry.entry_id, chem_name, chem_data)
            self.chemical_sensors[chem_name] = sensor
            new_entities.append(sensor)
            self.known_chemicals.add(chem_name)

        if new_entities:
            self.async_add_entities(new_entities)

        # Remove deleted chemical sensors
        for chem_name in removed_chems:
            sensor = self.chemical_sensors.pop(chem_name, None)
            if sensor:
                await sensor.async_remove()
            self.known_chemicals.remove(chem_name)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    manager = LawnManagerSensorManager(hass, entry, async_add_entities)
    await manager.async_setup()


class LawnMowSensor(SensorEntity):
    def __init__(self, entry_id, yard_zone, location, mow_interval, store):
        self._entry_id = entry_id
        self._yard_zone = yard_zone  # Store yard zone for name generation
        self._location = location
        self._mow_interval = mow_interval
        self._last_mow = None
        self._store = store
        self._unsub_dispatcher = None

    async def async_added_to_hass(self):
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, "lawn_manager_update", self._handle_update_signal
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    async def _handle_update_signal(self):
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        data = await self._store.async_load() or {}
        try:
            self._last_mow = dt_util.as_local(
                datetime.strptime(data.get("last_mow"), "%Y-%m-%d")
            )
        except Exception:
            self._last_mow = dt_util.now() - timedelta(days=self._mow_interval + 1)

    @property
    def name(self):
        return f"{self._yard_zone} Last Mow Date"

    @property
    def state(self):
        if self._last_mow:
            return self._last_mow.strftime("%Y-%m-%d")
        return "Never"

    @property
    def unit_of_measurement(self):
        return None

    @property
    def icon(self):
        return "mdi:calendar-check"

    @property
    def extra_state_attributes(self):
        if not self._last_mow:
            return {}
        next_due = self._last_mow + timedelta(days=self._mow_interval)
        return {
            "location": self._location,
            "last_mow": self._last_mow.strftime("%Y-%m-%d"),
            "next_mow_due": next_due.strftime("%Y-%m-%d"),
        }

    @property
    def unique_id(self):
        return f"lawn_manager_{self._entry_id}_{self._yard_zone.lower().replace(' ', '_')}_last_mow"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    @property
    def entity_category(self):
        return None  # Remove diagnostic category to make it a regular sensor


class LawnMowDueSensor(SensorEntity):
    def __init__(self, entry_id, yard_zone, location, mow_interval, store):
        self._entry_id = entry_id
        self._yard_zone = yard_zone
        self._location = location
        self._mow_interval = mow_interval
        self._last_mow = None
        self._store = store
        self._unsub_dispatcher = None

    async def async_added_to_hass(self):
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, "lawn_manager_update", self._handle_update_signal
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    async def _handle_update_signal(self):
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        data = await self._store.async_load() or {}
        try:
            self._last_mow = dt_util.as_local(
                datetime.strptime(data.get("last_mow"), "%Y-%m-%d")
            )
        except Exception:
            self._last_mow = None

    @property
    def name(self):
        return f"{self._yard_zone} Mow Due Date"

    @property
    def state(self):
        if self._last_mow:
            due_date = self._last_mow + timedelta(days=self._mow_interval)
            return due_date.strftime("%Y-%m-%d")
        return "Not Set"

    @property
    def icon(self):
        return "mdi:calendar-clock"

    @property
    def extra_state_attributes(self):
        if not self._last_mow:
            return {
                "mow_interval_days": self._mow_interval,
                "last_mow": "Never",
                "days_until_due": "Unknown"
            }
        
        due_date = self._last_mow + timedelta(days=self._mow_interval)
        days_until_due = (due_date - dt_util.now()).days
        
        return {
            "mow_interval_days": self._mow_interval,
            "last_mow": self._last_mow.strftime("%Y-%m-%d"),
            "days_until_due": days_until_due,
            "overdue": days_until_due < 0
        }

    @property
    def unique_id(self):
        return f"lawn_manager_{self._entry_id}_{self._yard_zone.lower().replace(' ', '_')}_mow_due"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }


class ChemicalApplicationSensor(SensorEntity):
    def __init__(self, entry_id, chemical_name, chem_data):
        self._entry_id = entry_id
        self._chemical_name = chemical_name
        self._last_applied = chem_data.get("last_applied")
        self._interval_days = chem_data.get("interval_days", 30)
        # Support both old and new format for backward compatibility
        self._default_amount_lb = chem_data.get("default_amount_lb_per_1000sqft", chem_data.get("amount_lb_per_1000sqft", 1.0))
        self._default_amount_oz = chem_data.get("default_amount_oz_per_1000sqft", chem_data.get("amount_oz_per_1000sqft", 16.0))
        self._applied_amount_lb = chem_data.get("applied_amount_lb_per_1000sqft", self._default_amount_lb)
        self._applied_amount_oz = chem_data.get("applied_amount_oz_per_1000sqft", self._default_amount_oz)
        self._rate_multiplier = chem_data.get("rate_multiplier", 1.0)
        self._rate_description = chem_data.get("rate_description", "Default")
        self._method = chem_data.get("method", "Unknown")
        self._state = None
        self._unsub_dispatcher = None
        
        # Calculate initial state
        if self._last_applied:
            try:
                last_dt = dt_util.as_local(datetime.strptime(self._last_applied, "%Y-%m-%d"))
                self._state = (dt_util.now() - last_dt).days
            except Exception:
                self._state = None

    async def async_added_to_hass(self):
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, "lawn_manager_update", self._handle_update_signal
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    async def _handle_update_signal(self):
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        # Reload data from storage to get latest chemical data
        from homeassistant.helpers.storage import Store
        from .const import STORAGE_VERSION, STORAGE_KEY
        
        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
        data = await store.async_load() or {}
        
        # Update chemical data from storage
        chem_data = data.get("applications", {}).get(self._chemical_name, {})
        if chem_data:
            self._last_applied = chem_data.get("last_applied")
            self._interval_days = chem_data.get("interval_days", 30)
            self._default_amount_lb = chem_data.get("default_amount_lb_per_1000sqft", chem_data.get("amount_lb_per_1000sqft", 1.0))
            self._default_amount_oz = chem_data.get("default_amount_oz_per_1000sqft", chem_data.get("amount_oz_per_1000sqft", 16.0))
            self._applied_amount_lb = chem_data.get("applied_amount_lb_per_1000sqft", self._default_amount_lb)
            self._applied_amount_oz = chem_data.get("applied_amount_oz_per_1000sqft", self._default_amount_oz)
            self._rate_multiplier = chem_data.get("rate_multiplier", 1.0)
            self._rate_description = chem_data.get("rate_description", "Default")
            self._method = chem_data.get("method", "Unknown")
        
        # Calculate state (days since application)
        if not self._last_applied:
            self._state = None
            return

        try:
            if self._last_applied:
                last_dt = dt_util.as_local(datetime.strptime(self._last_applied, "%Y-%m-%d"))
                self._state = (dt_util.now() - last_dt).days
            else:
                self._state = None
        except Exception as e:
            _LOGGER.error("Error parsing last_applied for %s: %s", self._chemical_name, e)
            self._state = None

    @property
    def name(self):
        if self._state is None:
            return f"{self._chemical_name} Application"
        elif self._state == 0:
            return f"{self._chemical_name} (Applied Today)"
        elif self._state == 1:
            return f"{self._chemical_name} (Applied Yesterday)"
        else:
            return f"{self._chemical_name} ({self._state} Days Ago)"

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "days"

    @property
    def extra_state_attributes(self):
        if not self._last_applied:
            return {}
        try:
            if self._last_applied:
                last_dt = datetime.strptime(self._last_applied, "%Y-%m-%d")
                next_due = last_dt + timedelta(days=self._interval_days)
                return {
                    "last_applied": self._last_applied,
                    "next_due": next_due.strftime("%Y-%m-%d"),
                    "interval_days": self._interval_days,
                    "default_amount_lb_per_1000sqft": self._default_amount_lb,
                    "default_amount_oz_per_1000sqft": self._default_amount_oz,
                    "applied_amount_lb_per_1000sqft": self._applied_amount_lb,
                    "applied_amount_oz_per_1000sqft": self._applied_amount_oz,
                    "rate_multiplier": self._rate_multiplier,
                    "rate_description": self._rate_description,
                    "method": self._method
                }
            else:
                return {}
        except Exception as e:
            _LOGGER.error("Error generating attributes for %s: %s", self._chemical_name, e)
            return {}

    @property
    def unique_id(self):
        return f"lawn_manager_{self._entry_id}_{self._chemical_name.lower().replace(' ', '_')}_application"

    @property
    def icon(self):
        return "mdi:flask-outline"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }
