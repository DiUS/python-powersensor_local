"""Abstraction interface for unified event stream from Powersensor devices"""
import asyncio
import sys

from datetime import datetime, timezone
from pathlib import Path
PROJECT_ROOT = str(Path(__file__).parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# pylint: disable=C0413
from powersensor_local.legacy_discovery import LegacyDiscovery
from powersensor_local.plug_api import PlugApi

EXPIRY_CHECK_INTERVAL_S = 30
EXPIRY_TIMEOUT_S = 5 * 60

class PowersensorDevices:
    """Abstraction interface for the unified event stream from all Powersensor 
    devices on the local network.
    """

    def __init__(self, bcast_addr='<broadcast>'):
        """Creates a fresh instance, without scanning for devices."""
        self._event_cb = None
        self._discovery = LegacyDiscovery(bcast_addr)
        self._devices = {}
        self._timer = None
        self._plug_apis = {}

    async def start(self, async_event_cb):
        """Registers the async event callback function and starts the scan
        of the local network to discover present devices. The callback is
        of the form

        async def yourcallback(event: dict)

        Known events:

        scan_complete:
            Indicates the discovery of Powersensor devices has completed.
            Emitted in response to start() and rescan() calls.
            The number of found gateways (plugs) is reported.

            { event: "scan_complete", gateway_count: N }

        device_found:
            A new device found on the network.
            The order found devices are announced is not fixed.

            { event: "device_found",
              device_type: "plug" or "sensor",
              mac: "...",
            }

        device_lost:
            A device appears to no longer be present on the network.

            { event: "device_lost", mac: "..." }


        Additionally, all events described in xlatemsg.translate_raw_message
        may be issued. The event name is inserted into the field 'event'.


        The start function returns the number of found gateway plugs.
        Powersensor devices aren't found directly as they are typically not
        on the network, but are instead detected when they relay data through
        a plug via long-range radio.
        """
        self._event_cb = async_event_cb
        await self._on_scanned(await self._discovery.scan())
        self._timer = self._Timer(EXPIRY_CHECK_INTERVAL_S, self._on_timer)
        return len(self._plug_apis)

    async def rescan(self):
        """Performs a fresh scan of the network to discover added devices,
        or devices which have changed their IP address for some reason."""
        await self._on_scanned(await self._discovery.scan())

    async def stop(self):
        """Stops the event streaming and disconnects from the devices.
        To restart the event streaming, call start() again."""
        for plug in self._plug_apis.values():
            await plug.disconnect()
        self._plug_apis = {}
        self._event_cb = None
        if self._timer:
            self._timer.terminate()
            self._timer = None

    def subscribe(self, mac):
        """Subscribes to events from the device with the given MAC address."""
        device = self._devices.get(mac)
        if device:
            device.subscribed = True

    def unsubscribe(self, mac):
        """Unsubscribes from events from the given MAC address."""
        device = self._devices.get(mac)
        if device:
            device.subscribed = False

    async def _emit_if_subscribed(self, ev, obj):
        if self._event_cb is None:
            return
        device = self._devices.get(obj.get('mac'))
        if device is not None and device.subscribed:
            obj['event'] = ev
            await self._event_cb(obj)

    async def _reemit(self, ev, obj):
        mac = obj['mac']
        device = self._devices.get(mac)
        if device is not None:
            device.mark_active()

        if ev == 'now_relaying_for':
            await self._add_device(mac, 'sensor')
        else:
            await self._emit_if_subscribed(ev, obj)

    async def _on_scanned(self, found):
        for device in found:
            mac = device['id']
            ip = device['ip']
            if not mac in self._devices:
                await self._add_device(mac, 'plug')
                api = PlugApi(mac, ip)
                self._plug_apis[mac] = api
                api.subscribe('average_flow', self._reemit)
                api.subscribe('average_power', self._reemit)
                api.subscribe('average_power_components', self._reemit)
                api.subscribe('battery_level', self._reemit)
                api.subscribe('exception', self._reemit)
                api.subscribe('now_relaying_for', self._reemit)
                api.subscribe('radio_signal_quality', self._reemit)
                api.subscribe('summation_energy', self._reemit)
                api.subscribe('summation_volume', self._reemit)
                api.connect()

        await self._event_cb({
            'event': 'scan_complete',
            'gateway_count': len(found),
        })

    async def _on_timer(self):
        devices = list(self._devices.values())
        for device in devices:
            if device.has_expired():
                await self._remove_device(device.mac)

    async def _add_device(self, mac, typ):
        if mac in self._devices:
            return
        self._devices[mac] = self._Device(mac)
        await self._event_cb({
            'event': 'device_found',
            'mac': mac,
            'device_type:': typ,
        })

    async def _remove_device(self, mac):
        if mac in self._devices:
            self._devices.pop(mac)
            await self._event_cb({
                'event': 'device_lost',
                'mac': mac,
            })

    ### Supporting classes ###

    class _Device:
        def __init__(self, mac):
            self.mac = mac
            self.subscribed = False
            self._last_active = datetime.now(timezone.utc)

        def mark_active(self):
            """Updates the last activity time to prevent expiry."""
            self._last_active = datetime.now(timezone.utc)

        def has_expired(self):
            """Checks whether the last activity time is past the expiry."""
            now = datetime.now(timezone.utc)
            delta = now - self._last_active
            return delta.total_seconds() > EXPIRY_TIMEOUT_S

    class _Timer: # pylint: disable=R0903
        def __init__(self, interval_s, callback):
            self._terminate = False
            self._interval = interval_s
            self._callback = callback
            self._task = asyncio.create_task(self._run())

        def terminate(self):
            """Disables the timer and cancels the associated task."""
            self._terminate = True
            self._task.cancel()

        async def _run(self):
            while not self._terminate:
                await asyncio.sleep(self._interval)
                await self._callback()
