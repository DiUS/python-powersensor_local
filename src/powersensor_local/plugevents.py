#!/usr/bin/env python3

"""Utility script for accessing the plug api from a single network-local
Powersensor device. Intended for advanced debugging use only."""

import sys
from typing import Union
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).parents[ 1])
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# pylint: disable=C0413
from powersensor_local.plug_api import PlugApi
from powersensor_local.abstract_event_handler import AbstractEventHandler

async def print_event_and_message(event, message):
    """Callback for printing event data."""
    print(event, message)

class PlugEvents(AbstractEventHandler):
    """Main logic wrapper."""
    def __init__(self):
        self.plug: Union[PlugApi, None] = None

    async def on_exit(self):
        if self.plug is not None:
            await self.plug.disconnect()
            self.plug = None

    async def main(self):
        if len(sys.argv) < 3:
            print(f"Syntax: {sys.argv[0]} <id> <ip> [port]")
            sys.exit(1)

        # Signal handler for Ctrl+C
        self.register_sigint_handler()

        plug = PlugApi(sys.argv[1], sys.argv[2], *sys.argv[3:3])
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
            plug.subscribe(ev, print_event_and_message)
        plug.connect()

        # Keep the event loop running until Ctrl+C is pressed
        await self.wait()

def app():
    """Application entry point."""
    PlugEvents().run()

if __name__ == "__main__":
    app()
