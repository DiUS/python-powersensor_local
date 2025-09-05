#!/usr/bin/env python3

"""Utility script for accessing the plug api from a single network-local
Powersensor device. Intended for advanced debugging use only."""

import asyncio
import os
import signal
import sys
from plug_api import PlugApi

exiting = False
plug = None

async def do_exit():
    global exiting
    global plug
    if plug != None:
        await plug.disconnect()
        del plug
    exiting = True

async def on_evt_msg(evt, msg):
    print(evt, msg)

async def on_evt(evt):
    print(evt)

async def main():
    if len(sys.argv) < 3:
        print(f"Syntax: {sys.argv[0]} <id> <ip> [port]")
        sys.exit(1)

    # Signal handler for Ctrl+C
    def handle_sigint(signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        asyncio.create_task(do_exit())

    signal.signal(signal.SIGINT, handle_sigint)

    global plug
    plug = PlugApi(sys.argv[1], sys.argv[2], *sys.argv[3:3])
    known_evs = [
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
        plug.subscribe(ev, on_evt_msg)
    plug.connect()

    # Keep the event loop running until Ctrl+C is pressed
    while not exiting:
        await asyncio.sleep(1)

def app():
    asyncio.run(main())

if __name__ == "__main__":
    app()
