from homeassistant.helpers.entity import Entity
from datetime import datetime, timedelta

class ChemicalApplicationSensor(Entity):
    """A sensor for tracking chemical applications."""

    def __init__(self, name, chemical, application_date, duration_days, zone):
        self._name = name
        self._chemical = chemical
        self._application_date = application_date
        self._duration_days = duration_days
        self._zone = zone
        self._state = self.calculate_days_remaining()

    def calculate_days_remaining(self):
        """Calculate how many days are left until the chemical expires."""
        end_date = self._application_date + timedelta(days=self._duration_days)
        remaining = (end_date - datetime.now()).days
        return max(remaining, 0)

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return {
            "chemical": self._chemical,
            "application_date": self._application_date.isoformat(),
            "zone": self._zone,
        }
