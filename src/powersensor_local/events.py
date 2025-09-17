#!/usr/bin/env python3

"""Utility script for accessing the full event stream from all network-local
Powersensor devices. Intended for debugging use only. Please use the proper
interface in devices.py rather than parsing the output from this script."""
import typing
import sys
from pathlib import Path

project_root = str(Path(__file__).parents[1])
if project_root not in sys.path:
    sys.path.append(project_root)

from powersensor_local.devices import PowersensorDevices
from powersensor_local.abstract_event_handler import AbstractEventHandler

class EventLoopRunner(AbstractEventHandler):
    def __init__(self):
        self.devices: typing.Union[PowersensorDevices, None] = PowersensorDevices()

    async def on_exit(self):
        if self.devices is not None:
            await self.devices.stop()

    async def on_message(self, obj):
        print(obj)
        if obj['event'] == 'device_found':
            self.devices.subscribe(obj['mac'])

    async def main(self):
        if self.devices is None:
            self.devices = PowersensorDevices()

        # Signal handler for Ctrl+C
        self.register_sigint_handler()

        await self.devices.start(self.on_message)

        # Keep the event loop running until Ctrl+C is pressed
        await self.wait()

def app():
    EventLoopRunner().run()

if __name__ == "__main__":
    app()
