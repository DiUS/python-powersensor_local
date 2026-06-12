"""Abstraction interface for unified event stream from Powersensor devices."""
import asyncio
import logging
import sys

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
PROJECT_ROOT = str(Path(__file__).parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# pylint: disable=C0413
from powersensor_local.legacy_discovery import LegacyDiscovery
from powersensor_local.plug_api import PlugApi

EXPIRY_CHECK_INTERVAL_S = 30
EXPIRY_TIMEOUT_S = 5 * 60

_KNOWN_PLUG_EVENTS = [
    'average_flow',
    'average_power',
    'average_power_components',
    'battery_level',
    'exception',
    'now_relaying_for',
    'radio_signal_quality',
    'summation_energy',
    'summation_volume',
]


class _LogLevel(Enum):
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'


class _PowersensorDevicesBase:
    """Shared base for PowersensorLegacyDevices and PowersensorZeroconfDevices.

    Manages the PlugApi lifecycle, device tracking, expiry, and the event
    callback.  Subclasses are responsible for discovery — they call
    _plug_discovered(mac, ip, port) when a plug appears and
    _plug_lost(mac) when one disappears.

    Known events
    ------------
    All subclasses emit the following lifecycle events:

    **device_found**
        A device has been discovered or re-discovered.
        ``{ event: "device_found", device_type: "plug"|"sensor", mac: "..." }``

    **device_lost**
        A device has definitively disappeared (plug) or been inactive long
        enough to expire (sensor).
        ``{ event: "device_lost", mac: "..." }``

    Additionally, all events from ``xlatemsg.translate_raw_message`` may be
    issued for subscribed devices, with the event name inserted into the
    ``event`` field.  Known measurement events include:

    ``average_flow``, ``average_power``, ``average_power_components``,
    ``battery_level``, ``exception``, ``now_relaying_for``,
    ``radio_signal_quality``, ``summation_energy``, ``summation_volume``.

    When ``relay_now_relaying_for=True`` the raw ``now_relaying_for`` wire
    message is forwarded to the callback immediately after the synthesised
    ``device_found`` for the same sensor MAC.

    Note: ``scan_complete`` is only emitted by PowersensorLegacyDevices.
    """

    def __init__(
        self,
        relay_now_relaying_for: bool = False,
        logger: 'logging.Logger | None' = None,
    ) -> None:
        """Initialise the base.

        Parameters
        ----------
        relay_now_relaying_for:
            When False (default), ``now_relaying_for`` messages are consumed
            internally to synthesise ``device_found`` / ``device_lost`` events,
            matching the behaviour of the original PowersensorDevices class.
            When True the raw ``now_relaying_for`` event is forwarded to the
            caller's callback unchanged, in addition to any ``device_found``
            synthesis.  Set this to True when the caller wants to inspect relay
            metadata directly (e.g. the HA dispatcher).
        logger:
            Optional :class:`logging.Logger` instance.  When provided, the
            library emits debug/warning/error messages via this logger.  When
            None (default) the library is completely silent.
        """
        self._event_cb = None
        self._devices: dict[str, '_PowersensorDevicesBase._Device'] = {}
        self._plug_apis: dict[str, PlugApi] = {}
        self._timer: '_PowersensorDevicesBase._Timer | None' = None
        self._relay_now_relaying_for = relay_now_relaying_for
        self._logger = logger

    # ------------------------------------------------------------------
    # Internal logging helper
    # ------------------------------------------------------------------

    def _maybe_log(self, level: _LogLevel, msg: str, *args) -> None:
        """Emit a log message if a logger was provided at construction."""
        if self._logger is None:
            return
        match level:
            case _LogLevel.DEBUG:    self._logger.debug(msg, *args)
            case _LogLevel.INFO:     self._logger.info(msg, *args)
            case _LogLevel.WARNING:  self._logger.warning(msg, *args)
            case _LogLevel.ERROR:    self._logger.error(msg, *args)

    # ------------------------------------------------------------------
    # Public subscription API
    # ------------------------------------------------------------------

    def subscribe(self, mac: str) -> None:
        """Subscribe to events from the device with the given MAC address."""
        device = self._devices.get(mac)
        if device:
            device.subscribed = True

    def unsubscribe(self, mac: str) -> None:
        """Unsubscribe from events from the given MAC address."""
        device = self._devices.get(mac)
        if device:
            device.subscribed = False

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        """Stop event streaming and disconnect from all devices.

        To restart, call start() (legacy) or add_plug() (zeroconf) again.
        """
        for plug in list(self._plug_apis.values()):
            await plug.disconnect()
        self._plug_apis.clear()
        self._event_cb = None
        if self._timer:
            self._timer.terminate()
            self._timer = None

    # ------------------------------------------------------------------
    # Called by subclasses when discovery reports changes
    # ------------------------------------------------------------------

    async def _plug_discovered(self, mac: str, ip: str, port: int) -> None:
        """Called by the subclass when a plug is found or updated.

        Creates a PlugApi for the plug if one doesn't exist yet, or
        reconnects with a new address if the IP/port has changed.
        """
        if mac in self._plug_apis:
            api = self._plug_apis[mac]
            if api.ip_address == ip and api.port == port:
                return  # no change
            # Address changed — disconnect stale connection and reconnect.
            await self._plug_apis.pop(mac).disconnect()
            await self._remove_device(mac)

        await self._add_device(mac, 'plug')
        api = PlugApi(mac, ip, port)
        self._plug_apis[mac] = api
        for event in _KNOWN_PLUG_EVENTS:
            api.subscribe(event, self._reemit)
        api.connect()

    async def _plug_lost(self, mac: str) -> None:
        """Called by the subclass when a plug has definitively disappeared."""
        if mac in self._plug_apis:
            await self._plug_apis.pop(mac).disconnect()
        await self._remove_device(mac)

    # ------------------------------------------------------------------
    # Internal event routing
    # ------------------------------------------------------------------

    async def _emit_if_subscribed(self, ev: str, mac: str, obj: dict) -> None:
        if self._event_cb is None:
            return
        device = self._devices.get(mac)
        if device is not None and device.subscribed:
            obj['event'] = ev
            await self._event_cb(obj)

    async def _reemit(self, ev: str, obj: dict[str, str]) -> None:
        mac: str|None = obj.get('mac')
        if mac is None:
            self._maybe_log(_LogLevel.WARNING, "Received event '%s' with no MAC address — ignoring", ev)
            return
        device = self._devices.get(mac)
        if device is not None:
            device.mark_active()

        if ev == 'now_relaying_for':
            await self._add_device(mac, 'sensor')
            if self._relay_now_relaying_for and self._event_cb is not None:
                obj['event'] = ev
                await self._event_cb(obj)
        else:
            await self._emit_if_subscribed(ev, mac, obj)

    async def _add_device(self, mac: str, typ: str) -> None:
        if mac in self._devices:
            return
        self._devices[mac] = self._Device(mac)
        if self._event_cb is not None:
            await self._event_cb({
                'event': 'device_found',
                'mac': mac,
                'device_type': typ,
            })

    async def _remove_device(self, mac: str) -> None:
        if mac in self._devices:
            self._devices.pop(mac)
            if self._event_cb is not None:
                await self._event_cb({
                    'event': 'device_lost',
                    'mac': mac,
                })

    async def _on_timer(self) -> None:
        for device in list(self._devices.values()):
            if device.has_expired():
                await self._remove_device(device.mac)

    def _start_expiry_timer(self) -> None:
        self._timer = self._Timer(EXPIRY_CHECK_INTERVAL_S, self._on_timer)

    # ------------------------------------------------------------------
    # Supporting inner classes
    # ------------------------------------------------------------------

    class _Device:
        def __init__(self, mac: str) -> None:
            self.mac = mac
            self.subscribed = False
            self._last_active = datetime.now(timezone.utc)

        def mark_active(self) -> None:
            """Update the last activity timestamp to prevent expiry."""
            self._last_active = datetime.now(timezone.utc)

        def has_expired(self) -> bool:
            """Return True if last activity is past the expiry window."""
            delta = datetime.now(timezone.utc) - self._last_active
            return delta.total_seconds() > EXPIRY_TIMEOUT_S

    class _Timer:
        def __init__(self, interval_s: float, callback) -> None:
            self._terminate = False
            self._interval = interval_s
            self._callback = callback
            self._task = asyncio.create_task(self._run())

        def terminate(self) -> None:
            """Cancel the timer task."""
            self._terminate = True
            self._task.cancel()

        async def _run(self) -> None:
            while not self._terminate:
                await asyncio.sleep(self._interval)
                await self._callback()


class PowersensorLegacyDevices(_PowersensorDevicesBase):
    """Abstraction interface for the unified event stream from all Powersensor
    devices on the local network, using the legacy broadcast UDP discovery.

    This is the original PowersensorDevices implementation, renamed to make
    room for PowersensorZeroconfDevices.  The name PowersensorDevices is kept
    as an alias for backwards compatibility.
    """

    def __init__(
        self,
        bcast_addr: str = '<broadcast>',
        relay_now_relaying_for: bool = False,
        logger: 'logging.Logger | None' = None,
    ) -> None:
        """Create a fresh instance, without scanning for devices."""
        super().__init__(relay_now_relaying_for=relay_now_relaying_for, logger=logger)
        self._discovery = LegacyDiscovery(bcast_addr)

    async def start(self, async_event_cb) -> int:
        """Register the async event callback and scan the local network.

        The callback has the form::

            async def yourcallback(event: dict) -> None

        See _PowersensorDevicesBase for the full list of known events.

        Additionally emits:

        **scan_complete**
            Indicates discovery has completed.
            ``{ event: "scan_complete", gateway_count: N }``

        Returns the number of gateway plugs found.
        """
        if self._timer is not None:
            self._maybe_log(_LogLevel.WARNING, "start() called while already running — ignoring")
            return len(self._plug_apis)
        self._event_cb = async_event_cb
        await self._on_scanned(await self._discovery.scan())
        self._start_expiry_timer()
        return len(self._plug_apis)

    async def rescan(self) -> None:
        """Perform a fresh scan to discover added or moved devices."""
        await self._on_scanned(await self._discovery.scan())

    async def _on_scanned(self, found: list) -> None:
        for device in found:
            mac = device['id']
            ip = device['ip']
            await self._plug_discovered(mac, ip, 49476)

        if self._event_cb is not None:
            await self._event_cb({
                'event': 'scan_complete',
                'gateway_count': len(self._plug_apis),
            })


# Backwards-compatible alias.
PowersensorDevices = PowersensorLegacyDevices
