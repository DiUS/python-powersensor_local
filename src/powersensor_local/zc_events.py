#!/usr/bin/env python3

"""Firehose event stream from all Powersensor devices via mDNS/zeroconf discovery.

Intended for debugging use only.  Please use the proper interface in
zeroconf_devices.py rather than parsing the output from this script.

All events from all discovered plugs and their relayed sensors are printed
to stdout as they arrive.  Every device is subscribed to automatically.

Requires the zeroconf extra::

    pip install powersensor-local[zeroconf]
"""
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# pylint: disable=C0413
from powersensor_local.abstract_event_handler import AbstractEventHandler
from powersensor_local.zeroconf_devices import PowersensorZeroconfDevices


class ZcEventLoopRunner(AbstractEventHandler):
    """Main logic wrapper."""

    def __init__(self) -> None:
        self.devices: PowersensorZeroconfDevices = PowersensorZeroconfDevices(
            relay_now_relaying_for=True,
        )

    async def on_exit(self) -> None:
        await self.devices.stop()

    async def on_message(self, obj: dict) -> None:
        """Print every event and subscribe to any newly discovered device."""
        print(obj)
        if obj['event'] == 'device_found':
            self.devices.subscribe(obj['mac'])

    async def main(self) -> None:
        self.register_sigint_handler()
        await self.devices.start(self.on_message)
        await self.wait()


def app() -> None:
    """Application entry point."""
    ZcEventLoopRunner().run()


if __name__ == '__main__':
    app()
