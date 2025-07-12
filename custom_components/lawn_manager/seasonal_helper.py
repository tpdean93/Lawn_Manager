import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import GRASS_TYPES

_LOGGER = logging.getLogger(__name__)


class SeasonalHelper:
    def __init__(self, hass: HomeAssistant, grass_type: str, location: str, weather_entity: Optional[str] = None):
        self.hass = hass
        self.grass_type = grass_type
        self.location = location
        self.weather_entity = weather_entity
        self.grass_info = GRASS_TYPES.get(grass_type, GRASS_TYPES["Bermuda"])
        self.season_type = self.grass_info["season"]  # "warm" or "cool"

    def get_current_season(self) -> str:
        """Get current season based on calendar."""
        now = dt_util.now()
        month = now.month
        
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:  # 9, 10, 11
            return "fall"

    def is_grass_growing_season(self) -> bool:
        """Check if grass is in active growing season."""
        current_month = dt_util.now().month
        peak_months = self.grass_info["peak_months"]
        return current_month in peak_months

    def is_grass_dormant_season(self) -> bool:
        """Check if grass is in dormant season."""
        current_month = dt_util.now().month
        dormant_months = self.grass_info["dormant_months"]
        return current_month in dormant_months

    def get_seasonal_mow_frequency(self) -> Dict:
        """Get recommended mowing frequency based on season and grass type."""
        if self.is_grass_dormant_season():
            return {
                "frequency_days": 21,  # Less frequent during dormancy
                "reason": "Dormant season - reduced growth",
                "active": False
            }
        elif self.is_grass_growing_season():
            return {
                "frequency_days": 5,  # More frequent during peak growth
                "reason": "Peak growing season - active growth",
                "active": True
            }
        else:
            return {
                "frequency_days": 7,  # Normal frequency
                "reason": "Moderate growing season",
                "active": True
            }

    def get_temperature_warnings(self) -> List[str]:
        """Get temperature-based warnings for lawn activities."""
        warnings = []
        
        if not self.weather_entity:
            return warnings
        
        state = self.hass.states.get(self.weather_entity)
        if not state:
            return warnings
        
        # Get current temperature
        temperature = state.attributes.get('temperature')
        if temperature is None:
            return warnings
        
        # Convert to Fahrenheit if needed
        unit = state.attributes.get('temperature_unit', '°F')
        if unit == '°C':
            temperature = (temperature * 9/5) + 32
        
        # Temperature-based warnings
        if temperature > 90:
            warnings.append("Very hot - avoid mowing during peak heat (10am-4pm)")
            warnings.append("High heat stress - avoid fertilizer applications")
        elif temperature > 85:
            warnings.append("Hot conditions - mow early morning or evening")
        
        if temperature < 32:
            warnings.append("Freezing temperatures - avoid all lawn activities")
        elif temperature < 45:
            warnings.append("Cold conditions - grass growth minimal")
        
        return warnings

    def get_seasonal_chemical_recommendations(self) -> Dict[str, Dict]:
        """Get seasonal chemical application recommendations."""
        season = self.get_current_season()
        month = dt_util.now().month
        
        recommendations = {}
        
        if self.season_type == "warm":
            # Warm season grass recommendations
            if season == "spring":
                if month == 3:
                    recommendations["Pre-emergent"] = {
                        "priority": "high",
                        "reason": "Apply before soil temperature reaches 55°F",
                        "timing": "early spring"
                    }
                if month in [4, 5]:
                    recommendations["Fertilizer"] = {
                        "priority": "high", 
                        "reason": "Spring feeding as grass begins active growth",
                        "timing": "mid to late spring"
                    }
            elif season == "summer":
                recommendations["Iron Supplement"] = {
                    "priority": "medium",
                    "reason": "Maintain color during heat stress",
                    "timing": "summer"
                }
                recommendations["Grub Killer"] = {
                    "priority": "high",
                    "reason": "Peak grub activity period",
                    "timing": "early summer"
                }
            elif season == "fall":
                recommendations["Fertilizer"] = {
                    "priority": "high",
                    "reason": "Fall feeding for root development",
                    "timing": "early fall"
                }
        else:
            # Cool season grass recommendations
            if season == "spring":
                recommendations["Fertilizer"] = {
                    "priority": "high",
                    "reason": "Spring feeding during active growth",
                    "timing": "spring"
                }
                if month == 3:
                    recommendations["Pre-emergent"] = {
                        "priority": "high",
                        "reason": "Prevent crabgrass germination",
                        "timing": "early spring"
                    }
            elif season == "fall":
                recommendations["Fertilizer"] = {
                    "priority": "high",
                    "reason": "Most important feeding for cool season grasses",
                    "timing": "fall"
                }
                recommendations["Overseeding"] = {
                    "priority": "medium",
                    "reason": "Optimal overseeding conditions",
                    "timing": "early fall"
                }
        
        return recommendations

    def get_seasonal_task_reminders(self, application_history: Optional[Dict] = None) -> List[Dict]:
        """Get seasonal task reminders based on current season and application history."""
        season = self.get_current_season()
        month = dt_util.now().month
        
        tasks = []
        
        # Get application history for smart recommendations
        if application_history is None:
            application_history = {}
        
        if season == "spring":
            if month == 3:
                tasks.append({
                    "task": "Apply pre-emergent herbicide",
                    "priority": "high",
                    "deadline": "Before soil temperature reaches 55°F"
                })
                tasks.append({
                    "task": "Service mower and equipment",
                    "priority": "medium",
                    "deadline": "Before growing season starts"
                })
            if month in [4, 5]:
                tasks.append({
                    "task": "Begin regular fertilizer program",
                    "priority": "high",
                    "deadline": "During active growth period"
                })
        
        elif season == "summer":
            tasks.append({
                "task": "Monitor for heat stress",
                "priority": "medium",
                "deadline": "During hot weather"
            })
            
            # Smart grub control recommendation
            grub_applied_recently = self._check_recent_application(application_history, "Grub Killer", 120)  # 120 days
            if not grub_applied_recently:
                tasks.append({
                    "task": "Apply grub control",
                    "priority": "high",
                    "deadline": "Early summer for best results",
                    "reason": "No grub control found in last 120 days"
                })
            else:
                tasks.append({
                    "task": "Grub control applied recently",
                    "priority": "info",
                    "deadline": "Next application due in fall",
                    "reason": "Grub control already applied this season"
                })
        
        elif season == "fall":
            tasks.append({
                "task": "Fall fertilizer application",
                "priority": "high",
                "deadline": "6-8 weeks before first frost"
            })
            if self.season_type == "cool":
                tasks.append({
                    "task": "Overseed thin areas",
                    "priority": "medium",
                    "deadline": "Early fall for best establishment"
                })
        
        elif season == "winter":
            tasks.append({
                "task": "Plan next year's lawn care",
                "priority": "low",
                "deadline": "During dormant season"
            })
            tasks.append({
                "task": "Equipment maintenance",
                "priority": "medium",
                "deadline": "Before next growing season"
            })
        
        return tasks

    def _check_recent_application(self, application_history: Dict, chemical_name: str, days_threshold: int) -> bool:
        """Check if a chemical was applied within the threshold days."""
        if not application_history:
            return False
        
        # Look for exact match or partial match in chemical names
        for app_name, app_data in application_history.items():
            if chemical_name.lower() in app_name.lower() or app_name.lower() in chemical_name.lower():
                last_applied = app_data.get("last_applied")
                if last_applied:
                    try:
                        from datetime import datetime
                        last_date = datetime.strptime(last_applied, "%Y-%m-%d")
                        current_date = dt_util.now().replace(tzinfo=None)
                        days_since = (current_date - last_date).days
                        return days_since <= days_threshold
                    except:
                        continue
        
        return False

    def get_seasonal_summary(self, application_history: Optional[Dict] = None) -> Dict:
        """Get comprehensive seasonal summary."""
        return {
            "season": self.get_current_season(),
            "grass_type": self.grass_type,
            "season_type": self.season_type,
            "growing_season": self.is_grass_growing_season(),
            "dormant_season": self.is_grass_dormant_season(),
            "mow_frequency": self.get_seasonal_mow_frequency(),
            "temperature_warnings": self.get_temperature_warnings(),
            "chemical_recommendations": self.get_seasonal_chemical_recommendations(),
            "task_reminders": self.get_seasonal_task_reminders(application_history)
        } 
