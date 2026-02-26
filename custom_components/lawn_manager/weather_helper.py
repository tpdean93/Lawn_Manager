import logging
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class WeatherHelper:
    def __init__(self, hass: HomeAssistant, weather_entity_id: str):
        self.hass = hass
        self.weather_entity_id = weather_entity_id
        self._is_awn = "awn" in weather_entity_id.lower() or "ambient" in weather_entity_id.lower()

    def _get_temperature(self) -> float | None:
        """Get current temperature in Fahrenheit, handling AWN and standard weather entities."""
        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return None

        if self._is_awn:
            # AWN entities may store temperature in the state itself or in attributes
            try:
                temp = float(state.state)
                unit = state.attributes.get("unit_of_measurement", "°F")
                if "°C" in str(unit) or "C" == str(unit):
                    temp = (temp * 9/5) + 32
                return temp
            except (ValueError, TypeError):
                pass
            temp = state.attributes.get("temperature")
            if temp is not None:
                unit = state.attributes.get("temperature_unit", "°F")
                if "°C" in str(unit):
                    temp = (temp * 9/5) + 32
                return temp
            return None

        # Standard weather entity
        temp = state.attributes.get("temperature")
        if temp is not None:
            unit = state.attributes.get("temperature_unit", "°F")
            if "°C" in str(unit):
                temp = (temp * 9/5) + 32
        return temp

    def _get_humidity(self) -> float | None:
        """Get current humidity."""
        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return None
        return state.attributes.get("humidity")

    def _get_wind_speed(self) -> float | None:
        """Get current wind speed in mph."""
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

        if self._is_awn:
            # AWN may store condition in different attributes
            condition = state.attributes.get("condition", state.state)
            return str(condition).lower()

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
        if wind and wind > 10 and "sprayer" not in chemical_lower:
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

        # Wind check
        if wind and wind > 15:
            parts.append(f"Wind {wind:.0f} mph - avoid spraying")
        elif wind and wind > 10:
            parts.append(f"Wind {wind:.0f} mph - use caution when spraying")

        # Temperature check
        if temp:
            if temp > 90:
                parts.append(f"Hot ({temp:.0f}°F) - avoid fertilizer, apply chemicals early AM")
            elif temp < 40:
                parts.append(f"Cold ({temp:.0f}°F) - most chemicals ineffective below 50°F")

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

            if 'pre-emergent' in chemical_lower or 'weed preventer' in chemical_lower:
                if condition in ['rainy']:
                    parts.append("Light rain OK - helps activate pre-emergent")
        else:
            # General recommendation (for mowing)
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
            return f"Current conditions: {condition}"

        return ". ".join(parts)

    def _get_hours_since_last_rain(self):
        if not self.weather_entity_id:
            return None

        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return None

        # Check AWN-specific precipitation data
        if self._is_awn:
            daily_rain = state.attributes.get("dailyrainin", state.attributes.get("daily_rain"))
            if daily_rain is not None:
                try:
                    if float(daily_rain) > 0:
                        return 2.0
                except (ValueError, TypeError):
                    pass

            hourly_rain = state.attributes.get("hourlyrainin", state.attributes.get("hourly_rain"))
            if hourly_rain is not None:
                try:
                    if float(hourly_rain) > 0:
                        return 0.5
                except (ValueError, TypeError):
                    pass

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
