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

        # Add mow sensor
        self.mow_sensor = LawnMowSensor(self.entry.entry_id, yard_zone, location, mow_interval, store)
        entities = [self.mow_sensor]

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
        self._name = f"{yard_zone} Mow Interval"
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
        return self._name

    @property
    def state(self):
        if self._last_mow:
            return (dt_util.now() - self._last_mow).days
        return None

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
        return f"lawn_manager_{self._entry_id}_{self._name.lower().replace(' ', '_')}_sensor"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC


class ChemicalApplicationSensor(SensorEntity):
    def __init__(self, entry_id, chemical_name, chem_data):
        self._entry_id = entry_id
        self._chemical_name = chemical_name
        self._last_applied = chem_data.get("last_applied")
        self._interval_days = chem_data.get("interval_days", 30)
        self._amount_lb = chem_data.get("amount_lb_per_1000sqft", 1.0)
        self._amount_oz = chem_data.get("amount_oz_per_1000sqft", 16.0)
        self._method = chem_data.get("method", "Unknown")
        self._state = None
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
        if not self._last_applied:
            self._state = None
            return

        try:
            last_dt = dt_util.as_local(datetime.strptime(self._last_applied, "%Y-%m-%d"))
            self._state = (dt_util.now() - last_dt).days
        except Exception as e:
            _LOGGER.error("Error parsing last_applied for %s: %s", self._chemical_name, e)
            self._state = None

    @property
    def name(self):
        return f"{self._chemical_name} Application"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        if not self._last_applied:
            return {}
        try:
            last_dt = datetime.strptime(self._last_applied, "%Y-%m-%d")
            next_due = last_dt + timedelta(days=self._interval_days)
            return {
                "last_applied": self._last_applied,
                "next_due": next_due.strftime("%Y-%m-%d"),
                "interval_days": self._interval_days,
                "amount_lb_per_1000sqft": self._amount_lb,
                "amount_oz_per_1000sqft": self._amount_oz,
                "method": self._method
            }
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
