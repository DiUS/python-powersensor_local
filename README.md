# Powersensor (local)

A small package to interface with the network-local event streams available on
Powersensor devices. Specifically, this package abstracts away the connections
to all Powersensor gateway devices (plugs) on the network, and provides a
uniform event stream from all devices (including sensors relaying their data
via the gateways).

The main API is in `powersensor_local.devices' via the PowersensorDevices
class, which provides an abstracted view of the discovered Powersensor devices
on the local network.

There are also two small utilities included, `ps-events` and `ps-rawfirehose`.
The former is effectively a consumer of the the PowersensorDevices event
stream which dumps all events to standard out. The latter, `ps-rawfirehose`
is a debugging aid which dumps the lower-level event streams from each
Powersensor gateway.
