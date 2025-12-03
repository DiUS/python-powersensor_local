import asyncio
import sys
from pathlib import Path
from typing import Optional

from powersensor_local import PlugApi
from powersensor_local.mock.const import SERVICE_DOMAIN

project_root = str(Path(__file__).parents[1])
if project_root not in sys.path:
    sys.path.append(project_root)
import logging
_LOGGER = logging.getLogger(__name__)
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

class PowersensorUDPServiceListener(ServiceListener):
    def __init__(self, loop):
        self.plugs = {}
        self.loop = loop
        self._apis = {}


    def add_service(self, zc, type_, name):

        self.__add_plug(zc, type_, name)

    def remove_service(self, zc, type_, name):
        if name in self.plugs:
            del self.plugs[name]

    def update_service(self, zc, type_, name):

        self.__add_plug(zc, type_, name)


    def __add_plug(self, zc, type_, name):
        info = zc.get_service_info(type_, name)

        if info:
            self.plugs[name] = {'type': type_,
                                 'name': name,
                                 'addresses': ['.'.join(str(b) for b in addr) for addr in info.addresses],
                                 'port': info.port,
                                 'server': info.server,
                                 'properties': info.properties
                                 }

        return info

    def get_plug_data(self):
        return self.plugs


class PowersensorDiscoveryService:
    def __init__(self, service_type: str = SERVICE_DOMAIN):
        self.service_type = service_type

        self.zc: Optional[Zeroconf] = None
        self.listener: Optional[PowersensorUDPServiceListener] = None
        self.browser: Optional[ServiceBrowser] = None
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.apis = dict()

    async def start(self, max_count = None):
        """Start the mDNS discovery service"""
        if self.running:
            return


        self.running = True
        self.zc = Zeroconf()
        self.listener = PowersensorUDPServiceListener(loop =asyncio.get_running_loop())

        # Create browser
        self.browser = ServiceBrowser(self.zc, self.service_type, self.listener)

        # Start the background task
        self.task = asyncio.create_task(self._run(max_count))

    async def _run(self, max_count = None):
        """Background task that keeps the service alive"""
        count = 0
        while max_count is None or count < max_count:
            count+=1
            await asyncio.sleep(1)


    async def _start_and_run(self, max_count = None):
        await self.start(max_count)
        task = self.task

        try:
            await task
        except asyncio.CancelledError:
            print("Shutting down")



    def run(self, max_count=None):
        try:
            asyncio.run(self._start_and_run(max_count))
        except KeyboardInterrupt:
            print("Interrupted by user")

    async def stop(self):
        """Stop the mDNS discovery service"""
        self.running = False

        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        if self.zc:
            self.zc.close()
            self.zc = None

        self.browser = None
        self.listener = None

class PowersensorZeroconfApiManager:
    def __init__(self, plugs):
        self.apis = {}
        self.__plugs = plugs

    def update_plugs(self, new_plugs):
        self.__plugs = new_plugs

    async def on_evt_msg(self, event, message):

        print(event, message)
        # if event == 'battery_level' or event == 'radio_signal_quality':
        #     if 'starttime_utc' in message.keys():
        #         print(math.floor(message['starttime_utc']) % 30)


    async def run(self, max_count = None):
        count = 0
        while max_count is None or count < max_count:
            count +=1
            api_keys = self.apis.keys()
            new_keys  = self.__plugs.keys()- api_keys

            for name in new_keys:
                api_data = self.__plugs[name]
                ip = api_data['addresses'][0]
                mac = api_data['properties'][b'id'].decode('UTF-8')
                print(mac, ip)
                self.apis[name] = PlugApi(mac, ip)
                known_evs = [
                    'exception',
                    'average_flow',
                    'average_power',
                    'average_power_components',
                    'battery_level',
                    'now_relaying_for',
                    'radio_signal_quality',
                    'summation_energy',
                    'summation_volume',
                    'uncalibrated_instant_reading',
                ]
                for ev in known_evs:
                    self.apis[name].subscribe(ev, self.on_evt_msg)

                self.apis[name].connect()

            await asyncio.sleep(1.0)


async def main(max_count=None):
    service = PowersensorDiscoveryService()


    await service.start(max_count)
    zeroconf_task = service.task
    api_manager = PowersensorZeroconfApiManager(service.listener.plugs)
    api_task = asyncio.create_task(api_manager.run(max_count))

    try:
        await asyncio.gather(zeroconf_task, api_task)
    except asyncio.CancelledError:
        print("Shutting down")

if __name__ == "__main__":
    asyncio.run(main(40))
    # service = PowersensorDiscoveryService()
    # service.run(10)
    # api_manager = PowersensorZeroconfApiManager(service.listener.plugs)
    # asyncio.run(api_manager.run())