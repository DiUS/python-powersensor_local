# Powersensor (local)

A small package to interface with the network-local event streams available on
Powersensor devices.

Two different high-level abstractions are provided. The first is the PlugApi,
which provides access to the event stream from a single Powersensor Plug. The
plug may be relaying data for sensors as well, which will also be included
in the said event stream. The PlugApi abstraction is ideal when used together
with Zeroconf/mDNS discovery (services '_powersensor._udp.local' and
'_powersensor._tcp.local'). Note that actual Zeroconf/mDNS discovery
functionality is not included here.

The second abstraction is the PowersensorDevices class, which uses the legacy
discovery mechanism (as opposed to mDNS) to discover the plugs, and then
aggregates all the event streams into a single callback. Internally it
relies on the PlugApi as well.

There are also some small utilities included,`ps-plugevents` and `ps-rawplug`
showcasing the use of the first interface approach, and `ps-events` the latter.
.
The `ps-events` is effectively a consumer of the the PowersensorDevices event
stream and dumps all events to standard out. Similary, `ps-plugevents` shows
the event stream from a single plug (plus whatever it might be relaying for),
and `ps-rawplug` shows the raw event stream from the plug. Note that the format
of the raw events is not guaranteed to be stable; only the interface provided
by PlugApi is.
