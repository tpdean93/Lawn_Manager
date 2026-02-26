import logging
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class WeatherHelper:
    def __init__(self, hass: HomeAssistant, weather_entity_id: str):
        self.hass = hass
        self.weather_entity_id = weather_entity_id
        self._is_sensor = weather_entity_id.startswith("sensor.")
        self._sibling_sensors = {}
        self._siblings_loaded = False

    def _load_sibling_sensors(self):
        """Find sibling sensors from the same device (humidity, wind, pressure, etc.)."""
        if self._siblings_loaded:
            return
        self._siblings_loaded = True

        if not self._is_sensor:
            return

        try:
            from homeassistant.helpers import entity_registry as er
            ent_reg = er.async_get(self.hass)
        except Exception:
            return

        main_entry = ent_reg.async_get(self.weather_entity_id)
        if not main_entry or not main_entry.device_id:
            return

        device_id = main_entry.device_id
        indoor_keywords = ["indoor", "inside", "interior", "in_temp", "in_humid"]

        for entry in ent_reg.entities.values():
            if entry.device_id != device_id or entry.domain != "sensor":
                continue
            if entry.disabled:
                continue

            eid_lower = entry.entity_id.lower()
            name_lower = (entry.original_name or entry.name or "").lower()
            if any(kw in eid_lower or kw in name_lower for kw in indoor_keywords):
                continue

            dev_class = entry.original_device_class or entry.device_class or ""

            if dev_class == "humidity" and "humidity" not in self._sibling_sensors:
                self._sibling_sensors["humidity"] = entry.entity_id
            elif dev_class == "wind_speed" and "wind_speed" not in self._sibling_sensors:
                self._sibling_sensors["wind_speed"] = entry.entity_id
            elif dev_class in ("pressure", "atmospheric_pressure") and "pressure" not in self._sibling_sensors:
                self._sibling_sensors["pressure"] = entry.entity_id
            elif dev_class == "precipitation" and "precipitation" not in self._sibling_sensors:
                self._sibling_sensors["precipitation"] = entry.entity_id
            elif "dew" in eid_lower and "dewpoint" not in self._sibling_sensors:
                self._sibling_sensors["dewpoint"] = entry.entity_id

    def _get_sibling_value(self, sensor_type) -> float | None:
        """Get a numeric value from a sibling sensor."""
        self._load_sibling_sensors()
        entity_id = self._sibling_sensors.get(sensor_type)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if not state:
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _get_temperature(self) -> float | None:
        """Get current temperature in Fahrenheit."""
        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return None

        if self._is_sensor:
            try:
                temp = float(state.state)
                unit = state.attributes.get("unit_of_measurement", "°F")
                if "C" in str(unit) and "°" in str(unit):
                    temp = (temp * 9 / 5) + 32
                return temp
            except (ValueError, TypeError):
                return None

        # Standard weather entity
        temp = state.attributes.get("temperature")
        if temp is not None:
            unit = state.attributes.get("temperature_unit", "°F")
            if "°C" in str(unit):
                temp = (temp * 9 / 5) + 32
        return temp

    def _get_humidity(self) -> float | None:
        """Get current humidity."""
        if self._is_sensor:
            return self._get_sibling_value("humidity")

        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return None
        return state.attributes.get("humidity")

    def _get_wind_speed(self) -> float | None:
        """Get current wind speed in mph."""
        if self._is_sensor:
            wind = self._get_sibling_value("wind_speed")
            if wind is not None:
                # Check unit of sibling sensor
                entity_id = self._sibling_sensors.get("wind_speed")
                if entity_id:
                    st = self.hass.states.get(entity_id)
                    if st:
                        unit = st.attributes.get("unit_of_measurement", "mph")
                        if "km" in str(unit).lower():
                            wind = wind * 0.621371
                        elif "m/s" in str(unit).lower():
                            wind = wind * 2.23694
            return wind

        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return None

        wind = state.attributes.get("wind_speed")
        if wind is None:
            return None

        wind_unit = state.attributes.get("wind_speed_unit", "mph")
        if "km" in str(wind_unit).lower():
            wind = wind * 0.621371
        elif "m/s" in str(wind_unit).lower():
            wind = wind * 2.23694
        return wind

    def _get_condition(self) -> str:
        """Get the current weather condition string."""
        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return "unknown"

        if self._is_sensor:
            # Sensor entities don't have a "condition" - infer from data
            temp = self._get_temperature()
            humidity = self._get_humidity()
            precip = self._get_sibling_value("precipitation")

            if precip and precip > 0:
                return "rainy"
            if humidity and humidity > 90:
                return "humid"
            if temp and temp > 85:
                return "sunny"
            return "clear"

        return state.state.lower()

    def is_suitable_for_mowing(self) -> bool:
        if not self.weather_entity_id:
            return True

        condition = self._get_condition()
        if condition in ['rainy', 'pouring', 'snowy', 'snowy-rainy', 'thunderstorm']:
            return False

        wind = self._get_wind_speed()
        if wind and wind > 25:
            return False

        humidity = self._get_humidity()
        if humidity and humidity > 95:
            return False

        recent_rain_hours = self._get_hours_since_last_rain()
        if recent_rain_hours is not None and recent_rain_hours < 6:
            return False

        upcoming_rain_hours = self._get_hours_until_next_rain()
        if upcoming_rain_hours is not None and upcoming_rain_hours < 2:
            return False

        return True

    def is_suitable_for_chemicals(self, chemical_name: str = "") -> bool:
        if not self.weather_entity_id:
            return True

        condition = self._get_condition()
        chemical_lower = chemical_name.lower()

        wind = self._get_wind_speed()
        if wind and wind > 10:
            return False

        if any(fert in chemical_lower for fert in ['fertilizer', 'iron', 'urea']):
            if condition in ['pouring', 'thunderstorm']:
                return False
            return True

        if condition in ['rainy', 'pouring', 'windy', 'snowy', 'snowy-rainy', 'thunderstorm']:
            return False

        return True

    def get_weather_recommendation(self, chemical_name: str = "") -> str:
        if not self.weather_entity_id:
            return "No weather data available"

        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return "Weather entity not found"

        condition = self._get_condition()
        chemical_lower = chemical_name.lower()
        temp = self._get_temperature()
        wind = self._get_wind_speed()
        humidity = self._get_humidity()

        parts = []

        if wind and wind > 15:
            parts.append(f"Wind {wind:.0f} mph - avoid spraying")
        elif wind and wind > 10:
            parts.append(f"Wind {wind:.0f} mph - use caution when spraying")

        if temp:
            if temp > 90:
                parts.append(f"Hot ({temp:.0f}°F) - avoid fertilizer, apply chemicals early AM")
            elif temp < 40:
                parts.append(f"Cold ({temp:.0f}°F) - most chemicals ineffective below 50°F")

        if humidity and humidity > 85 and temp and temp > 75:
            parts.append("High humidity - increased fungal disease risk")

        if chemical_name:
            if any(fert in chemical_lower for fert in ['fertilizer', 'iron', 'urea']):
                if condition in ['rainy']:
                    parts.append("Rain will help water in the fertilizer")
                elif condition in ['pouring', 'thunderstorm']:
                    parts.append("Wait for heavy rain to stop")
                elif condition in ['sunny', 'clear']:
                    parts.append("Good conditions - water in after application")
            else:
                if condition in ['rainy', 'pouring']:
                    parts.append("Wait for rain to stop before applying")
                elif condition in ['sunny', 'clear']:
                    parts.append("Good conditions for application")
        else:
            if condition in ['rainy', 'pouring']:
                parts.append("Wait for rain to stop and grass to dry")
            elif condition in ['sunny', 'clear']:
                recent_rain = self._get_hours_since_last_rain()
                if recent_rain is not None and recent_rain < 6:
                    parts.append(f"Rain {recent_rain:.1f}h ago - wait for grass to dry")
                else:
                    parts.append("Good conditions for lawn care")

                upcoming_rain = self._get_hours_until_next_rain()
                if upcoming_rain is not None and upcoming_rain < 2:
                    parts.append(f"Rain expected in {upcoming_rain:.1f}h")
                elif upcoming_rain is not None and upcoming_rain < 6:
                    parts.append(f"Rain in {upcoming_rain:.1f}h - finish quickly")

        if not parts:
            if temp:
                return f"Current: {temp:.0f}°F, {condition}"
            return f"Current conditions: {condition}"

        return ". ".join(parts)

    def _get_hours_since_last_rain(self):
        if not self.weather_entity_id:
            return None

        # For sensor entities, check precipitation sibling
        if self._is_sensor:
            precip = self._get_sibling_value("precipitation")
            if precip is not None and precip > 0:
                return 0.5
            humidity = self._get_humidity()
            if humidity and humidity > 90:
                return 2.0
            return 12.0

        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return None

        forecast = state.attributes.get('forecast', [])
        if forecast:
            for item in forecast[:6]:
                condition = item.get('condition', '').lower()
                if condition in ['rainy', 'pouring', 'thunderstorm']:
                    return 2.0

        attrs = state.attributes
        humidity = attrs.get('humidity')
        if humidity and humidity > 90:
            return 2.0

        precipitation = attrs.get('precipitation', attrs.get('precipitation_amount', 0))
        if precipitation and precipitation > 0:
            return 2.0

        return 12.0

    def _get_hours_until_next_rain(self):
        if not self.weather_entity_id:
            return None

        # Sensor entities don't have forecasts
        if self._is_sensor:
            return None

        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return None

        forecast = state.attributes.get('forecast', [])
        if not forecast:
            return None

        for i, item in enumerate(forecast[:8]):
            condition = item.get('condition', '').lower()
            if condition in ['rainy', 'pouring', 'thunderstorm']:
                datetime_str = item.get('datetime', '')
                if datetime_str:
                    try:
                        from datetime import datetime
                        import dateutil.parser
                        forecast_time = dateutil.parser.parse(datetime_str)
                        current_time = datetime.now(forecast_time.tzinfo)
                        hours_until = (forecast_time - current_time).total_seconds() / 3600
                        return max(0, hours_until)
                    except Exception:
                        pass
                return i * 3

        return 24.0
