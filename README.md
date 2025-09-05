# Powersensor (local)

A small package to interface with the network-local event streams available on
Powersensor devices.

Two different interfaces are provided. The first is suitable for using when
relying on the legacy plug discovery method. It abstracts away the connections
to all Powersensor gateway devices (plugs) on the network, and provides a
uniform event stream from all devices (including sensors relaying their data
via the gateways).

The main API is in `powersensor_local.devices' via the PowersensorDevices
class, which provides an abstracted view of the discovered Powersensor devices
on the local network.

The second interface is intended for use when mDNS based service discovery,
also known as ZeroConf, is used. This abstraction provides an instantiation
for each plug as they get discovered, with individual async events provided.
Actual mDNS discovery is not included.

There are also some small utilities included, `ps-events` and `ps-rawfirehose`
showcasing the use of the first interface approach, and `ps-plugevents` and
`ps-rawplug` for the latter.
.
The `ps-events` is effectively a consumer of the the PowersensorDevices event
stream which dumps all events to standard out, while, `ps-rawfirehose`
is a debugging aid which dumps the lower-level event streams from each
Powersensor gateway. Similary, `ps-plugevents` shows the event stream from
a single plug (plus whatever it might be relaying for), and `ps-rawplug`
shows the raw event stream from the plug.
