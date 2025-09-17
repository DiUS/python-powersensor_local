#!/usr/bin/env python3

"""Utility script for accessing the raw plug subscription data from a single
network-local Powersensor device. Intended for advanced debugging use only."""

from typing import Union
import sys

from pathlib import Path

project_root = str(Path(__file__).parents[ 1])
if project_root not in sys.path:
        sys.path.append(project_root)

from powersensor_local.plug_listener import PlugListener
from powersensor_local.abstract_event_handler import AbstractEventHandler

async def print_message_ignore_event(_, message):
    print(message)

async def print_event(event):
    print(event)

class RawPlug(AbstractEventHandler):
    def __init__(self):
        self.plug: Union[PlugListener, None] = None

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

        plug = PlugListener(sys.argv[1], *sys.argv[2:2])
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
    RawPlug().run()
if __name__ == "__main__":
    app()
