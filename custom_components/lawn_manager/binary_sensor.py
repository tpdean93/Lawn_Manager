from datetime import datetime, timedelta
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
import logging
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, DEFAULT_MOW_INTERVAL, get_storage_key

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1


async def async_setup_entry(hass, entry, async_add_entities):
    yard_zone = entry.data.get("yard_zone", "Lawn")
    mow_interval = entry.data.get("mow_interval", 7)

    sensor = LawnDueSensor(entry, yard_zone, mow_interval, hass)
    async_add_entities([sensor], update_before_add=True)


class LawnDueSensor(BinarySensorEntity):
    def __init__(self, entry, yard_zone, mow_interval, hass):
        self._entry = entry
        self._yard_zone = yard_zone
        self._attr_name = f"{yard_zone} Needs Mowing"
        self._mow_interval = mow_interval
        self._last_mow = None
        zone_storage_key = get_storage_key(entry.entry_id)
        self._store = Store(hass, STORAGE_VERSION, zone_storage_key)
        self._unsub_dispatcher = None

    async def async_added_to_hass(self):
        signal_name = f"lawn_manager_update_{self._entry.entry_id}"
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, signal_name, self._handle_update_signal
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_dispatcher:
            self._unsub_dispatcher()

    async def _handle_update_signal(self):
        await self.async_update()
        self.async_write_ha_state()

    async def async_update(self):
        data = await self._store.async_load() or {}
        try:
            if data.get("last_mow"):
                self._last_mow = dt_util.as_local(
                    datetime.strptime(data.get("last_mow"), "%Y-%m-%d")
                )
            else:
                self._last_mow = None
        except Exception:
            self._last_mow = dt_util.now() - timedelta(days=self._mow_interval + 1)

    @property
    def is_on(self):
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
    def unique_id(self):
        return f"lawn_manager_{self._entry.entry_id}_{self._yard_zone.lower().replace(' ', '_')}_needs_mowing"

    @property
    def device_class(self):
        return "problem"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._yard_zone,
            "manufacturer": "Lawn Manager",
        }
