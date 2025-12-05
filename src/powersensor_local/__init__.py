"""Direct (non-cloud) interface to Powersensor devices

This package contains various abstractions for interacting with Powersensor
devices on the local network.

The recommended approach is to use mDNS to discover plugs via their service
"_powersensor._udp.local" (or "_powersensor._tcp.local" for TCP transport), and
then instantiate a PlugApi to obtain the event stream from each plug. Note
that the plugs are only capable of handling a single TCP connection at a time,
so UDP is the preferred transport. Up to 5 concurrent subscriptions are
supported over UDP. The interfaces provided by PlugListenerUdp and
PlugListenerTCP are identical; switching between them should be trivial.

A legacy abstraction is also provided via PowersensorDevices, which uses
an older way of discovering plugs, and then funnels all the event streams
through a single callback.

Lower-level interfaces are available in the PlugListenerUdp and PlugListenerTcp
classes, though they are not recommended for general use.

Additionally, a convenience abstraction for translating some of the events into
a household view is available in VirtualHousehold.

Quick overview:
• PlugApi is the recommended API layer
• PlugListenerUdp is the UDP lower-level abstraction used by PlugApi
• PlugListenerTcp is the TCP lower-level abstraction used by PlugApi
• PowersensorDevices is the legacy main API layer
• LegacyDiscovery provides access to the legacy discovery mechanism
• VirtualHousehold can be used to translate events into a household view

The 'plugevents' and 'rawplug' modules are helper utilities provided as
debug aids, which get installed under the names ps-plugevents and ps-rawplug
respectively. There is also the legacy 'events' debug aid which get installed
nder the names ps-events, and offers up the events from PowersensorDevices.
"""
__all__ = [
    'VirtualHousehold',
    'PlugApi',
    '__version__',
    'PlugListenerTcp',
    'PlugListenerUdp'
]
__version__ = "2.1.0"
from .devices import PowersensorDevices
from .legacy_discovery import LegacyDiscovery
from .plug_api import PlugApi
from .plug_listener_tcp import PlugListenerTcp
from .plug_listener_udp import PlugListenerUdp
from .virtual_household import VirtualHousehold
