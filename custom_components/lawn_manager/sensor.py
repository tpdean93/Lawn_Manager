from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, DEFAULT_MOW_INTERVAL
from .weather_helper import WeatherHelper

_LOGGER = logging.getLogger(__name__)

try:
    from .seasonal_helper import SeasonalHelper
    SEASONAL_AVAILABLE = True
except ImportError:
    SEASONAL_AVAILABLE = False
    _LOGGER.warning("Seasonal helper not available - seasonal features disabled")
STORAGE_KEY = "lawn_manager_data"
STORAGE_VERSION = 1

@@ -33,15 +41,29 @@ async def async_setup(self):
location = config.get("location", "Unknown")
mow_interval = config.get("mow_interval", DEFAULT_MOW_INTERVAL)

        # Get weather entity and grass type from config
        weather_entity = config.get("weather_entity")
        grass_type = config.get("grass_type", "Bermuda")
        
# Add core mow tracking sensors (always created)
self.mow_sensor = LawnMowSensor(self.entry.entry_id, yard_zone, location, mow_interval, store)
        self.mow_due_sensor = LawnMowDueSensor(self.entry.entry_id, yard_zone, location, mow_interval, store)
        self.mow_due_sensor = LawnMowDueSensor(self.entry.entry_id, yard_zone, location, mow_interval, store, weather_entity, grass_type)
entities = [self.mow_sensor, self.mow_due_sensor]
        
        # Add weather conditions sensor if weather entity is configured
        if weather_entity:
            self.weather_sensor = LawnWeatherSensor(self.entry.entry_id, yard_zone, weather_entity, grass_type, location)
            entities.append(self.weather_sensor)
        
        # Add seasonal intelligence sensor if seasonal helper is available
        if SEASONAL_AVAILABLE:
            self.seasonal_sensor = LawnSeasonalSensor(self.entry.entry_id, yard_zone, grass_type, location, weather_entity)
            entities.append(self.seasonal_sensor)

# Add chemical sensors
for chem_name, chem_data in data.get("applications", {}).items():
self.known_chemicals.add(chem_name)
            sensor = ChemicalApplicationSensor(self.entry.entry_id, chem_name, chem_data)
            sensor = ChemicalApplicationSensor(self.entry.entry_id, chem_name, chem_data, weather_entity)
self.chemical_sensors[chem_name] = sensor
entities.append(sensor)

@@ -61,7 +83,9 @@ async def _handle_update_signal(self):
# Add new chemical sensors
for chem_name in new_chems:
chem_data = data["applications"][chem_name]
            sensor = ChemicalApplicationSensor(self.entry.entry_id, chem_name, chem_data)
            config = self.entry.data
            weather_entity = config.get("weather_entity")
            sensor = ChemicalApplicationSensor(self.entry.entry_id, chem_name, chem_data, weather_entity)
self.chemical_sensors[chem_name] = sensor
new_entities.append(sensor)
self.known_chemicals.add(chem_name)
@@ -162,19 +186,32 @@ def entity_category(self):


class LawnMowDueSensor(SensorEntity):
    def __init__(self, entry_id, yard_zone, location, mow_interval, store):
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
self._unsub_dispatcher = async_dispatcher_connect(
self.hass, "lawn_manager_update", self._handle_update_signal
)
        # Initialize weather helper if weather entity is configured
        if self._weather_entity:
            self._weather_helper = WeatherHelper(self.hass, self._weather_entity)
        
        # Initialize seasonal helper
        if SEASONAL_AVAILABLE:
            self._seasonal_helper = SeasonalHelper(self.hass, self._grass_type, self._location, self._weather_entity)
        else:
            self._seasonal_helper = None

async def async_will_remove_from_hass(self):
if self._unsub_dispatcher:
@@ -188,11 +225,17 @@ async def _handle_update_signal(self):
async def async_update(self):
data = await self._store.async_load() or {}
try:
            self._last_mow = dt_util.as_local(
                datetime.strptime(data.get("last_mow"), "%Y-%m-%d")
            )
            if data.get("last_mow"):
                self._last_mow = dt_util.as_local(
                    datetime.strptime(data.get("last_mow"), "%Y-%m-%d")
                )
            else:
                self._last_mow = None
except Exception:
self._last_mow = None
        
        # Store application history for seasonal recommendations
        self._application_history = data.get("applications", {})

@property
def name(self):
@@ -211,22 +254,51 @@ def icon(self):

@property
def extra_state_attributes(self):
        base_attrs = {}
        
if not self._last_mow:
            return {
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

        due_date = self._last_mow + timedelta(days=self._mow_interval)
        days_until_due = (due_date - dt_util.now()).days
        # Add weather information if available
        if self._weather_helper:
            try:
                base_attrs.update({
                    "weather_suitable_for_mowing": self._weather_helper.is_suitable_for_mowing(),
                    "weather_recommendation": self._weather_helper.get_weather_recommendation()
                })
            except Exception as e:
                _LOGGER.warning("Error getting weather information: %s", e)
                base_attrs["weather_recommendation"] = "Weather data unavailable"

        return {
            "mow_interval_days": self._mow_interval,
            "last_mow": self._last_mow.strftime("%Y-%m-%d"),
            "days_until_due": days_until_due,
            "overdue": days_until_due < 0
        }
        # Note: Seasonal intelligence is now in its own dedicated sensor
        # But we still use seasonal helper for mowing frequency if available
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
@@ -242,7 +314,7 @@ def device_info(self):


class ChemicalApplicationSensor(SensorEntity):
    def __init__(self, entry_id, chemical_name, chem_data):
    def __init__(self, entry_id, chemical_name, chem_data, weather_entity=None):
self._entry_id = entry_id
self._chemical_name = chemical_name
self._last_applied = chem_data.get("last_applied")
@@ -257,6 +329,8 @@ def __init__(self, entry_id, chemical_name, chem_data):
self._method = chem_data.get("method", "Unknown")
self._state = None
self._unsub_dispatcher = None
        self._weather_entity = weather_entity
        self._weather_helper = None

# Calculate initial state
if self._last_applied:
@@ -270,6 +344,9 @@ async def async_added_to_hass(self):
self._unsub_dispatcher = async_dispatcher_connect(
self.hass, "lawn_manager_update", self._handle_update_signal
)
        # Initialize weather helper if weather entity is configured
        if self._weather_entity:
            self._weather_helper = WeatherHelper(self.hass, self._weather_entity)

async def async_will_remove_from_hass(self):
if self._unsub_dispatcher:
@@ -343,7 +420,7 @@ def extra_state_attributes(self):
if self._last_applied:
last_dt = datetime.strptime(self._last_applied, "%Y-%m-%d")
next_due = last_dt + timedelta(days=self._interval_days)
                return {
                base_attrs = {
"last_applied": self._last_applied,
"next_due": next_due.strftime("%Y-%m-%d"),
"interval_days": self._interval_days,
@@ -355,6 +432,19 @@ def extra_state_attributes(self):
"rate_description": self._rate_description,
"method": self._method
}
                
                # Add weather information if available
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
else:
return {}
except Exception as e:
@@ -376,3 +466,253 @@ def device_info(self):
"name": "Lawn Manager",
"manufacturer": "Custom Integration",
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
        # Initialize seasonal helper
        if SEASONAL_AVAILABLE:
            self._seasonal_helper = SeasonalHelper(self.hass, self._grass_type, self._location, self._weather_entity)
        else:
            self._seasonal_helper = None
        
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
        # Load application history for smart recommendations
        from homeassistant.helpers.storage import Store
        from .const import STORAGE_VERSION, STORAGE_KEY
        
        store = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
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
            
            if season == "spring":
                return "mdi:flower-tulip"
            elif season == "summer":
                return "mdi:white-balance-sunny"
            elif season == "fall":
                return "mdi:leaf-maple"
            elif season == "winter":
                return "mdi:snowflake"
            else:
                return "mdi:calendar-clock"
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
            
            # Organize attributes in a logical way
            attrs = {
                # Basic info
                "grass_type": self._grass_type,
                "location": self._location,
                "current_season": seasonal_info["season"],
                "growing_season": seasonal_info["growing_season"],
                "dormant_season": seasonal_info["dormant_season"],
                
                # Mowing recommendations
                "recommended_mow_frequency_days": seasonal_info["mow_frequency"]["frequency_days"],
                "mow_frequency_reason": seasonal_info["mow_frequency"]["reason"],
                
                # Temperature alerts
                "temperature_warnings": seasonal_info["temperature_warnings"],
                
                # Chemical recommendations (organized by priority)
                # Note: chemical_recommendations is a dict like {"Pre-emergent": {"priority": "high", "reason": "..."}}
                "high_priority_chemicals": [chem_name for chem_name, chem_info in seasonal_info["chemical_recommendations"].items() if chem_info["priority"].upper() == "HIGH"],
                "medium_priority_chemicals": [chem_name for chem_name, chem_info in seasonal_info["chemical_recommendations"].items() if chem_info["priority"].upper() == "MEDIUM"],
                "low_priority_chemicals": [chem_name for chem_name, chem_info in seasonal_info["chemical_recommendations"].items() if chem_info["priority"].upper() == "LOW"],
                
                # Task reminders (organized by priority)
                # Note: task_reminders is a list like [{"task": "...", "priority": "high", "reason": "..."}]
                "high_priority_tasks": [task["task"] for task in seasonal_info["task_reminders"] if task["priority"].upper() == "HIGH"],
                "medium_priority_tasks": [task["task"] for task in seasonal_info["task_reminders"] if task["priority"].upper() == "MEDIUM"],
                "low_priority_tasks": [task["task"] for task in seasonal_info["task_reminders"] if task["priority"].upper() == "LOW"],
                
                # Detailed recommendations with reasons
                "chemical_details": [
                    {
                        "task": chem_name,
                        "priority": chem_info["priority"],
                        "reason": chem_info["reason"]
                    } for chem_name, chem_info in seasonal_info["chemical_recommendations"].items()
                ],
                "task_details": [
                    {
                        "task": task["task"],
                        "priority": task["priority"],
                        "reason": task.get("reason", task.get("deadline", ""))
                    } for task in seasonal_info["task_reminders"]
                ]
            }
            
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
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }


class LawnWeatherSensor(SensorEntity):
    def __init__(self, entry_id, yard_zone, weather_entity, grass_type="Bermuda", location="Unknown"):
        self._entry_id = entry_id
        self._yard_zone = yard_zone
        self._weather_entity = weather_entity
        self._grass_type = grass_type
        self._location = location
        self._weather_helper = None
        self._seasonal_helper = None
        self._current_condition = None

    async def async_added_to_hass(self):
        # Initialize weather helper
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
            
            # Note: Seasonal intelligence is now in its own dedicated sensor
            
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
            "name": "Lawn Manager",
            "manufacturer": "Custom Integration",
        }
