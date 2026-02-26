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

        if grass_type.startswith("Custom:"):
            if "warm" in grass_type.lower():
                self.grass_info = {"season": "warm", "peak_months": [5, 6, 7, 8, 9], "dormant_months": [11, 12, 1, 2]}
            elif "cool" in grass_type.lower():
                self.grass_info = {"season": "cool", "peak_months": [3, 4, 5, 9, 10, 11], "dormant_months": [7, 8]}
            else:
                self.grass_info = {"season": "transition", "peak_months": [4, 5, 6, 9, 10], "dormant_months": [1, 2, 7, 8]}
        else:
            self.grass_info = GRASS_TYPES.get(grass_type, GRASS_TYPES["Bermuda"])

        self.season_type = self.grass_info["season"]

    def get_current_season(self) -> str:
        now = dt_util.now()
        month = now.month

        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "fall"

    def is_grass_growing_season(self) -> bool:
        current_month = dt_util.now().month
        return current_month in self.grass_info["peak_months"]

    def is_grass_dormant_season(self) -> bool:
        current_month = dt_util.now().month
        return current_month in self.grass_info["dormant_months"]

    def _get_soil_temperature_estimate(self) -> Optional[float]:
        """Estimate soil temperature from air temperature.
        
        Soil temp at 4 inches lags air temp by ~2-4 weeks and is typically
        5-10°F cooler than avg air temp in spring, 5-10°F warmer in fall.
        """
        if not self.weather_entity:
            return None

        state = self.hass.states.get(self.weather_entity)
        if not state:
            return None

        temperature = state.attributes.get('temperature')
        if temperature is None:
            return None

        unit = state.attributes.get('temperature_unit', '°F')
        if unit == '°C':
            temperature = (temperature * 9/5) + 32

        month = dt_util.now().month
        season = self.get_current_season()

        if season == "spring":
            soil_temp = temperature - 8
        elif season == "fall":
            soil_temp = temperature + 5
        elif season == "summer":
            soil_temp = temperature - 3
        else:
            soil_temp = temperature - 5

        return soil_temp

    def get_seasonal_mow_frequency(self) -> Dict:
        if self.is_grass_dormant_season():
            return {
                "frequency_days": 21,
                "reason": "Dormant season - reduced growth. Only mow if grass is actively growing.",
                "active": False
            }
        elif self.is_grass_growing_season():
            soil_temp = self._get_soil_temperature_estimate()
            if soil_temp and soil_temp > 80:
                return {
                    "frequency_days": 4,
                    "reason": "Peak growing season with warm soil - rapid growth expected",
                    "active": True
                }
            return {
                "frequency_days": 5,
                "reason": "Peak growing season - active growth, mow frequently using 1/3 rule",
                "active": True
            }
        else:
            return {
                "frequency_days": 7,
                "reason": "Moderate growing season - standard weekly mowing",
                "active": True
            }

    def get_temperature_warnings(self) -> List[str]:
        warnings = []

        if not self.weather_entity:
            return warnings

        state = self.hass.states.get(self.weather_entity)
        if not state:
            return warnings

        temperature = state.attributes.get('temperature')
        if temperature is None:
            return warnings

        unit = state.attributes.get('temperature_unit', '°F')
        if unit == '°C':
            temperature = (temperature * 9/5) + 32

        if temperature > 95:
            warnings.append("EXTREME HEAT - Avoid all lawn activities. Water deeply in early morning.")
            warnings.append("Do NOT apply fertilizer or chemicals in extreme heat - risk of burn.")
        elif temperature > 90:
            warnings.append("Very hot - avoid mowing during peak heat (10am-4pm)")
            warnings.append("High heat stress - avoid fertilizer, iron supplements OK early AM")
        elif temperature > 85:
            warnings.append("Hot conditions - mow early morning or evening, raise HOC by 0.5 inch")

        if temperature < 28:
            warnings.append("HARD FREEZE - Do not walk on frozen grass, causes crown damage")
        elif temperature < 32:
            warnings.append("Freezing temperatures - avoid all lawn activities")
        elif temperature < 40:
            warnings.append("Very cold - grass dormant, minimal to no growth expected")
        elif temperature < 50:
            if self.season_type == "warm":
                warnings.append("Below 50°F - warm season grass entering/in dormancy")

        humidity = state.attributes.get('humidity')
        if humidity and humidity > 85 and temperature > 75:
            warnings.append("High humidity + warmth = increased fungal disease risk. Monitor for brown patch.")

        wind_speed = state.attributes.get('wind_speed')
        if wind_speed and wind_speed > 15:
            warnings.append(f"Windy ({wind_speed} mph) - Do NOT spray chemicals, drift will occur")

        soil_temp = self._get_soil_temperature_estimate()
        if soil_temp:
            if soil_temp > 50 and soil_temp < 60:
                warnings.append(f"Estimated soil temp ~{int(soil_temp)}°F - approaching pre-emergent window")
            elif soil_temp >= 55 and soil_temp <= 70:
                warnings.append(f"Estimated soil temp ~{int(soil_temp)}°F - CRITICAL pre-emergent window")

        return warnings

    def get_pre_emergent_recommendation(self, application_history: Optional[Dict] = None) -> Dict:
        """Get detailed pre-emergent recommendation based on season and soil temp."""
        month = dt_util.now().month
        soil_temp = self._get_soil_temperature_estimate()
        applied_recently = self._check_recent_application(application_history or {}, "Weed Preventer", 90)

        result = {
            "needed": False,
            "urgency": "none",
            "reason": "",
            "timing": "",
            "product_suggestion": ""
        }

        if applied_recently:
            result["reason"] = "Pre-emergent already applied within last 90 days"
            result["timing"] = "Next application due in approximately 90 days from last application"
            return result

        if self.season_type == "warm":
            if month in [1, 2]:
                result["needed"] = True
                result["urgency"] = "medium"
                result["reason"] = "Pre-emergent window approaching for warm-season grass"
                result["timing"] = "Apply before soil temps consistently reach 55°F (typically Feb-Mar)"
                result["product_suggestion"] = "Prodiamine (Barricade) for longest control, or Dithiopyr (Dimension) for early post-emergent"
            elif month == 3:
                result["needed"] = True
                result["urgency"] = "high"
                if soil_temp and soil_temp >= 50:
                    result["reason"] = f"CRITICAL: Soil temp ~{int(soil_temp)}°F, approaching 55°F threshold for crabgrass germination"
                else:
                    result["reason"] = "Prime pre-emergent window - apply before soil reaches 55°F"
                result["timing"] = "Apply NOW for best results. Split application recommended."
                result["product_suggestion"] = "Prodiamine 65 WDG at 0.185 oz per 1,000 sq ft via sprayer, or granular at 3.5 lb per 1,000 sq ft"
            elif month == 4:
                result["needed"] = True
                result["urgency"] = "high"
                result["reason"] = "Late pre-emergent window - may still be effective"
                result["timing"] = "Apply immediately if not yet applied. Consider Dithiopyr which has early post-emergent activity."
                result["product_suggestion"] = "Dithiopyr (Dimension) - provides both pre and early post-emergent control"
            elif month in [8, 9]:
                result["needed"] = True
                result["urgency"] = "medium"
                result["reason"] = "Fall pre-emergent for winter weeds (Poa annua, henbit)"
                result["timing"] = "Apply when nighttime temps consistently drop below 70°F"
                result["product_suggestion"] = "Prodiamine for fall weed prevention"
        else:
            if month in [2, 3]:
                result["needed"] = True
                result["urgency"] = "high"
                result["reason"] = "Spring pre-emergent for cool-season grass - prevent crabgrass"
                result["timing"] = "Apply when soil temps reach 50-55°F for 3-5 consecutive days"
                result["product_suggestion"] = "Prodiamine or Dithiopyr - safe for cool-season grasses"
            elif month == 4:
                result["needed"] = True
                result["urgency"] = "medium"
                result["reason"] = "Late spring pre-emergent - still effective for some weeds"
                result["timing"] = "Apply as soon as possible for remaining effectiveness"
                result["product_suggestion"] = "Dithiopyr for late-season pre/early-post emergent control"
            elif month in [9, 10]:
                result["needed"] = True
                result["urgency"] = "medium"
                result["reason"] = "Fall pre-emergent for winter annual weeds"
                result["timing"] = "Apply when soil temps drop below 70°F"
                result["product_suggestion"] = "Prodiamine for winter weed prevention"

        return result

    def get_scalping_recommendation(self) -> Dict:
        """Get scalping recommendation based on grass type and season."""
        month = dt_util.now().month

        result = {
            "recommended": False,
            "urgency": "none",
            "reason": "",
            "timing": "",
            "how_to": ""
        }

        if self.season_type == "warm":
            if month in [2, 3]:
                soil_temp = self._get_soil_temperature_estimate()
                if soil_temp and soil_temp < 55:
                    result["recommended"] = True
                    result["urgency"] = "medium"
                    result["reason"] = "Scalp warm-season grass to remove dead material and allow sunlight to warm the soil"
                    result["timing"] = "Before green-up begins, when soil is still below 55°F"
                    result["how_to"] = "Lower mower to lowest setting (0.25-0.5 inch). Bag clippings. Apply pre-emergent after scalping."
                elif soil_temp and soil_temp >= 55:
                    result["recommended"] = True
                    result["urgency"] = "high"
                    result["reason"] = "Soil warming up - scalp NOW before active growth begins"
                    result["timing"] = "Immediately - green-up is starting or about to start"
                    result["how_to"] = "Lower mower to lowest setting (0.25-0.5 inch). Bag clippings. This promotes faster green-up."
            elif month == 4:
                result["reason"] = "Scalping window may have passed. If grass is already green, do NOT scalp - it will stress the plant."
                result["timing"] = "Too late for most warm-season grasses"
        elif self.season_type == "cool":
            result["reason"] = "Cool-season grasses should generally NOT be scalped. Maintain 2.5-4 inch height."
            result["how_to"] = "Instead of scalping, do a gradual height reduction in spring."

        return result

    def get_dethatching_recommendation(self, application_history: Optional[Dict] = None) -> Dict:
        """Get dethatching recommendation based on grass type, season, and conditions."""
        month = dt_util.now().month

        result = {
            "recommended": False,
            "urgency": "none",
            "reason": "",
            "timing": "",
            "how_to": "",
            "alternatives": ""
        }

        if self.season_type == "warm":
            if month in [4, 5, 6]:
                result["recommended"] = True
                result["urgency"] = "medium"
                result["reason"] = "Best time to dethatch warm-season grass - during active growth for quick recovery"
                result["timing"] = "Late spring to early summer when grass is actively growing"
                result["how_to"] = "Use a power dethatcher or vertical mower. Set blades to cut through thatch layer (~0.5 inch deep). Bag debris."
                result["alternatives"] = "For light thatch, core aeration may be sufficient. For heavy thatch (>0.5 inch), dethatching is recommended."
            elif month in [1, 2, 3]:
                result["reason"] = "Too early - wait until grass is actively growing (April-June) for warm-season"
                result["timing"] = "Wait until active growing season"
            elif month in [7, 8]:
                result["reason"] = "Can still dethatch but heat stress may slow recovery"
                result["timing"] = "Possible but risky - grass may struggle to recover in extreme heat"
                result["alternatives"] = "Consider waiting until next spring, or core aerate instead"
        elif self.season_type == "cool":
            if month in [8, 9, 10]:
                result["recommended"] = True
                result["urgency"] = "medium"
                result["reason"] = "Best time to dethatch cool-season grass - early fall for recovery before winter"
                result["timing"] = "Late August through October"
                result["how_to"] = "Use a power dethatcher. Overseed immediately after for best results."
                result["alternatives"] = "Core aeration is often preferred for cool-season grasses over dethatching."
            elif month in [3, 4]:
                result["recommended"] = True
                result["urgency"] = "low"
                result["reason"] = "Spring dethatching is OK but fall is preferred for cool-season grass"
                result["timing"] = "Early spring before active growth period"
                result["how_to"] = "Use a power dethatcher, but be gentle. Follow up with overseeding if needed."

        return result

    def get_aeration_recommendation(self) -> Dict:
        """Get aeration recommendation."""
        month = dt_util.now().month

        result = {
            "recommended": False,
            "urgency": "none",
            "reason": "",
            "timing": "",
            "how_to": ""
        }

        if self.season_type == "warm":
            if month in [5, 6, 7]:
                result["recommended"] = True
                result["urgency"] = "medium"
                result["reason"] = "Ideal aeration window for warm-season grass during peak growth"
                result["timing"] = "Late spring through mid-summer"
                result["how_to"] = "Core aerate when soil is moist (not wet). Make 2-3 passes in different directions. Leave cores on lawn to decompose."
        elif self.season_type == "cool":
            if month in [8, 9, 10]:
                result["recommended"] = True
                result["urgency"] = "medium"
                result["reason"] = "Ideal aeration window for cool-season grass during fall growth period"
                result["timing"] = "Late summer through early fall"
                result["how_to"] = "Core aerate when soil is moist. Overseed immediately after for best results. Top-dress with compost."
            elif month in [3, 4]:
                result["recommended"] = True
                result["urgency"] = "low"
                result["reason"] = "Spring aeration acceptable for cool-season grass"
                result["timing"] = "Early to mid spring"

        return result

    def get_seasonal_chemical_recommendations(self, application_history: Optional[Dict] = None) -> Dict[str, Dict]:
        season = self.get_current_season()
        month = dt_util.now().month
        soil_temp = self._get_soil_temperature_estimate()

        recommendations = {}

        if application_history is None:
            application_history = {}

        # Pre-emergent recommendations
        pre_emergent_rec = self.get_pre_emergent_recommendation(application_history)
        if pre_emergent_rec["needed"]:
            recommendations["Pre-emergent"] = {
                "priority": pre_emergent_rec["urgency"],
                "reason": pre_emergent_rec["reason"],
                "timing": pre_emergent_rec["timing"],
                "product": pre_emergent_rec.get("product_suggestion", "")
            }

        if self.season_type == "warm":
            if season == "spring":
                if month in [4, 5]:
                    if not self._check_recent_application(application_history, "Fertilizer", 45):
                        recommendations["Fertilizer"] = {
                            "priority": "high",
                            "reason": "Spring feeding as grass begins active growth - use balanced fertilizer",
                            "timing": "After 2-3 mowings of active growth"
                        }
                    if month == 5:
                        recommendations["T-Nex / PGR"] = {
                            "priority": "low",
                            "reason": "Consider PGR to reduce mowing frequency and improve lawn density",
                            "timing": "After grass is fully green and actively growing"
                        }
            elif season == "summer":
                if not self._check_recent_application(application_history, "Iron", 30):
                    recommendations["Iron Supplement"] = {
                        "priority": "medium",
                        "reason": "Maintain deep green color during heat stress without pushing growth",
                        "timing": "Apply early morning to avoid leaf burn"
                    }
                if not self._check_recent_application(application_history, "Grub", 120):
                    recommendations["Grub Killer"] = {
                        "priority": "high",
                        "reason": "Peak grub activity period - preventative application recommended",
                        "timing": "Early summer for preventative (Imidacloprid), mid-summer for curative (Dylox)"
                    }
                if not self._check_recent_application(application_history, "Insecticide", 90):
                    recommendations["Insecticide"] = {
                        "priority": "medium",
                        "reason": "Summer pest activity peaks - monitor for chinch bugs, armyworms",
                        "timing": "At first sign of pest activity or preventatively"
                    }
            elif season == "fall":
                if month in [9, 10]:
                    if not self._check_recent_application(application_history, "Fertilizer", 30):
                        recommendations["Fertilizer"] = {
                            "priority": "high",
                            "reason": "Fall potassium application strengthens roots for winter dormancy",
                            "timing": "6-8 weeks before first expected frost"
                        }
            elif season == "winter":
                if month == 12 and soil_temp and soil_temp > 45:
                    recommendations["Soil Conditioner"] = {
                        "priority": "low",
                        "reason": "Winter soil conditioning can improve spring green-up",
                        "timing": "During mild winter days"
                    }
        else:
            # Cool season grass
            if season == "spring":
                if not self._check_recent_application(application_history, "Fertilizer", 30):
                    recommendations["Fertilizer"] = {
                        "priority": "high" if month in [4, 5] else "medium",
                        "reason": "Spring feeding during active growth - use slow-release nitrogen",
                        "timing": "When grass is actively growing"
                    }
            elif season == "summer":
                recommendations["Disease Preventer"] = {
                    "priority": "medium",
                    "reason": "Summer disease pressure (brown patch, dollar spot) increases for cool-season grass",
                    "timing": "Preventatively when nighttime temps exceed 65°F"
                }
                if not self._check_recent_application(application_history, "Iron", 30):
                    recommendations["Iron Supplement"] = {
                        "priority": "medium",
                        "reason": "Maintain color during summer stress without nitrogen push",
                        "timing": "Apply early morning"
                    }
            elif season == "fall":
                if not self._check_recent_application(application_history, "Fertilizer", 30):
                    recommendations["Fertilizer"] = {
                        "priority": "high",
                        "reason": "MOST IMPORTANT feeding for cool-season grasses - builds root reserves",
                        "timing": "Early fall (Sept-Oct) and late fall (Nov) applications"
                    }
                recommendations["Overseeding"] = {
                    "priority": "medium",
                    "reason": "Optimal overseeding conditions for cool-season grass",
                    "timing": "Early fall - soil temps 50-65°F"
                }

        return recommendations

    def get_seasonal_task_reminders(self, application_history: Optional[Dict] = None) -> List[Dict]:
        season = self.get_current_season()
        month = dt_util.now().month

        tasks = []

        if application_history is None:
            application_history = {}

        # Scalping recommendation
        scalp_rec = self.get_scalping_recommendation()
        if scalp_rec["recommended"]:
            tasks.append({
                "task": f"Scalp lawn - {scalp_rec['how_to'][:80]}",
                "priority": scalp_rec["urgency"],
                "reason": scalp_rec["reason"],
                "deadline": scalp_rec["timing"]
            })

        # Dethatching recommendation
        dethatch_rec = self.get_dethatching_recommendation(application_history)
        if dethatch_rec["recommended"]:
            tasks.append({
                "task": f"Dethatch lawn - {dethatch_rec['how_to'][:80]}",
                "priority": dethatch_rec["urgency"],
                "reason": dethatch_rec["reason"],
                "deadline": dethatch_rec["timing"]
            })

        # Aeration recommendation
        aerate_rec = self.get_aeration_recommendation()
        if aerate_rec["recommended"]:
            tasks.append({
                "task": f"Core aerate - {aerate_rec['how_to'][:80]}",
                "priority": aerate_rec["urgency"],
                "reason": aerate_rec["reason"],
                "deadline": aerate_rec["timing"]
            })

        # Pre-emergent reminder
        pre_rec = self.get_pre_emergent_recommendation(application_history)
        if pre_rec["needed"]:
            tasks.append({
                "task": f"Apply pre-emergent - {pre_rec['product_suggestion'][:60]}",
                "priority": pre_rec["urgency"],
                "reason": pre_rec["reason"],
                "deadline": pre_rec["timing"]
            })

        if season == "spring":
            if month == 3:
                tasks.append({
                    "task": "Service mower - sharpen blades, change oil, check spark plug",
                    "priority": "medium",
                    "reason": "Prepare equipment before growing season",
                    "deadline": "Before first mow of the season"
                })
            if month in [4, 5]:
                grub_applied = self._check_recent_application(application_history, "Grub", 120)
                if not grub_applied:
                    tasks.append({
                        "task": "Plan grub prevention for early summer",
                        "priority": "medium",
                        "reason": "Grub preventative works best when applied before grubs are active",
                        "deadline": "Apply in May-June for best prevention"
                    })

        elif season == "summer":
            tasks.append({
                "task": "Monitor for heat stress - raise mowing height, water deeply and infrequently",
                "priority": "medium",
                "reason": "Hot weather increases stress, especially above 90°F",
                "deadline": "Ongoing during hot weather"
            })

            grub_applied = self._check_recent_application(application_history, "Grub Killer", 120)
            if not grub_applied:
                tasks.append({
                    "task": "Apply grub control (preventative)",
                    "priority": "high",
                    "reason": "No grub control found in last 120 days - peak grub season",
                    "deadline": "Apply now for best results"
                })

            if month in [6, 7]:
                tasks.append({
                    "task": "Check for chinch bugs and armyworms",
                    "priority": "medium",
                    "reason": "Peak pest activity period",
                    "deadline": "Scout weekly - look for irregularly shaped brown patches"
                })

        elif season == "fall":
            if not self._check_recent_application(application_history, "Fertilizer", 45):
                tasks.append({
                    "task": "Fall fertilizer application - emphasize potassium (K)",
                    "priority": "high",
                    "reason": "Strengthens roots for winter, promotes spring recovery",
                    "deadline": "6-8 weeks before first expected frost"
                })

            if self.season_type == "cool":
                tasks.append({
                    "task": "Overseed thin areas after aerating",
                    "priority": "medium",
                    "reason": "Fall is the ideal time for overseeding cool-season grass",
                    "deadline": "September-October for best establishment"
                })

            if month in [10, 11] and self.season_type == "warm":
                tasks.append({
                    "task": "Prepare for dormancy - last fertilizer, lower mowing height gradually",
                    "priority": "medium",
                    "reason": "Warm-season grass entering dormancy",
                    "deadline": "Before first hard frost"
                })

        elif season == "winter":
            tasks.append({
                "task": "Plan next year's lawn care schedule",
                "priority": "low",
                "reason": "Use dormant season to research products and plan applications",
                "deadline": "During winter months"
            })
            tasks.append({
                "task": "Equipment maintenance - clean, sharpen blades, winterize sprayer",
                "priority": "medium",
                "reason": "Maintain equipment during off-season",
                "deadline": "Before spring"
            })
            if self.season_type == "warm" and month in [1, 2]:
                tasks.append({
                    "task": "Order pre-emergent and spring fertilizer",
                    "priority": "medium",
                    "reason": "Be ready when spring arrives - popular products sell out",
                    "deadline": "January-February"
                })

        # Add weather-based tasks
        weather_warnings = self.get_temperature_warnings()
        for warning in weather_warnings:
            if "EXTREME" in warning or "FREEZE" in warning or "HARD FREEZE" in warning:
                tasks.append({
                    "task": warning,
                    "priority": "high",
                    "reason": "Weather alert",
                    "deadline": "Today"
                })

        return tasks

    def _check_recent_application(self, application_history: Dict, chemical_name: str, days_threshold: int) -> bool:
        if not application_history:
            return False

        for app_name, app_data in application_history.items():
            if chemical_name.lower() in app_name.lower() or app_name.lower() in chemical_name.lower():
                last_applied = app_data.get("last_applied")
                if last_applied:
                    try:
                        last_date = datetime.strptime(last_applied, "%Y-%m-%d")
                        current_date = dt_util.now().replace(tzinfo=None)
                        days_since = (current_date - last_date).days
                        return days_since <= days_threshold
                    except Exception:
                        continue

        return False

    def get_seasonal_summary(self, application_history: Optional[Dict] = None) -> Dict:
        return {
            "season": self.get_current_season(),
            "grass_type": self.grass_type,
            "season_type": self.season_type,
            "growing_season": self.is_grass_growing_season(),
            "dormant_season": self.is_grass_dormant_season(),
            "mow_frequency": self.get_seasonal_mow_frequency(),
            "temperature_warnings": self.get_temperature_warnings(),
            "chemical_recommendations": self.get_seasonal_chemical_recommendations(application_history),
            "task_reminders": self.get_seasonal_task_reminders(application_history),
            "pre_emergent": self.get_pre_emergent_recommendation(application_history),
            "scalping": self.get_scalping_recommendation(),
            "dethatching": self.get_dethatching_recommendation(application_history),
            "aeration": self.get_aeration_recommendation(),
            "estimated_soil_temp": self._get_soil_temperature_estimate(),
        }
