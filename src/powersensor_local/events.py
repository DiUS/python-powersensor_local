#!/usr/bin/env python3

"""Utility script for accessing the full event stream from all network-local
Powersensor devices. Intended for debugging use only. Please use the proper
interface in devices.py rather than parsing the output from this script."""

import asyncio
import os
import signal
import sys

from pathlib import Path
project_root = str(Path(__file__).parents[1])
if project_root not in sys.path:
    sys.path.append(project_root)

from powersensor_local.devices import PowersensorDevices

exiting = False
devices = None

async def do_exit():
    global exiting
    global devices
    if devices != None:
        await devices.stop()
    exiting = True

async def on_msg(obj):
    print(obj)
    global devices
    if obj['event'] == 'device_found':
        devices.subscribe(obj['mac'])

async def main():
    global devices
    devices = PowersensorDevices()

    # Signal handler for Ctrl+C
    def handle_sigint(signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        asyncio.create_task(do_exit())

    signal.signal(signal.SIGINT, handle_sigint)

    await devices.start(on_msg)

    # Keep the event loop running until Ctrl+C is pressed
    while not exiting:
        await asyncio.sleep(1)

def app():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
    loop.stop()

if __name__ == "__main__":
    app()
