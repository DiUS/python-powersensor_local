"""Direct (non-cloud) interface to Powersensor devices

This package contains various abstractions for interacting with Powersensor
devices on the local network.

The recommended approach is to use mDNS to discover plugs via their service
"_powersensor._tcp.local", and then instantiate a PlugApi to obtain the event
stream from each plug.

A legacy abstraction is also provided via PowersensorDevices, which uses
an older way of discovering plugs.

Lower-level interfaces are available in the PlugListener and
PowersensorListener classed, though they are not recommended for general use.

Additionally a convience abstraction for translating some of the events into
a household view is available in VirtualHousehold.

Quick overview:
• PlugApi is the recommended API layer
• PlugListener is the lower-level abstraction used by PlugApi
• PowersensorDevices is the legacy main API layer
• PowersensorListener provides a (legacy) lower-level abstraction
• VirtualHousehold can be used to translate events into a household view

The 'plugevents' and 'rawplug' modules are helper utilities provided as
debug aids, which get installed under the names ps-plugevents and ps-rawplug
respectively. There are also the legacy 'events' and 'rawfirehose' debug aids
which get installed under the names ps-events and ps-rawfirehose respectively.
"""
__all__ = [ 'devices', 'listener', 'plug_api', 'plug_listener', 'virtual_household' ]
from .devices import PowersensorDevices
from .listener import PowersensorListener
from .plug_api import PlugApi
from .plug_listener import PlugListener
from .virtual_household import VirtualHousehold
