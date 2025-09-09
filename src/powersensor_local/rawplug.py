#!/usr/bin/env python3

"""Utility script for accessing the raw plug subscription data from a single
network-local Powersensor device. Intended for advanced debugging use only."""

import asyncio
import os
import signal
import sys
from plug_listener import PlugListener

exiting = False
plug = None

async def do_exit():
    global exiting
    global plug
    if plug != None:
        await plug.disconnect()
        del plug
    exiting = True

async def on_evt_msg(_, msg):
    print(msg)

async def on_evt(evt):
    print(evt)

async def main():
    if len(sys.argv) < 2:
        print(f"Syntax: {sys.argv[0]} <ip> [port]")
        sys.exit(1)

    # Signal handler for Ctrl+C
    def handle_sigint(signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        asyncio.create_task(do_exit())

    signal.signal(signal.SIGINT, handle_sigint)

    global plug
    plug = PlugListener(sys.argv[1], *sys.argv[2:2])
    plug.subscribe('exception', on_evt_msg)
    plug.subscribe('message', on_evt_msg)
    plug.subscribe('connecting', on_evt)
    plug.subscribe('connecting', on_evt)
    plug.subscribe('connected', on_evt)
    plug.subscribe('disconnected', on_evt)
    plug.connect()

    # Keep the event loop running until Ctrl+C is pressed
    while not exiting:
        await asyncio.sleep(1)

def app():
    asyncio.run(main())

if __name__ == "__main__":
    app()
