from datetime import datetime, timedelta
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, DEFAULT_MOW_INTERVAL, get_storage_key
from .weather_helper import WeatherHelper

_LOGGER = logging.getLogger(__name__)

try:
    from .seasonal_helper import SeasonalHelper
    SEASONAL_AVAILABLE = True
except ImportError:
    SEASONAL_AVAILABLE = False
    _LOGGER.warning("Seasonal helper not available - seasonal features disabled")

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
        zone_storage_key = get_storage_key(self.entry.entry_id)
        store = Store(self.hass, STORAGE_VERSION, zone_storage_key)
        data = await store.async_load() or {}
        config = self.entry.data
        yard_zone = config.get("yard_zone", "Lawn")
        location = config.get("location", "Unknown")
        mow_interval = config.get("mow_interval", DEFAULT_MOW_INTERVAL)

        weather_entity = config.get("weather_entity")
        grass_type = config.get("grass_type", "Bermuda")

        self.mow_sensor = LawnMowSensor(self.entry.entry_id, yard_zone, location, mow_interval, store)
        self.mow_due_sensor = LawnMowDueSensor(self.entry.entry_id, yard_zone, location, mow_interval, store, weather_entity, grass_type)
        entities = [self.mow_sensor, self.mow_due_sensor]

        if weather_entity:
            self.weather_sensor = LawnWeatherSensor(self.entry.entry_id, yard_zone, weather_entity, grass_type, location)
            entities.append(self.weather_sensor)

        if SEASONAL_AVAILABLE:
            self.seasonal_sensor = LawnSeasonalSensor(self.entry.entry_id, yard_zone, grass_type, location, weather_entity)
            entities.append(self.seasonal_sensor)

        applications = data.get("applications", {})
        if isinstance(applications, list):
            applications = {app.get("chemical_name", f"Chemical {i}"): app
                          for i, app in enumerate(applications) if isinstance(app, dict)}
            data["applications"] = applications
            await store.async_save(data)

        for chem_name, chem_data in applications.items():
            self.known_chemicals.add(chem_name)
            sensor = ChemicalApplicationSensor(self.entry.entry_id, yard_zone, chem_name, chem_data, weather_entity)
            self.chemical_sensors[chem_name] = sensor
            entities.append(sensor)

        self.equipment_sensor = EquipmentInventorySensor(self.entry.entry_id, yard_zone, location)
        entities.append(self.equipment_sensor)

        # Rate calculation result sensor
        self.rate_sensor = RateCalculationSensor(self.entry.entry_id, yard_zone)
        entities.append(self.rate_sensor)

        # Unified activity history sensor
        self.history_sensor = ActivityHistorySensor(self.entry.entry_id, yard_zone)
        entities.append(self.history_sensor)

        self.async_add_entities(entities, update_before_add=False)

        signal_name = f"lawn_manager_update_{self.entry.entry_id}"
        self._unsub_dispatcher = async_dispatcher_connect(self.hass, signal_name, self._handle_update_signal)
        self._unsub_equipment_dispatcher = async_dispatcher_connect(self.hass, "lawn_manager_equipment_update", self._handle_equipment_update_signal)

    async def _handle_update_signal(self):
        zone_storage_key = get_storage_key(self.entry.entry_id)
        store = Store(self.hass, STORAGE_VERSION, zone_storage_key)
        data = await store.async_load() or {}

        current_chems = set(data.get("applications", {}).keys())
        new_chems = current_chems - self.known_chemicals

        if new_chems:
            new_entities = []
            config = self.entry.data
            yard_zone = config.get("yard_zone", "Lawn")

            for chem_name in new_chems:
                chem_data = data["applications"][chem_name]
                sensor = ChemicalApplicationSensor(
                    self.entry.entry_id,
                    yard_zone,
                    chem_name,
                    chem_data,
                    self.mow_sensor._weather_entity if hasattr(self.mow_sensor, '_weather_entity') else None
                )
                self.chemical_sensors[chem_name] = sensor
                new_entities.append(sensor)

            if new_entities:
                self.async_add_entities(new_entities)

            self.known_chemicals = current_chems

        for sensor in self.chemical_sensors.values():
            await sensor.async_update()
            sensor.async_write_ha_state()

    async def _handle_equipment_update_signal(self):
        if hasattr(self, 'equipment_sensor') and self.equipment_sensor:
            await self.equipment_sensor.async_update()
            self.equipment_sensor.async_write_ha_state()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    manager = LawnManagerSensorManager(hass, entry, async_add_entities)
    await manager.async_setup()
    return True


class LawnMowSensor(SensorEntity):
    def __init__(self, entry_id, yard_zone, location, mow_interval, store):
        self._entry_id = entry_id
        self._yard_zone = yard_zone
        self._location = location
        self._mow_interval = mow_interval
        self._last_mow = None
        self._store = store
        self._unsub_dispatcher = None
        self._latest_activity = None

    async def async_added_to_hass(self):
        signal_name = f"lawn_manager_update_{self._entry_id}"
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, signal_name, self._handle_update_signal
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()

    async def _handle_update_signal(self):
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        data = await self._store.async_load() or {}
        try:
            if data.get("last_mow"):
                self._last_mow = dt_util.as_local(
                    datetime.strptime(data.get("last_mow"), "%Y-%m-%d")
                )
            else:
                self._last_mow = None
        except Exception:
            self._last_mow = dt_util.now() - timedelta(days=self._mow_interval + 1)

        mowing_history = data.get("mowing_history", [])
        if mowing_history:
            self._latest_activity = mowing_history[-1]
        else:
            self._latest_activity = None

    @property
    def name(self):
        return f"{self._yard_zone} Last Lawn Activity"

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
        attrs = {
            "location": self._location,
            "last_mow": self._last_mow.strftime("%Y-%m-%d"),
            "next_mow_due": next_due.strftime("%Y-%m-%d"),
        }

        if self._latest_activity:
            attrs["last_activity_type"] = self._latest_activity.get("cut_type", "Regular Maintenance")
            if "height_of_cut_inches" in self._latest_activity:
                attrs["last_height_of_cut_inches"] = self._latest_activity["height_of_cut_inches"]
            if "timestamp" in self._latest_activity:
                attrs["last_activity_timestamp"] = self._latest_activity["timestamp"]

        return attrs

    @property
    def unique_id(self):
        return f"lawn_manager_{self._entry_id}_{self._yard_zone.lower().replace(' ', '_')}_last_mow"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._yard_zone,
            "manufacturer": "Lawn Manager",
        }


class LawnMowDueSensor(SensorEntity):
    def __init__(self, entry_id, yard_zone, location, mow_interval, store, weather_entity=None, grass_type="Bermuda"):
        self._entry_id = entry_id
        self._yard_zone = yard_zone
        self._location = location
        self._mow_interval = mow_interval
        self._last_mow = None
        self._store = store
        self._weather_entity = weather_entity
        self._weather_helper = None
        self._grass_type = grass_type
        self._seasonal_helper = None
        self._unsub_dispatcher = None

    async def async_added_to_hass(self):
        signal_name = f"lawn_manager_update_{self._entry_id}"
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, signal_name, self._handle_update_signal
        )
        if self._weather_entity:
            self._weather_helper = WeatherHelper(self.hass, self._weather_entity)

        if SEASONAL_AVAILABLE:
            self._seasonal_helper = SeasonalHelper(self.hass, self._grass_type, self._location, self._weather_entity)

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()

    async def _handle_update_signal(self):
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        data = await self._store.async_load() or {}
        try:
            if data.get("last_mow"):
                self._last_mow = dt_util.as_local(
                    datetime.strptime(data.get("last_mow"), "%Y-%m-%d")
                )
            else:
                self._last_mow = None
        except Exception:
            self._last_mow = None

        self._application_history = data.get("applications", {})

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
        base_attrs = {}

        if not self._last_mow:
            base_attrs = {
                "mow_interval_days": self._mow_interval,
                "last_mow": "Never",
                "days_until_due": "Unknown"
            }
        else:
            due_date = self._last_mow + timedelta(days=self._mow_interval)
            days_until_due = (due_date - dt_util.now()).days

            base_attrs = {
                "mow_interval_days": self._mow_interval,
                "last_mow": self._last_mow.strftime("%Y-%m-%d"),
                "days_until_due": days_until_due,
                "overdue": days_until_due < 0
            }

        if self._weather_helper:
            try:
                base_attrs.update({
                    "weather_suitable_for_mowing": self._weather_helper.is_suitable_for_mowing(),
                    "weather_recommendation": self._weather_helper.get_weather_recommendation()
                })
            except Exception as e:
                _LOGGER.warning("Error getting weather information: %s", e)
                base_attrs["weather_recommendation"] = "Weather data unavailable"

        if self._seasonal_helper:
            try:
                seasonal_info = self._seasonal_helper.get_seasonal_summary(getattr(self, '_application_history', {}))
                seasonal_mow = seasonal_info["mow_frequency"]

                base_attrs.update({
                    "seasonal_recommended_frequency": seasonal_mow["frequency_days"],
                    "seasonal_frequency_reason": seasonal_mow["reason"]
                })
            except Exception as e:
                _LOGGER.warning("Error getting seasonal mowing information: %s", e)

        return base_attrs

    @property
    def unique_id(self):
        return f"lawn_manager_{self._entry_id}_{self._yard_zone.lower().replace(' ', '_')}_mow_due"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._yard_zone,
            "manufacturer": "Lawn Manager",
        }


class ChemicalApplicationSensor(SensorEntity):
    def __init__(self, entry_id, yard_zone, chemical_name, chem_data, weather_entity=None):
        self._entry_id = entry_id
        self._yard_zone = yard_zone
        self._chemical_name = chemical_name
        self._last_applied = chem_data.get("last_applied")
        self._interval_days = chem_data.get("interval_days", 30)
        self._default_amount_lb = chem_data.get("default_amount_lb_per_1000sqft", chem_data.get("amount_lb_per_1000sqft", 1.0))
        self._default_amount_oz = chem_data.get("default_amount_oz_per_1000sqft", chem_data.get("amount_oz_per_1000sqft", 16.0))
        self._applied_amount_lb = chem_data.get("applied_amount_lb_per_1000sqft", self._default_amount_lb)
        self._applied_amount_oz = chem_data.get("applied_amount_oz_per_1000sqft", self._default_amount_oz)
        self._rate_multiplier = chem_data.get("rate_multiplier", 1.0)
        self._rate_description = chem_data.get("rate_description", "Default")
        self._method = chem_data.get("method", "Unknown")
        self._state = None
        self._unsub_dispatcher = None
        self._weather_entity = weather_entity
        self._weather_helper = None

        if self._last_applied:
            try:
                last_dt = dt_util.as_local(datetime.strptime(self._last_applied, "%Y-%m-%d"))
                self._state = (dt_util.now() - last_dt).days
            except Exception:
                self._state = None

    async def async_added_to_hass(self):
        signal_name = f"lawn_manager_update_{self._entry_id}"
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, signal_name, self._handle_update_signal
        )
        if self._weather_entity:
            self._weather_helper = WeatherHelper(self.hass, self._weather_entity)

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()

    async def _handle_update_signal(self):
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        from homeassistant.helpers.storage import Store
        from .const import STORAGE_VERSION

        zone_storage_key = get_storage_key(self._entry_id)
        store = Store(self.hass, STORAGE_VERSION, zone_storage_key)
        data = await store.async_load() or {}

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
        if self._state is None:
            return f"{self._yard_zone} {self._chemical_name} Application"
        elif self._state == 0:
            return f"{self._yard_zone} {self._chemical_name} (Applied Today)"
        elif self._state == 1:
            return f"{self._yard_zone} {self._chemical_name} (Applied Yesterday)"
        else:
            return f"{self._yard_zone} {self._chemical_name} ({self._state} Days Ago)"

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
            last_dt = datetime.strptime(self._last_applied, "%Y-%m-%d")
            next_due = last_dt + timedelta(days=self._interval_days)
            base_attrs = {
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

            if self._weather_helper:
                try:
                    base_attrs.update({
                        "weather_suitable_for_application": self._weather_helper.is_suitable_for_chemicals(self._chemical_name),
                        "weather_recommendation": self._weather_helper.get_weather_recommendation(self._chemical_name)
                    })
                except Exception as e:
                    _LOGGER.warning("Error getting weather information for %s: %s", self._chemical_name, e)
                    base_attrs["weather_recommendation"] = "Weather data unavailable"

            return base_attrs
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
            "name": self._yard_zone,
            "manufacturer": "Lawn Manager",
        }


class LawnSeasonalSensor(SensorEntity):
    """Dedicated sensor for seasonal lawn care intelligence."""

    def __init__(self, entry_id, yard_zone, grass_type, location, weather_entity=None):
        self._entry_id = entry_id
        self._yard_zone = yard_zone
        self._grass_type = grass_type
        self._location = location
        self._weather_entity = weather_entity
        self._seasonal_helper = None
        self._application_history = {}
        self._unsub_dispatcher = None

    async def async_added_to_hass(self):
        if SEASONAL_AVAILABLE:
            self._seasonal_helper = SeasonalHelper(self.hass, self._grass_type, self._location, self._weather_entity)

        signal_name = f"lawn_manager_update_{self._entry_id}"
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, signal_name, self._handle_update_signal
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()

    async def _handle_update_signal(self):
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        from homeassistant.helpers.storage import Store
        from .const import STORAGE_VERSION

        zone_storage_key = get_storage_key(self._entry_id)
        store = Store(self.hass, STORAGE_VERSION, zone_storage_key)
        data = await store.async_load() or {}
        self._application_history = data.get("applications", {})

    @property
    def name(self):
        return f"{self._yard_zone} Seasonal Intelligence"

    @property
    def state(self):
        if not self._seasonal_helper:
            return "unavailable"

        try:
            seasonal_info = self._seasonal_helper.get_seasonal_summary(self._application_history)
            season = seasonal_info["season"]
            growing = seasonal_info["growing_season"]

            if growing:
                return f"{season.title()} - Growing Season"
            else:
                return f"{season.title()} - Dormant Season"
        except Exception:
            return "unknown"

    @property
    def icon(self):
        if not self._seasonal_helper:
            return "mdi:calendar-question"

        try:
            seasonal_info = self._seasonal_helper.get_seasonal_summary(self._application_history)
            season = seasonal_info["season"]
            icons = {"spring": "mdi:flower-tulip", "summer": "mdi:white-balance-sunny",
                     "fall": "mdi:leaf-maple", "winter": "mdi:snowflake"}
            return icons.get(season, "mdi:calendar-clock")
        except Exception:
            return "mdi:calendar-question"

    @property
    def extra_state_attributes(self):
        if not self._seasonal_helper:
            return {
                "grass_type": self._grass_type,
                "location": self._location,
                "status": "Seasonal intelligence unavailable"
            }

        try:
            seasonal_info = self._seasonal_helper.get_seasonal_summary(self._application_history)

            attrs = {
                "grass_type": self._grass_type,
                "location": self._location,
                "current_season": seasonal_info["season"],
                "growing_season": seasonal_info["growing_season"],
                "dormant_season": seasonal_info["dormant_season"],
                "recommended_mow_frequency_days": seasonal_info["mow_frequency"]["frequency_days"],
                "mow_frequency_reason": seasonal_info["mow_frequency"]["reason"],
                "temperature_warnings": seasonal_info["temperature_warnings"],
                "high_priority_chemicals": [chem_name for chem_name, chem_info in seasonal_info["chemical_recommendations"].items() if chem_info["priority"].upper() == "HIGH"],
                "medium_priority_chemicals": [chem_name for chem_name, chem_info in seasonal_info["chemical_recommendations"].items() if chem_info["priority"].upper() == "MEDIUM"],
                "low_priority_chemicals": [chem_name for chem_name, chem_info in seasonal_info["chemical_recommendations"].items() if chem_info["priority"].upper() == "LOW"],
                "high_priority_tasks": [task["task"] for task in seasonal_info["task_reminders"] if task["priority"].upper() == "HIGH"],
                "medium_priority_tasks": [task["task"] for task in seasonal_info["task_reminders"] if task["priority"].upper() == "MEDIUM"],
                "low_priority_tasks": [task["task"] for task in seasonal_info["task_reminders"] if task["priority"].upper() == "LOW"],
                "chemical_details": [
                    {"task": chem_name, "priority": chem_info["priority"], "reason": chem_info["reason"]}
                    for chem_name, chem_info in seasonal_info["chemical_recommendations"].items()
                ],
                "task_details": [
                    {"task": task["task"], "priority": task["priority"],
                     "reason": task.get("reason", task.get("deadline", ""))}
                    for task in seasonal_info["task_reminders"]
                ],
            }

            # Add detailed lawn care recommendations
            if "pre_emergent" in seasonal_info:
                pre_em = seasonal_info["pre_emergent"]
                attrs["pre_emergent_needed"] = pre_em.get("needed", False)
                attrs["pre_emergent_urgency"] = pre_em.get("urgency", "none")
                attrs["pre_emergent_reason"] = pre_em.get("reason", "")
                attrs["pre_emergent_timing"] = pre_em.get("timing", "")
                if pre_em.get("product_suggestion"):
                    attrs["pre_emergent_product"] = pre_em["product_suggestion"]

            if "scalping" in seasonal_info:
                scalp = seasonal_info["scalping"]
                attrs["scalping_recommended"] = scalp.get("recommended", False)
                attrs["scalping_reason"] = scalp.get("reason", "")
                if scalp.get("how_to"):
                    attrs["scalping_instructions"] = scalp["how_to"]

            if "dethatching" in seasonal_info:
                dethatch = seasonal_info["dethatching"]
                attrs["dethatching_recommended"] = dethatch.get("recommended", False)
                attrs["dethatching_reason"] = dethatch.get("reason", "")
                if dethatch.get("how_to"):
                    attrs["dethatching_instructions"] = dethatch["how_to"]
                if dethatch.get("alternatives"):
                    attrs["dethatching_alternatives"] = dethatch["alternatives"]

            if "aeration" in seasonal_info:
                aerate = seasonal_info["aeration"]
                attrs["aeration_recommended"] = aerate.get("recommended", False)
                attrs["aeration_reason"] = aerate.get("reason", "")
                if aerate.get("how_to"):
                    attrs["aeration_instructions"] = aerate["how_to"]

            if seasonal_info.get("estimated_soil_temp") is not None:
                attrs["estimated_soil_temp_f"] = round(seasonal_info["estimated_soil_temp"], 1)

            return attrs
        except Exception as e:
            _LOGGER.warning("Error getting seasonal information: %s", e)
            return {
                "grass_type": self._grass_type,
                "location": self._location,
                "status": "Error loading seasonal data"
            }

    @property
    def unique_id(self):
        return f"lawn_manager_{self._entry_id}_{self._yard_zone.lower().replace(' ', '_')}_seasonal"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._yard_zone,
            "manufacturer": "Lawn Manager",
        }


class LawnWeatherSensor(SensorEntity):
    def __init__(self, entry_id, yard_zone, weather_entity, grass_type="Bermuda", location="Unknown"):
        self._entry_id = entry_id
        self._yard_zone = yard_zone
        self._weather_entity = weather_entity
        self._grass_type = grass_type
        self._location = location
        self._weather_helper = None
        self._current_condition = None

    async def async_added_to_hass(self):
        if self._weather_entity:
            self._weather_helper = WeatherHelper(self.hass, self._weather_entity)

    async def async_update(self):
        if self._weather_helper:
            state = self.hass.states.get(self._weather_entity)
            if state:
                self._current_condition = state.state
            else:
                self._current_condition = "unavailable"

    @property
    def name(self):
        return f"{self._yard_zone} Weather Conditions"

    @property
    def state(self):
        return self._current_condition or "unknown"

    @property
    def icon(self):
        condition = (self._current_condition or "").lower()
        if condition in ['sunny', 'clear']:
            return "mdi:weather-sunny"
        elif condition in ['rainy', 'pouring']:
            return "mdi:weather-rainy"
        elif condition in ['cloudy', 'overcast']:
            return "mdi:weather-cloudy"
        elif condition in ['windy']:
            return "mdi:weather-windy"
        elif condition in ['snowy']:
            return "mdi:weather-snowy"
        else:
            return "mdi:weather-partly-cloudy"

    @property
    def extra_state_attributes(self):
        if not self._weather_helper:
            return {"weather_recommendation": "No weather data available"}

        try:
            attrs = {
                "weather_entity": self._weather_entity,
                "mowing_suitable": self._weather_helper.is_suitable_for_mowing(),
                "mowing_recommendation": self._weather_helper.get_weather_recommendation(),
                "fertilizer_suitable": self._weather_helper.is_suitable_for_chemicals("fertilizer"),
                "fertilizer_recommendation": self._weather_helper.get_weather_recommendation("fertilizer"),
                "herbicide_suitable": self._weather_helper.is_suitable_for_chemicals("weed preventer"),
                "herbicide_recommendation": self._weather_helper.get_weather_recommendation("weed preventer"),
                "general_chemical_suitable": self._weather_helper.is_suitable_for_chemicals(""),
                "general_chemical_recommendation": self._weather_helper.get_weather_recommendation("")
            }
            return attrs
        except Exception as e:
            _LOGGER.warning("Error getting weather information: %s", e)
            return {"weather_recommendation": "Weather data unavailable"}

    @property
    def unique_id(self):
        return f"lawn_manager_{self._entry_id}_{self._yard_zone.lower().replace(' ', '_')}_weather"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._yard_zone,
            "manufacturer": "Lawn Manager",
        }


class EquipmentInventorySensor(SensorEntity):
    def __init__(self, entry_id, yard_zone, location):
        self._entry_id = entry_id
        self._yard_zone = yard_zone
        self._location = location
        self._equipment_list = []
        self._unsub_dispatcher = None

    async def async_added_to_hass(self):
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, "lawn_manager_equipment_update", self._handle_equipment_update_signal
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()

    async def _handle_equipment_update_signal(self):
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        equipment_store = Store(self.hass, 1, "lawn_manager_equipment")
        equipment_data = await equipment_store.async_load() or {}

        self._equipment_list = []
        for eq_id, eq_info in equipment_data.items():
            self._equipment_list.append({
                "id": eq_id,
                "name": eq_info.get("friendly_name", "Unknown Equipment"),
                "type": eq_info.get("type", "unknown"),
                "brand": eq_info.get("brand", "Unknown"),
                "capacity": f"{eq_info.get('capacity', 0)} {eq_info.get('capacity_unit', 'units')}"
            })

    @property
    def name(self):
        return f"{self._yard_zone} Equipment Inventory"

    @property
    def state(self):
        if not self._equipment_list:
            return "No equipment added"
        names = [item["name"] for item in self._equipment_list]
        return ", ".join(names)

    @property
    def icon(self):
        return "mdi:tools"

    @property
    def extra_state_attributes(self):
        if not self._equipment_list:
            return {"equipment_count": 0, "status": "No equipment. Add via service or config flow."}

        attrs = {
            "equipment_count": len(self._equipment_list),
        }
        for i, item in enumerate(self._equipment_list):
            prefix = f"equipment_{i+1}"
            attrs[f"{prefix}_name"] = item["name"]
            attrs[f"{prefix}_type"] = item["type"]
            attrs[f"{prefix}_brand"] = item["brand"]
            attrs[f"{prefix}_capacity"] = item["capacity"]
            attrs[f"{prefix}_id"] = item["id"]

        attrs["equipment_list"] = self._equipment_list
        return attrs

    @property
    def unique_id(self):
        return f"lawn_manager_{self._entry_id}_{self._yard_zone.lower().replace(' ', '_')}_equipment"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._yard_zone,
            "manufacturer": "Lawn Manager",
        }


class RateCalculationSensor(SensorEntity):
    """Sensor to display the last application rate calculation result."""

    def __init__(self, entry_id, yard_zone):
        self._entry_id = entry_id
        self._yard_zone = yard_zone
        self._calculation_result = None
        self._unsub_dispatcher = None

    async def async_added_to_hass(self):
        from homeassistant.helpers.dispatcher import async_dispatcher_connect
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            f"lawn_manager_rate_calculated_{self._entry_id}",
            self._handle_rate_calculated
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()

    async def _handle_rate_calculated(self, result):
        self._calculation_result = result
        self.async_write_ha_state()

    @property
    def name(self):
        return f"{self._yard_zone} Application Rate Calculator"

    @property
    def state(self):
        if not self._calculation_result:
            return "No calculation yet"
        chemical = self._calculation_result.get("chemical", "Unknown")
        rate = self._calculation_result.get("application_rate", "")
        return f"{chemical}: {rate}" if rate else chemical

    @property
    def icon(self):
        return "mdi:calculator-variant"

    @property
    def extra_state_attributes(self):
        if not self._calculation_result:
            return {"status": "Press 'Calculate Application Rate' button to see results"}
        return self._calculation_result

    @property
    def unique_id(self):
        return f"lawn_manager_{self._entry_id}_{self._yard_zone.lower().replace(' ', '_')}_rate_calc"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._yard_zone,
            "manufacturer": "Lawn Manager",
            "model": "Chemical Application",
        }


class ActivityHistorySensor(SensorEntity):
    """Unified activity history sensor showing all activities for a zone."""

    def __init__(self, entry_id, yard_zone):
        self._entry_id = entry_id
        self._yard_zone = yard_zone
        self._activities = []
        self._unsub_dispatcher = None
        self._total_mowing = 0
        self._total_chemical = 0

    async def async_added_to_hass(self):
        signal_name = f"lawn_manager_update_{self._entry_id}"
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, signal_name, self._handle_update_signal
        )
        await self.async_update()

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()

    async def _handle_update_signal(self):
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        zone_storage_key = get_storage_key(self._entry_id)
        store = Store(self.hass, STORAGE_VERSION, zone_storage_key)
        data = await store.async_load() or {}

        activities = []

        for mow in data.get("mowing_history", []):
            activity = {
                "type": "mowing",
                "activity": mow.get("cut_type", "Mow"),
                "date": mow.get("date", ""),
                "timestamp": mow.get("timestamp", mow.get("date", "")),
            }
            if "height_of_cut_inches" in mow:
                activity["detail"] = f"HOC: {mow['height_of_cut_inches']} in"
            activities.append(activity)

        applications = data.get("applications", {})
        if isinstance(applications, dict):
            for chem_name, chem_data in applications.items():
                if isinstance(chem_data, dict) and chem_data.get("last_applied"):
                    activities.append({
                        "type": "chemical",
                        "activity": chem_name,
                        "date": chem_data.get("last_applied", ""),
                        "timestamp": chem_data.get("last_applied", ""),
                        "detail": f"{chem_data.get('rate_description', 'Default')} via {chem_data.get('method', '?')}",
                    })

        # Also check application_history list if present
        for app in data.get("application_history", []):
            activities.append({
                "type": "chemical",
                "activity": app.get("chemical", "Unknown"),
                "date": app.get("date", ""),
                "timestamp": app.get("timestamp", app.get("date", "")),
                "detail": app.get("detail", ""),
            })

        activities.sort(key=lambda x: x.get("timestamp", x.get("date", "")), reverse=True)

        self._total_mowing = len([a for a in activities if a["type"] == "mowing"])
        self._total_chemical = len([a for a in activities if a["type"] == "chemical"])
        self._activities = activities[:30]

    @property
    def name(self):
        return f"{self._yard_zone} Activity History"

    @property
    def state(self):
        total = self._total_mowing + self._total_chemical
        if total == 0:
            return "No activities"
        return f"{total} activities"

    @property
    def icon(self):
        return "mdi:history"

    @property
    def extra_state_attributes(self):
        if not self._activities:
            return {"status": "No activities recorded yet. Log a mowing or chemical application to start tracking."}

        attrs = {
            "total_activities": self._total_mowing + self._total_chemical,
            "total_mowing_activities": self._total_mowing,
            "total_chemical_applications": self._total_chemical,
            "recent_activities": self._activities[:10],
        }

        mowing = [a for a in self._activities if a["type"] == "mowing"]
        chemicals = [a for a in self._activities if a["type"] == "chemical"]

        if mowing:
            attrs["last_mowing"] = mowing[0]
        if chemicals:
            attrs["last_chemical"] = chemicals[0]

        return attrs

    @property
    def unique_id(self):
        return f"lawn_manager_{self._entry_id}_{self._yard_zone.lower().replace(' ', '_')}_history"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._yard_zone,
            "manufacturer": "Lawn Manager",
        }
