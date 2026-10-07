#!/usr/bin/env python3

"""Utility script for accessing the raw plug subscription data from a single
network-local Powersensor device. Intended for advanced debugging use only."""

import sys

from pathlib import Path
from typing import Any

PROJECT_ROOT = str(Path(__file__).parents[ 1])
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# pylint: disable=C0413
from powersensor_local import PlugListenerTcp,PlugListenerUdp
from powersensor_local.abstract_event_handler import AbstractEventHandler
from powersensor_local.xlatemsg import Event

async def print_message_ignore_event(_: str, event: Event) -> None:
    """Callback for printing event data withou the event name."""
    print(event)

async def print_event(event: Event) -> None:
    """Callback for printing an event."""
    print(event)

class RawPlug(AbstractEventHandler):
    """Main logic wrapper."""
    def __init__(self, protocol: str|None = None) -> None:
        self.plug: PlugListenerTcp | PlugListenerUdp | None = None
        if protocol is None or protocol == 'udp':
            self._protocol = 'udp'
        else:
            self._protocol = 'tcp'

    async def on_exit(self) -> None:
        if self.plug is not None:
            await self.plug.disconnect()
            self.plug = None

    async def main(self) -> None:
        if len(sys.argv) < 2:
            print(f"Syntax: {sys.argv[0]} <ip> [port [udp|tcp]]")
            sys.exit(1)

        # Signal handler for Ctrl+C
        self.register_sigint_handler()
        if len(sys.argv) >= 4:
            self._protocol = sys.argv[3]
        self.plug = None
        args: dict[str,Any] = { "ip": sys.argv[1] }
        if len(sys.argv) > 2:
          args["port"] = int(sys.argv[2])
        if self._protocol == 'udp':
            self.plug = PlugListenerUdp(**args)
        elif self._protocol == 'tcp':
            self.plug = PlugListenerTcp(**args)
        else:
            print('Unsupported protocol:', self._protocol)
            sys.exit(1)
        self.plug.subscribe('exception', print_message_ignore_event)
        self.plug.subscribe('message', print_message_ignore_event)
        self.plug.subscribe('connecting', print_event)
        self.plug.subscribe('connecting', print_event)
        self.plug.subscribe('connected', print_event)
        self.plug.subscribe('disconnected', print_event)
        self.plug.connect()

        # Keep the event loop running until Ctrl+C is pressed
        await self.wait()

def app() -> None:
    """Application entry point."""
    RawPlug().run()

if __name__ == "__main__":
    app()
