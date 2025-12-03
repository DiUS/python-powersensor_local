import asyncio
import datetime
import logging
import random
import time
from abc import abstractmethod, ABC
from const import SENSOR_OFFSET_KEY

logger = logging.getLogger(__name__)

class MockSensor(ABC):
    """Base class for mock sensors that generate realistic data streams"""

    def __init__(self, mac: str, role: str | None=None,  update_interval: float = 5.0, shared_state : dict | None = None):
        self.mac = mac
        self.role = role
        self.update_interval = update_interval
        self._last_raw_rssi = None
        self._last_battery_microvolt = None
        self._last_power = None
        self._current_summation = None
        if shared_state is None:
            self._shared_state = dict()
        else:
            self._shared_state = shared_state

    @abstractmethod
    def get_unit(self)->str:
        pass

    def get_raw_rssi(self):
        self._last_raw_rssi = round(random.gauss(-95.71486761710794, 1.659845729993101))
        return self._last_raw_rssi

    def get_rssi(self):
        return  float(self._last_raw_rssi + random.gauss(-0.016810085782794366, 1.5284142221819026))

    def summation_start(self):
        return 1761122290

    def battery_microvolt(self):
        if self._last_battery_microvolt is None:
            self._last_battery_microvolt = 4057056
        sample = random.random()
        if sample <= 0.008125:
            self._last_battery_microvolt -= 8192
        elif sample <= 0.203125:
            self._last_battery_microvolt -= 4096
        elif sample <= 0.796875:
            pass
        elif sample <= 0.991875:
            self._last_battery_microvolt += 4096
        else:
            self._last_battery_microvolt += 8192
        return self._last_battery_microvolt

    def duration(self):
        return int(self.update_interval)

    def power(self):
        if self._last_power is None:
            self._last_power = 512
        self._last_power += round(random.gauss(0, 60))
        return self._last_power

    def summation(self):
        if self._current_summation is None:
            self._current_summation = 683508996
        self._current_summation += int(self.update_interval*self._last_power)
        return self._current_summation

    def generate_reading(self) -> dict:
        return {'starttime': int( datetime.datetime.now(datetime.timezone.utc).timestamp()),
         'raw_rssi': self.get_raw_rssi(),
         'device': 'sensor',
         'rssi': self.get_rssi(),
         'type': 'instant_power',
         'summation_start': self.summation_start(),
         'batteryMicrovolt': self.battery_microvolt(),
         'mac': self.mac,
         'duration': self.duration(),
         'role': self.role,
         'power': self.power(),
         'unit': self.get_unit(),
         'summation': self.summation()}

    async def run(self, callback):
        """
        Continuously generate sensor readings and call the callback.

        Args:
            callback: async function to call with each reading
        """
        logger.info(f"Sensor {self.mac} starting (interval: {self.update_interval}s)")
        while True:
            try:
                offset = self._shared_state.get(SENSOR_OFFSET_KEY, 0) % self.update_interval
                current_second = time.time() % self.update_interval

                if offset < current_second:
                    offset += self.update_interval
                await asyncio.sleep(offset - current_second)
                reading = self.generate_reading()
                logger.debug(f"Sensor {self.mac} calling callback with reading: {reading}")
                await callback(reading)
                logger.debug(f"Sensor {self.mac} callback completed")
            except Exception as e:
                logger.error(f"Sensor {self.mac} error in run loop: {e}", exc_info=True)