from datetime import datetime, timedelta
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, CONF_LOCATION, CONF_MOW_INTERVAL, DEFAULT_NAME, DEFAULT_MOW_INTERVAL

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Lawn Manager sensor platform from YAML config."""
    name = config.get(CONF_NAME, DEFAULT_NAME)
    location = config.get(CONF_LOCATION, "Unknown")
    mow_interval = config.get(CONF_MOW_INTERVAL, DEFAULT_MOW_INTERVAL)

    last_mow_date = hass.states.get(f\"sensor.{DOMAIN}_last_mow_date\")
    if last_mow_date:
        last_mow_str = last_mow_date.state
        try:
            last_mow = datetime.strptime(last_mow_str, \"%Y-%m-%d\")
        except Exception:
            last_mow = datetime.now() - timedelta(days=mow_interval + 1)
    else:
        last_mow = datetime.now() - timedelta(days=mow_interval + 1)

    add_entities([
        LawnMowSensor(name, location, last_mow, mow_interval)
    ])

class LawnMowSensor(SensorEntity):
    """Sensor for time since last mowing."""

    def __init__(self, name, location, last_mow, mow_interval):
        self._name = f\"{name} Mow Interval\"
        self._location = location
        self._last_mow = last_mow
        self._mow_interval = mow_interval
        self._state = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        days_since = (datetime.now() - self._last_mow).days
        return days_since

    @property
    def extra_state_attributes(self):
        next_due = self._last_mow + timedelta(days=self._mow_interval)
        return {
            \"location\": self._location,
            \"last_mow\": self._last_mow.strftime(\"%Y-%m-%d\"),
            \"next_mow_due\": next_due.strftime(\"%Y-%m-%d\"),
            \"mow_interval_days\": self._mow_interval,
        }
