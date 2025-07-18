from datetime import datetime, timedelta
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
import logging
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, DEFAULT_MOW_INTERVAL, get_storage_key

_LOGGER = logging.getLogger(__name__)
STORAGE_KEY = "lawn_manager_data"
STORAGE_VERSION = 1

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Lawn Manager binary sensor from config entry."""
    name = entry.data.get("name")
    mow_interval = entry.data.get("mow_interval", 7)

    sensor = LawnDueSensor(entry, name, mow_interval, hass)
    async_add_entities([sensor], update_before_add=True)


class LawnDueSensor(BinarySensorEntity):
    def __init__(self, entry, name, mow_interval, hass):
        self._entry = entry
        self._attr_name = f"{name} Needs Mowing"
        self._mow_interval = mow_interval
        self._last_mow = None
        # Use zone-specific storage
        zone_storage_key = get_storage_key(entry.entry_id)
        self._store = Store(hass, STORAGE_VERSION, zone_storage_key)
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
