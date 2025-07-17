from datetime import datetime, timedelta
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
import logging
from homeassistant.helpers.dispatcher import async_dispatcher_connect

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
        """Reload data from storage."""
        data = await self._store.async_load() or {}
        try:
            # Parse the date string and ensure it's treated as local date
            date_str = data.get("last_mow")
            if date_str:
                # Parse as date only, no time component
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                # Create datetime at midnight in local timezone
                self._last_mow = dt_util.as_local(
                    datetime.combine(parsed_date, datetime.min.time())
                )
            else:
                self._last_mow = None
        except Exception as e:
            _LOGGER.error("Error parsing last_mow date: %s", e)
            self._last_mow = dt_util.now() - timedelta(days=self._mow_interval + 1)

    @property
    def is_on(self):
        """Return True if mowing is due or overdue."""
        if not self._last_mow:
            return False
        due_date = self._last_mow + timedelta(days=self._mow_interval)
        return dt_util.now().date() >= due_date.date()

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
