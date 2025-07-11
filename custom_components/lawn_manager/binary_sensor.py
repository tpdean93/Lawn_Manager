from datetime import datetime, timedelta
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
import logging

from .const import DOMAIN, DEFAULT_MOW_INTERVAL

_LOGGER = logging.getLogger(__name__)
STORAGE_KEY = "lawn_manager_data"
STORAGE_VERSION = 1

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Lawn Manager binary sensor from config entry."""
    name = entry.data.get("name")
    mow_interval = entry.data.get("mow_interval", 7)

    sensor = LawnDueSensor(name, mow_interval, hass)
    async_add_entities([sensor], update_before_add=True)


class LawnDueSensor(BinarySensorEntity):
    def __init__(self, name, mow_interval, hass):
        self._attr_name = f"{name} Needs Mowing"
        self._mow_interval = mow_interval
        self._last_mow = None
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_update(self):
        """Reload data from storage."""
        data = await self._store.async_load() or {}
        try:
            self._last_mow = dt_util.as_local(
                datetime.strptime(data.get("last_mow"), "%Y-%m-%d")
            )
        except Exception:
            self._last_mow = dt_util.now() - timedelta(days=self._mow_interval + 1)

    @property
    def is_on(self):
        """Return True if mowing is due or overdue."""
        if not self._last_mow:
            return False
        days_since = (dt_util.now() - self._last_mow).days
        return days_since >= self._mow_interval

    @property
    def extra_state_attributes(self):
        if not self._last_mow:
            return {}
        return {
            "last_mow": self._last_mow.strftime("%Y-%m-%d"),
            "interval_days": self._mow_interval,
        }

    @property
    def device_class(self):
        return "problem"  # shows as red in UI
