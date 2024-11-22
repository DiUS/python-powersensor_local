#!/usr/bin/env python3

"""Utility script for accessing the raw plug subscription data from all
network-local Powersensor devices. Intended for advanced debugging use only.
For all other uses, please see the API in devices.py"""

import asyncio
import os
import signal
import sys

if __name__ == "__main__":
    # Make CLI runnable from source tree
    package_source_path = os.path.dirname(os.path.dirname(__file__))
    sys.path.insert(0, package_source_path)
    __package__ = "powersensor_local"

from .listener import PowersensorListener


exiting = False
ps = None

async def do_exit():
    global exiting
    global ps
    if ps != None:
        await ps.unsubscribe()
        await ps.stop()
    exiting = True

async def on_msg(data):
    print(data)

async def main():
    global ps
    ps = PowersensorListener()

    # Signal handler for Ctrl+C
    def handle_sigint(signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        asyncio.create_task(do_exit())

    signal.signal(signal.SIGINT, handle_sigint)

    # Scan for devices and subscribe upon completion
    await ps.scan()
    await ps.subscribe(on_msg)

    # Keep the event loop running until Ctrl+C is pressed
    while not exiting:
        await asyncio.sleep(1)

def app():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
    loop.stop()

if __name__ == "__main__":
    app()
