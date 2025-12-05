#!/usr/bin/env python3

"""Utility script for accessing the full event stream from all network-local
Powersensor devices. Intended for debugging use only. Please use the proper
interface in devices.py rather than parsing the output from this script."""
import typing
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# pylint: disable=C0413
from powersensor_local.devices import PowersensorDevices
from powersensor_local.abstract_event_handler import AbstractEventHandler

class EventLoopRunner(AbstractEventHandler):
    """Main logic wrapper."""
    def __init__(self):
        self.devices: typing.Union[PowersensorDevices, None] = PowersensorDevices()

    async def on_exit(self):
        if self.devices is not None:
            await self.devices.stop()

    async def on_message(self, obj):
        """Callback for printing received events."""
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
    """Application entry point."""
    EventLoopRunner().run()

if __name__ == "__main__":
    app()
