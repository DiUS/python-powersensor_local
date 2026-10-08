"""Zeroconf/mDNS-based discovery for Powersensor devices.

This module provides PowersensorZeroconfDevices, which uses continuous mDNS
browsing to discover Powersensor plugs rather than the alternative, legacy
one-shot UDP broadcast in PowersensorLegacyDevices.

The zeroconf package is an optional dependency.  Install it via::

    pip install powersensor-local[zeroconf]

Architecture
------------
PowersensorZeroconfDevices owns the full lifecycle:

- It starts a zeroconf AsyncServiceBrowser that calls back on plug
  add/update/remove.
- Plug removals are debounced (default 60 s) to absorb transient disappearances
  such as reboots or DHCP renewals.

Zeroconf instance ownership
----------------------------
If ``zeroconf_instance`` is None (the default), the class creates and owns a
Zeroconf instance and closes it in stop().  If a Zeroconf instance is passed
in, the caller owns it and the class will not close it — this is the correct
pattern for Home Assistant, which maintains a single shared zeroconf instance.

Thread safety
-------------
PowersensorZeroconfDevices uses purely async zeroconf discovery where all
callbacks are fired on the event loop rather than a separate thread. Older
versions of zeroconf that do not provide this guarantee are not supported.
Mixing of event loops is also not supported - a single
PowersensorZeroconfDevices cannot be used on more than one event loop or thread.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any, Callable, Coroutine

from .devices import _AsyncCallback, _LogLevel, _PowersensorDevicesBase

_InternalCallback = Coroutine[None, None, None]


_SERVICE_TYPE_UDP = '_powersensor._udp.local.'
_SERVICE_TYPE_TCP = '_powersensor._tcp.local.'

_DEBOUNCE_DEFAULT_S = 60.0


try:
    import zeroconf as _zc
    from zeroconf.asyncio import AsyncServiceBrowser

    class PowersensorZeroconfDevices(_PowersensorDevicesBase):
        """Discovers and manages Powersensor plugs via continuous mDNS browsing.

        Usage example (no existing zeroconf instance)::

            devices = PowersensorZeroconfDevices()
            await devices.start(my_callback)
            # plugs arrive via my_callback as device_found events
            # ...
            await devices.stop()

        Usage example (HA — pass the shared zeroconf instance)::

            zc = await homeassistant.components.zeroconf.async_get_instance(hass)
            devices = PowersensorZeroconfDevices(zeroconf_instance=zc)
            await devices.start(my_callback)

        The callback signature is the same as PowersensorLegacyDevices.start():
        ``async def callback(event: dict) -> None``

        Lifecycle events emitted:

        **device_found**
            ``{ event: "device_found", device_type: "plug"|"sensor", mac: "..." }``

        **device_lost**
            ``{ event: "device_lost", mac: "..." }``

        Note: ``scan_complete`` is NOT emitted — mDNS browsing is continuous and
        has no defined completion point.
        """

        def __init__(
                self,
                zeroconf_instance: Any = None,
                service_type: str = _SERVICE_TYPE_UDP,
                debounce_timeout: float = _DEBOUNCE_DEFAULT_S,
                relay_now_relaying_for: bool = False,
                logger: 'logging.Logger | None' = None,
        ) -> None:
            """Initialise.

            Parameters
            ----------
            zeroconf_instance:
                An existing ``Zeroconf`` instance to use.  If None, one is created
                and owned by this object (and closed in stop()).
            service_type:
                The mDNS service type to browse.  Defaults to the UDP service
                ``_powersensor._udp.local.``; pass ``_powersensor._tcp.local.``
                to use TCP transport instead.
            debounce_timeout:
                Seconds to wait after a ``remove_service`` callback before treating
                the plug as truly gone.  Defaults to 60 s.
            relay_now_relaying_for:
                See _PowersensorDevicesBase for documentation.
            logger:
                See _PowersensorDevicesBase for documentation.
            """
            super().__init__(relay_now_relaying_for=relay_now_relaying_for, logger=logger)
            self._zc_instance = zeroconf_instance
            self._zc_owned = zeroconf_instance is None  # True → we close it in stop()
            self._service_type = service_type
            self._debounce_seconds = debounce_timeout
            self._browser: Any = None
            self._listener: _Listener | None = None
            self._pending_removals: dict[str, asyncio.TimerHandle] = {}
            self._internal_callbacks: set[asyncio.Task[None]] = set()

        # ------------------------------------------------------------------
        # Lifecycle
        # ------------------------------------------------------------------

        async def start(self, async_event_cb: _AsyncCallback) -> None:
            """Register the event callback and start the mDNS service browser.

            The browser is event-driven; no polling loop is started here.
            Plugs already present on the network will trigger add_service
            callbacks shortly after the browser starts.
            """
            if self._browser is not None:
                self._maybe_log(_LogLevel.WARNING, "start() called while already running — ignoring")
                return

            self._event_cb = async_event_cb
            self._start_expiry_timer()

            if self._zc_instance is None:
                self._zc_instance = _zc.Zeroconf()

            self._listener = _Listener(self)
            self._browser = AsyncServiceBrowser(
                self._zc_instance, self._service_type, self._listener
            )

        async def stop(self) -> None:
            """Stop browsing, cancel pending removals, and disconnect all plugs."""
            # This should be a noop under sane conditions
            for cb in self._internal_callbacks:
              cb.cancel()

            self._event_cb = None

            for handle in list(self._pending_removals.values()):
                handle.cancel()
            self._pending_removals.clear()

            if self._browser is not None:
                await self._browser.async_cancel()
                self._browser = None

            self._listener = None

            if self._zc_owned and self._zc_instance is not None:
                self._zc_instance.close()
                self._zc_instance = None

            await super().stop()

        # ------------------------------------------------------------------
        # Debounce helpers
        # ------------------------------------------------------------------

        def _schedule_removal(self, mac: str) -> None:
            if mac in self._pending_removals:
                return
            loop = asyncio.get_running_loop()
            handle = loop.call_later(
                self._debounce_seconds,
                self._on_debounce_expired,
                mac,
            )
            self._pending_removals[mac] = handle
            self._maybe_log(_LogLevel.DEBUG, "Scheduled removal for %s in %.0f s", mac, self._debounce_seconds)

        def _on_debounce_expired(self, mac: str) -> None:
            """Called by the event loop when the debounce timer fires."""
            self._pending_removals.pop(mac, None)
            self._maybe_log(_LogLevel.INFO, "Plug %s still absent after debounce — removing", mac)
            self._internal_callback(self._plug_lost(mac))

        def _cancel_pending_removal(self, mac: str, source: str) -> None:
            handle = self._pending_removals.pop(mac, None)
            if handle:
                handle.cancel()
                self._maybe_log(_LogLevel.DEBUG, "Cancelled pending removal for %s (%s)", mac, source)

        # ------------------------------------------------------------------
        # Called from _Listener
        # ------------------------------------------------------------------

        async def _on_zc_add(self, mac: str, ip: str, port: int) -> None:
            self._cancel_pending_removal( mac, 'zeroconf add')
            await self._plug_discovered(mac, ip, port)

        async def _on_zc_update(self, mac: str, ip: str, port: int) -> None:
            self._cancel_pending_removal(mac, 'zeroconf update')
            await self._plug_discovered(mac, ip, port)

        async def _on_zc_remove(self, mac: str) -> None:
            self._schedule_removal(mac)

        # ------------------------------------------------------------------
        # Sync to async bridge for callbacks, per asyncio docs
        # ------------------------------------------------------------------

        def _internal_callback(self, coro: _InternalCallback) -> None:
            """Helper to prevent gc collection of short-lived callback tasks."""
            task = asyncio.create_task(coro)
            self._internal_callbacks.add(task)
            task.add_done_callback(self._internal_callbacks.discard)


    class _Listener(_zc.ServiceListener):
        """Zeroconf ServiceListener that forwards events to PowersensorZeroconfDevices."""

        def __init__(self, owner: PowersensorZeroconfDevices) -> None:
            self._owner = owner
            self._name_to_mac: dict[str, str] = {}

        def _extract(self, zc: Any, type_: str, name: str) -> tuple[str, str, int] | None:
            """Return (mac, ip, port) from the zeroconf cache, or None.

            Uses ServiceInfo.load_from_cache() rather than
            Zeroconf.get_service_info() for two reasons:

            1. On zeroconf >= 0.32 (including HA's 0.149.x), ServiceBrowser
               callbacks run inside the asyncio event loop.  Calling
               get_service_info() from there blocks waiting for a DNS reply
               that can never be processed because the event loop is occupied —
               it deadlocks, times out after 3 s, and silently returns None,
               causing the device to be dropped.

            2. load_from_cache() is synchronous, non-blocking, and explicitly
               documented as threadsafe.  The ServiceBrowser guarantees the
               cache is populated before firing add_service / update_service,
               so the record is always present when this method is called.
            """
            info = _zc.ServiceInfo(type_, name)
            if not info.load_from_cache(zc):
                self._owner._maybe_log(
                    _LogLevel.WARNING,
                    "No cache entry for %s — device will appear on next mDNS announcement",
                    name,
                )
                return None

            addresses = info.parsed_addresses()
            if not addresses:
                self._owner._maybe_log(_LogLevel.WARNING, "No addresses in zeroconf cache record for %s", name)
                return None

            try:
                raw_id = info.properties[b'id']
            except KeyError:
                self._owner._maybe_log(_LogLevel.ERROR, "Missing 'id' property in zeroconf record for %s", name)
                return None

            if raw_id is None:
                self._owner._maybe_log(_LogLevel.ERROR, "'id' property in zeroconf record for %s has no value", name)
                return None

            if info.port is None:
                self._owner._maybe_log(_LogLevel.ERROR, "No port in zeroconf record for %s", name)
                return None

            return raw_id.decode('utf-8'), addresses[0], info.port

        def add_service(self, zc: Any, type_: str, name: str) -> None:
            result = self._extract(zc, type_, name)
            if result is None:
                self._owner._maybe_log(
                    _LogLevel.WARNING,
                    "add_service: no info available for %s — will retry on next announcement",
                    name,
                )
                return
            mac, ip, port = result
            self._name_to_mac[name] = mac
            self._owner._internal_callback(self._owner._on_zc_add(mac, ip, port))

        def update_service(self, zc: Any, type_: str, name: str) -> None:
            result = self._extract(zc, type_, name)
            if result is None:
                self._owner._maybe_log(
                    _LogLevel.WARNING,
                    "update_service: no info available for %s — will retry on next announcement",
                    name,
                )
                return
            mac, ip, port = result
            self._name_to_mac[name] = mac
            self._owner._internal_callback(self._owner._on_zc_update(mac, ip, port))

        def remove_service(self, zc: Any, type_: str, name: str) -> None:
            mac = self._name_to_mac.pop(name, None)
            if mac is None:
                self._owner._maybe_log(
                    _LogLevel.WARNING,
                    "remove_service for %s: MAC not in cache — removal ignored", name,
                )
                return
            self._owner._internal_callback(self._owner._on_zc_remove(mac))

except ImportError as exc:
    _zeroconf_import_error = exc

    class PowersensorZeroconfDevices(_PowersensorDevicesBase):  # type: ignore[no-redef]
        """Stub raised when the optional zeroconf package is not installed.

        To use mDNS-based discovery, install the zeroconf extra::

            pip install powersensor-local[zeroconf]
        """

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__()
            raise ImportError(
                "The 'zeroconf' package is required for PowersensorZeroconfDevices. "
                "Install it with: pip install powersensor-local[zeroconf]"
            ) from _zeroconf_import_error
