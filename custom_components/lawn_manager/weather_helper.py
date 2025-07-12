import logging
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class WeatherHelper:
    def __init__(self, hass: HomeAssistant, weather_entity_id: str):
        self.hass = hass
        self.weather_entity_id = weather_entity_id

    def is_suitable_for_mowing(self) -> bool:
        """Check if current weather is suitable for mowing."""
        if not self.weather_entity_id:
            return True  # No weather entity configured, assume suitable
        
        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return True  # Weather entity not found, assume suitable
        
        condition = state.state.lower()
        
        # Check for current rain or wet conditions
        if condition in ['rainy', 'pouring', 'snowy', 'snowy-rainy']:
            return False
        
        # Check recent weather history for drying time
        recent_rain_hours = self._get_hours_since_last_rain()
        if recent_rain_hours is not None and recent_rain_hours < 6:
            return False  # Need at least 6 hours to dry after rain
        
        # Check if rain is expected in the next few hours
        upcoming_rain_hours = self._get_hours_until_next_rain()
        if upcoming_rain_hours is not None and upcoming_rain_hours < 2:
            return False  # Don't start mowing if rain expected within 2 hours
        
        return True

    def is_suitable_for_chemicals(self, chemical_name: str = "") -> bool:
        """Check if current weather is suitable for chemical applications."""
        if not self.weather_entity_id:
            return True  # No weather entity configured, assume suitable
        
        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return True  # Weather entity not found, assume suitable
        
        condition = state.state.lower()
        chemical_lower = chemical_name.lower()
        
        # Fertilizers that need watering in are OK with rain
        if any(fert in chemical_lower for fert in ['fertilizer', 'iron', 'urea']):
            # Only avoid heavy rain/storms for fertilizers
            if condition in ['pouring', 'thunderstorm']:
                return False
            return True
        
        # Other chemicals (herbicides, pesticides, etc.) avoid rain and wind
        if condition in ['rainy', 'pouring', 'windy', 'snowy', 'snowy-rainy', 'thunderstorm']:
            return False
        
        return True

    def get_weather_recommendation(self, chemical_name: str = "") -> str:
        """Get weather-based recommendation."""
        if not self.weather_entity_id:
            return "No weather data available"
        
        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return "Weather entity not found"
        
        condition = state.state.lower()
        chemical_lower = chemical_name.lower()
        
        # Chemical-specific recommendations
        if chemical_name:
            # Fertilizers that benefit from watering
            if any(fert in chemical_lower for fert in ['fertilizer', 'iron', 'urea']):
                if condition in ['rainy']:
                    return "Good - rain will help water in the fertilizer"
                elif condition in ['pouring', 'thunderstorm']:
                    return "Wait for heavy rain to stop"
                elif condition in ['sunny', 'clear']:
                    return "Good conditions - water in after application"
                else:
                    return f"Current conditions: {condition}"
            
            # Other chemicals that need dry conditions
            else:
                if condition in ['rainy', 'pouring']:
                    return "Wait for rain to stop"
                elif condition in ['windy']:
                    return "Avoid application due to wind"
                elif condition in ['sunny', 'clear']:
                    return "Good conditions for application"
                else:
                    return f"Current conditions: {condition}"
        
        # General recommendation (for mowing)
        if condition in ['rainy', 'pouring']:
            return "Wait for rain to stop"
        elif condition in ['windy']:
            return "Avoid chemical applications due to wind"
        elif condition in ['sunny', 'clear']:
            # Check if grass has had time to dry
            recent_rain_hours = self._get_hours_since_last_rain()
            if recent_rain_hours is not None and recent_rain_hours < 6:
                return f"Wait for grass to dry (rain {recent_rain_hours:.1f} hours ago)"
            
            # Check if rain is coming soon
            upcoming_rain_hours = self._get_hours_until_next_rain()
            if upcoming_rain_hours is not None and upcoming_rain_hours < 2:
                return f"Rain expected in {upcoming_rain_hours:.1f} hours - wait or finish quickly"
            elif upcoming_rain_hours is not None and upcoming_rain_hours < 6:
                return f"Good conditions now, but rain expected in {upcoming_rain_hours:.1f} hours"
            
            return "Good conditions for lawn care"
        else:
            # Check drying time for other conditions too
            recent_rain_hours = self._get_hours_since_last_rain()
            if recent_rain_hours is not None and recent_rain_hours < 6:
                return f"Wait for grass to dry (rain {recent_rain_hours:.1f} hours ago)"
            
            # Check if rain is coming soon
            upcoming_rain_hours = self._get_hours_until_next_rain()
            if upcoming_rain_hours is not None and upcoming_rain_hours < 2:
                return f"Rain expected in {upcoming_rain_hours:.1f} hours - wait or finish quickly"
            elif upcoming_rain_hours is not None and upcoming_rain_hours < 6:
                return f"Current conditions: {condition}, but rain expected in {upcoming_rain_hours:.1f} hours"
            
            return f"Current conditions: {condition}" 

    def _get_hours_since_last_rain(self):
        """Get hours since last significant rain by checking weather history."""
        if not self.weather_entity_id:
            return None
        
        # Try to get weather entity's forecast or history
        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return None
        
        # Check if we have forecast data with recent conditions
        forecast = state.attributes.get('forecast', [])
        if forecast:
            # Look for recent rain in forecast history (some weather integrations include past data)
            for item in forecast[:6]:  # Check last 6 forecast periods
                condition = item.get('condition', '').lower()
                if condition in ['rainy', 'pouring', 'thunderstorm']:
                    # Found recent rain, assume it was recent
                    return 2.0  # Assume 2 hours ago if we found rain in recent forecast
        
        # Fallback: check attributes for precipitation or humidity indicators
        attrs = state.attributes
        
        # High humidity might indicate recent rain
        humidity = attrs.get('humidity')
        if humidity and humidity > 90:
            return 2.0  # Assume recent rain if very high humidity
        
        # Check for precipitation amount (some weather entities provide this)
        precipitation = attrs.get('precipitation', attrs.get('precipitation_amount', 0))
        if precipitation and precipitation > 0:
            return 2.0  # Assume recent rain if precipitation detected
        
        # If no indicators of recent rain, assume it's been dry long enough
        return 12.0  # Assume 12+ hours since last rain

    def _get_hours_until_next_rain(self):
        """Get hours until next expected rain from forecast."""
        if not self.weather_entity_id:
            return None
        
        state = self.hass.states.get(self.weather_entity_id)
        if not state:
            return None
        
        # Check forecast for upcoming rain
        forecast = state.attributes.get('forecast', [])
        if not forecast:
            return None
        
        # Look through next few forecast periods for rain
        for i, item in enumerate(forecast[:8]):  # Check next 8 forecast periods
            condition = item.get('condition', '').lower()
            if condition in ['rainy', 'pouring', 'thunderstorm']:
                # Estimate hours based on forecast period (assuming hourly or 3-hourly forecasts)
                # Most weather forecasts are either hourly or 3-hourly
                datetime_str = item.get('datetime', '')
                if datetime_str:
                    # Try to parse the datetime to get exact timing
                    try:
                        from datetime import datetime
                        import dateutil.parser
                        forecast_time = dateutil.parser.parse(datetime_str)
                        current_time = datetime.now(forecast_time.tzinfo)
                        hours_until = (forecast_time - current_time).total_seconds() / 3600
                        return max(0, hours_until)
                    except:
                        pass
                
                # Fallback: estimate based on position in forecast
                # Assume each forecast period is 3 hours apart
                return i * 3
        
        # No rain found in forecast
        return 24.0  # Assume no rain for at least 24 hours 
