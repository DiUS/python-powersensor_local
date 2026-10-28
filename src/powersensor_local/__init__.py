"""Direct (non-cloud) interface to Powersensor devices.

This package contains various abstractions for interacting with Powersensor
devices on the local network.

The library provides two types of abstractions: per-plug event streams, and a
shared-across-all-devices event stream. Neither is "best", it depends on the
particular use case. Device discovery can be done in two ways. The preferred
way is via mDNS/Zeroconf. There is also a legacy method relying on a simpler,
custom, discovery protocol, but there should be no reason to use it for new
projects.

The simplest approach is to use the shared event stream, and do discovery via
Zeroconf. This is available out-of-the-box in the
:class:`PowersensorZeroconfDevices` class, which encapsulates the Zeroconf
machinations and merging of plug event streams.

A legacy abstraction is also provided via
:class:`PowersensorLegacyDevices`, which uses an older way of discovering plugs.
It is more fragile than Zeroconf, but may be slightly more responsive in
certain situations, as the user is fully in control over when to scan for
devices. In general it is not recommended for new use.

If wanting individual event streams from each plug, the :class:`PlugApi` class
is the one to use. Device discovery is left up to the user in this case.

The recommended approach is to use mDNS to discover plugs via their service
"_powersensor._udp.local" (or "_powersensor._tcp.local" for TCP transport), and
then instantiate a PlugApi to obtain the event stream from each plug. Note
that the plugs are only capable of handling a single TCP connection at a time,
so UDP is the preferred transport. Up to 5 concurrent subscriptions are
supported over UDP. Internally, the :class:`PlugApi` uses either
:class:`PlugListenerUdp` or :class:`PlugListenerTcp` for connecting to the
plugs. The interfaces are identical; switching between UDP and TCP should be
invisible to the user of the :class:`PlugApi`.

Additionally, a convenience abstraction for translating some of the events into
a household view is available in :class:`VirtualHousehold`.

Quick overview:
  - :class:`PowersensorZeroconfDevices` is the shared event stream abstraction with Zeroconf discovery.
  - :class:`PowersensorLegacyDevices` provides the legacy discovery mechanism together with a shared event stream.
  - :class:`PlugApi` is the recommended API layer for per-plug event streams.
  - :class:`PlugListenerUdp` is the UDP lower-level abstraction used by PlugApi.
  - :class:`PlugListenerTcp` is the TCP lower-level abstraction used by PlugApi.
  - :class:`VirtualHousehold` can be used to translate events into a household view.

The 'plugevents' and 'rawplug' modules are helper utilities provided as
debug aids, which get installed under the names ps-plugevents and ps-rawplug
respectively. There is also the legacy 'events' debug aid which get installed
nder the names ps-events, and offers up the events from PowersensorDevices.
Similarly, 'zc_events' offers up events from PowersensorZeroconfDevices,
installed as 'ps-zcevents', again, for debug use only.

Type hints for emitted data are available in :type:`Event`/:type:`Events`/:type:`Message`.
"""
__all__ = [
    'VirtualHousehold',
    'PlugApi',
    '__version__',
    'PlugListenerTcp',
    'PlugListenerUdp',
    'PowersensorDevices',
    'PowersensorLegacyDevices',
    'PowersensorZeroconfDevices',
    'AsyncEventCallback',
    'Event',
    'Events',
    'Message',
    'CommonEventsDocs',
]
__version__ = "2.4.1rc3"
from .devices import (
    AsyncEventCallback,
    PowersensorDevices,
    PowersensorLegacyDevices
)
from .legacy_discovery import LegacyDiscovery
from .plug_api import PlugApi
from .plug_listener_tcp import PlugListenerTcp
from .plug_listener_udp import PlugListenerUdp
from .virtual_household import VirtualHousehold
from .zeroconf_devices import PowersensorZeroconfDevices
from .xlatemsg import Event, Events, Message
from .common_events_docs import CommonEventsDocs
