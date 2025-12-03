import asyncio
import math
import sys
import statistics
from pathlib import Path
project_root = str(Path(__file__).parents[1])
if project_root not in sys.path:
    sys.path.append(project_root)

from powersensor_local.zeroconf_listener import PowersensorZeroconfApiManager, PowersensorDiscoveryService

class OffsetGetter(PowersensorZeroconfApiManager):
    def __init__(self,plugs = None):
        if plugs is None:
            plugs = {}
        super().__init__(plugs)
        self.__observed_offsets = []

    async def on_evt_msg(self, event, message):
        if event == 'battery_level' or event == 'radio_signal_quality':
            if 'starttime_utc' in message.keys():
                self.__observed_offsets.append(math.floor(message['starttime_utc']) % 30)

    async def async_collect_data(self, max_count=None):
        service = PowersensorDiscoveryService()

        await service.start(max_count)
        zeroconf_task = service.task
        self.update_plugs(service.listener.plugs)
        api_task = (
            asyncio.create_task(self.run(max_count)))

        try:
            if max_count is None:
                print("Starting data collection to determine offset. This will run indefinitely.")
            else:
                print(f"Starting data collection to determine offset. This will run for {max_count} seconds.")
            await asyncio.gather(zeroconf_task, api_task)
        except asyncio.CancelledError:
            print("Shutting down")
        finally:
            print('Data collection complete.')

    def collect_data(self, max_count=None):
        asyncio.run(self.async_collect_data(max_count))

    def get_offset(self):
        if not self.__observed_offsets:
            return -1
        else:
            return statistics.mode(self.__observed_offsets)

def get_offset_of_existing_devices(number_of_seconds = 180):
    offset_getter = OffsetGetter()
    offset_getter.collect_data(number_of_seconds)
    return offset_getter.get_offset()

async def async_get_offset_of_existing_devices(number_of_seconds = 180):
    offset_getter = OffsetGetter()
    offset_getter.collect_data(number_of_seconds)
    return offset_getter.get_offset()
if __name__ == "__main__":
    get_offset_of_existing_devices(60)