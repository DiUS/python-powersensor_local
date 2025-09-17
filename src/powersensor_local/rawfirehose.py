#!/usr/bin/env python3

"""Utility script for accessing the raw plug subscription data from all
network-local Powersensor devices. Intended for advanced debugging use only.
For all other uses, please see the API in devices.py"""

import typing
import sys
from pathlib import Path

project_root = str(Path(__file__).parents[ 1])
if project_root not in sys.path:
        sys.path.append(project_root)

from powersensor_local.listener import PowersensorListener
from powersensor_local.abstract_event_handler import AbstractEventHandler

async def print_message(obj):
    print(obj)


class RawFirehose(AbstractEventHandler):
    def __init__(self):
        self.exiting: bool = False
        self.ps: typing.Union[PowersensorListener, None] = PowersensorListener()

    async def on_exit(self):
        if self.ps is not None:
            await self.ps.unsubscribe()
            await self.ps.stop()

    async def main(self):
        if self.ps is None:
            self.ps = PowersensorListener()

        # Signal handler for Ctrl+C
        self.register_sigint_handler()

        # Scan for devices and subscribe upon completion
        await self.ps.scan()
        await self.ps.subscribe(print_message)

        # Keep the event loop running until Ctrl+C is pressed
        await self.wait()

def app():
    RawFirehose().run()

if __name__ == "__main__":
    app()
