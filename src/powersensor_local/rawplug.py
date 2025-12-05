#!/usr/bin/env python3

"""Utility script for accessing the raw plug subscription data from a single
network-local Powersensor device. Intended for advanced debugging use only."""

from typing import Union
import sys

from pathlib import Path

PROJECT_ROOT = str(Path(__file__).parents[ 1])
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# pylint: disable=C0413
from powersensor_local import PlugListenerTcp,PlugListenerUdp
from powersensor_local.abstract_event_handler import AbstractEventHandler

async def print_message_ignore_event(_, message):
    """Callback for printing event data withou the event name."""
    print(message)

async def print_event(event):
    """Callback for printing an event."""
    print(event)

class RawPlug(AbstractEventHandler):
    """Main logic wrapper."""
    def __init__(self, protocol=None):
        self.plug: Union[PlugListenerTcp, PlugListenerUdp, None] = None
        if protocol is None:
            self._protocol = 'udp'
        else:
            self._protocol = 'tcp'

    async def on_exit(self):
        if self.plug is not None:
            await self.plug.disconnect()
            self.plug = None

    async def main(self):
        if len(sys.argv) < 2:
            print(f"Syntax: {sys.argv[0]} <ip> [port]")
            sys.exit(1)

        # Signal handler for Ctrl+C
        self.register_sigint_handler()
        if len(sys.argv) >= 4:
            self._protocol = sys.argv[3]
        plug = None
        if self._protocol == 'udp':
            plug = PlugListenerUdp(sys.argv[1], *sys.argv[2:3])
        elif self._protocol == 'tcp':
            plug = PlugListenerTcp(sys.argv[1], *sys.argv[2:3])
        else:
            print('Unsupported protocol:', self._protocol)
        plug.subscribe('exception', print_message_ignore_event)
        plug.subscribe('message', print_message_ignore_event)
        plug.subscribe('connecting', print_event)
        plug.subscribe('connecting', print_event)
        plug.subscribe('connected', print_event)
        plug.subscribe('disconnected', print_event)
        plug.connect()

        # Keep the event loop running until Ctrl+C is pressed
        await self.wait()

def app():
    """Application entry point."""
    RawPlug().run()

if __name__ == "__main__":
    app()
