import random
from ElectricitySensor import ElectricitySensor


class SolarSensor(ElectricitySensor):
    """Simulates a magnetic sensor"""

    def __init__(self, mac: str, update_interval: float = 30.0,shared_state : dict | None = None):
        super().__init__(mac, 'solar',  update_interval, shared_state)
        self._current_summation = -699691872

    def power(self):
        if self._last_power is None:
            self._last_power = -771
        self._last_power -= round(random.gauss(0, 60))
        return self._last_power