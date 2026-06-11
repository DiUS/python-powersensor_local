"""Zeroconf/mDNS-based discovery for Powersensor devices.

This module provides PowersensorZeroconfDevices, which uses continuous mDNS
browsing to discover Powersensor plugs rather than the legacy one-shot UDP
broadcast in PowersensorLegacyDevices.

The zeroconf package is an optional dependency.  Install it via::

    pip install powersensor-local[zeroconf]

Architecture
------------
PowersensorZeroconfDevices owns the full lifecycle:

- It starts a zeroconf ServiceBrowser that calls back on plug add/update/remove.
- Plug removals are debounced (default 60 s) to absorb transient disappearances
  such as reboots or DHCP renewals.
- The public add_plug() / remove_plug() methods are the seam between discovery
  and the plug API lifecycle, and can also be called directly (e.g. from a
  test or from HA's own mDNS handler) without needing a real zeroconf instance.

Zeroconf instance ownership
----------------------------
If ``zeroconf_instance`` is None (the default), the class creates and owns a
Zeroconf instance and closes it in stop().  If a Zeroconf instance is passed
in, the caller owns it and the class will not close it — this is the correct
pattern for Home Assistant, which maintains a single shared zeroconf instance.

Thread safety
-------------
On zeroconf >= 0.32 (including Home Assistant's 0.149.x), ServiceBrowser
callbacks run inside the asyncio event loop rather than on a background thread.
On older zeroconf (e.g. 1.0.0, which used a select() thread), they run on a
background thread.

``_Listener`` is therefore written to be safe in both models:

- ``_extract`` uses ``ServiceInfo.load_from_cache()`` rather than
  ``Zeroconf.get_service_info()``.  On >= 0.32, calling get_service_info()
  from inside a ServiceBrowser callback deadlocks — it blocks waiting for a
  DNS reply that can never arrive because it holds the event loop.
  load_from_cache() is synchronous, non-blocking, and explicitly threadsafe;
  the ServiceBrowser guarantees the cache is populated before firing the
  callback, so the record is always present.

- ``_name_to_mac`` is populated in ``add_service`` / ``update_service`` and
  consumed in ``remove_service``.  On >= 0.32 all three callbacks run on the
  same event loop thread, so no locking is needed.  On older versions they run
  on the same zeroconf background thread, so no locking is needed there either.

- All work that touches PowersensorZeroconfDevices state crosses the thread
  boundary via ``loop.call_soon_threadsafe``, making it safe regardless of
  which threading model the installed zeroconf uses.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = str(Path(__file__).parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from powersensor_local.devices import _PowersensorDevicesBase

_SERVICE_TYPE_UDP = '_powersensor._udp.local.'
_SERVICE_TYPE_TCP = '_powersensor._tcp.local.'

_DEBOUNCE_DEFAULT_S = 60.0


try:
    import zeroconf as _zc
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

        # ------------------------------------------------------------------
        # Lifecycle
        # ------------------------------------------------------------------

        async def start(self, async_event_cb) -> None:
            """Register the event callback and start the mDNS service browser.

            The browser is event-driven; no polling loop is started here.
            Plugs already present on the network will trigger add_service
            callbacks shortly after the browser starts.
            """
            if self._browser is not None:
                if self._logger:
                    self._logger.warning("start() called while already running — ignoring")
                return

            self._event_cb = async_event_cb
            self._start_expiry_timer()

            if self._zc_instance is None:
                self._zc_instance = _zc.Zeroconf()

            loop = asyncio.get_running_loop()
            self._listener = _Listener(self, loop)
            self._browser = _zc.ServiceBrowser(
                self._zc_instance, self._service_type, self._listener
            )

        async def stop(self) -> None:
            """Stop browsing, cancel pending removals, and disconnect all plugs."""
            for handle in list(self._pending_removals.values()):
                handle.cancel()
            self._pending_removals.clear()

            if self._browser is not None:
                self._browser.cancel()
                self._browser = None

            self._listener = None

            if self._zc_owned and self._zc_instance is not None:
                self._zc_instance.close()
                self._zc_instance = None

            await super().stop()

        # ------------------------------------------------------------------
        # Public discovery seam — may also be called directly
        # ------------------------------------------------------------------

        def add_plug(self, mac: str, ip: str, port: int) -> None:
            """Notify that a plug is present at the given address.

            Creates or reconnects the PlugApi for this plug.  Safe to call
            directly without a zeroconf browser (e.g. from tests, or from HA's
            own mDNS handler).  Cancels any pending debounced removal for this MAC.

            Must be called from the event loop thread.
            """
            self._cancel_pending_removal(mac, source='add_plug')
            asyncio.get_running_loop().create_task(
                self._plug_discovered(mac, ip, port)
            )

        def remove_plug(self, mac: str) -> None:
            """Schedule a debounced removal for the given plug.

            After ``debounce_timeout`` seconds with no re-announcement, the plug
            API is disconnected and a ``device_lost`` event is emitted.

            Must be called from the event loop thread.
            """
            self._schedule_removal(mac)

        # ------------------------------------------------------------------
        # Debounce helpers (event-loop side only)
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
            if self._logger:
                self._logger.debug("Scheduled removal for %s in %.0f s", mac, self._debounce_seconds)

        def _on_debounce_expired(self, mac: str) -> None:
            """Called by the event loop when the debounce timer fires."""
            self._pending_removals.pop(mac, None)
            if self._logger:
                self._logger.info("Plug %s still absent after debounce — removing", mac)
            asyncio.get_running_loop().create_task(self._plug_lost(mac))

        def _cancel_pending_removal(self, mac: str, source: str) -> None:
            handle = self._pending_removals.pop(mac, None)
            if handle:
                handle.cancel()
                if self._logger:
                    self._logger.debug("Cancelled pending removal for %s (%s)", mac, source)

        # ------------------------------------------------------------------
        # Called from _Listener (zeroconf thread → event loop via stored loop ref)
        # ------------------------------------------------------------------

        def _on_zc_add(self, mac: str, ip: str, port: int, loop: asyncio.AbstractEventLoop) -> None:
            loop.call_soon_threadsafe(self._cancel_pending_removal, mac, 'zeroconf add')
            loop.call_soon_threadsafe(
                lambda: loop.create_task(self._plug_discovered(mac, ip, port))
            )

        def _on_zc_update(self, mac: str, ip: str, port: int, loop: asyncio.AbstractEventLoop) -> None:
            loop.call_soon_threadsafe(self._cancel_pending_removal, mac, 'zeroconf update')
            loop.call_soon_threadsafe(
                lambda: loop.create_task(self._plug_discovered(mac, ip, port))
            )

        def _on_zc_remove(self, mac: str, loop: asyncio.AbstractEventLoop) -> None:
            loop.call_soon_threadsafe(self._schedule_removal, mac)


    class _Listener(_zc.ServiceListener):
        """Zeroconf ServiceListener that forwards events to PowersensorZeroconfDevices.

        Internal implementation detail.  All ServiceListener callbacks arrive on
        the zeroconf event loop (>= 0.32) or background thread (< 0.32 / 1.0.0).

        Thread safety
        -------------
        ``_name_to_mac`` is populated in ``add_service`` / ``update_service`` and
        consumed in ``remove_service``.  In both threading models all three
        callbacks arrive on the same thread/loop, so no locking is required.

        The stored ``_loop`` reference is captured once at construction from the
        running asyncio event loop, and is used (read-only) from the callback
        context to schedule work back onto that loop via ``call_soon_threadsafe``.
        """

        def __init__(self, owner: PowersensorZeroconfDevices, loop: asyncio.AbstractEventLoop) -> None:
            self._owner = owner
            self._loop = loop
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
                if self._owner._logger:
                    self._owner._logger.warning(
                        "No cache entry for %s — device will appear on next mDNS announcement",
                        name,
                    )
                return None

            addresses = info.parsed_addresses()
            if not addresses:
                if self._owner._logger:
                    self._owner._logger.warning("No addresses in zeroconf cache record for %s", name)
                return None

            try:
                raw_id = info.properties[b'id']
            except KeyError:
                if self._owner._logger:
                    self._owner._logger.error("Missing 'id' property in zeroconf record for %s", name)
                return None

            if raw_id is None:
                if self._owner._logger:
                    self._owner._logger.error("'id' property in zeroconf record for %s has no value", name)
                return None

            if info.port is None:
                if self._owner._logger:
                    self._owner._logger.error("No port in zeroconf record for %s", name)
                return None

            return raw_id.decode('utf-8'), addresses[0], info.port

        def add_service(self, zc: Any, type_: str, name: str) -> None:
            result = self._extract(zc, type_, name)
            if result is None:
                if self._owner._logger:
                    self._owner._logger.warning(
                        "add_service: no info available for %s — will retry on next announcement",
                        name,
                    )
                return
            mac, ip, port = result
            self._name_to_mac[name] = mac
            self._owner._on_zc_add(mac, ip, port, self._loop)

        def update_service(self, zc: Any, type_: str, name: str) -> None:
            result = self._extract(zc, type_, name)
            if result is None:
                if self._owner._logger:
                    self._owner._logger.warning(
                        "update_service: no info available for %s — will retry on next announcement",
                        name,
                    )
                return
            mac, ip, port = result
            self._name_to_mac[name] = mac
            self._owner._on_zc_update(mac, ip, port, self._loop)

        def remove_service(self, zc: Any, type_: str, name: str) -> None:
            mac = self._name_to_mac.pop(name, None)
            if mac is None:
                if self._owner._logger:
                    self._owner._logger.warning(
                        "remove_service for %s: MAC not in cache — removal ignored", name
                    )
                return
            self._owner._on_zc_remove(mac, self._loop)

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
