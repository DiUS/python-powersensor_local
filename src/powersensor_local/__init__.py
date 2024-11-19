"""Direct (non-cloud) interface to Powersensor devices

This package contains two abstraction layers:

• PowersensorDevices is the main API layer
• PowersensorListener provides a lower-level abstraction

These are both available within this namespace, or specifically as
devices.PowersensorDevices and listener.PowersensorListener

The 'events' and 'rawfirehose' modules are helper utilities provided as
debug aids, which get installed under the names ps-events and ps-rawfirehose
respectively.
"""
__all__ = [ 'devices', 'listener' ]
from .devices import PowersensorDevices
from .listener import PowersensorListener
