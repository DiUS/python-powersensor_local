import asyncio
import json

from datetime import datetime, timezone

from .listener import PowersensorListener

EXPIRY_CHECK_INTERVAL_S = 30
EXPIRY_TIMEOUT_S = 5 * 60

class PowersensorDevices:
    """Abstraction interface for the unified event stream from all Powersensor 
    devices on the local network.
    """

    def __init__(self, bcast_addr='<broadcast>'):
        """Creates a fresh instance, without scanning for devices."""
        self._event_cb = None
        self._ps = PowersensorListener(bcast_addr)
        self._devices = dict()
        self._timer = None

    async def start(self, async_event_cb):
        """Registers the async event callback function and starts the scan
        of the local network to discover present devices. The callback is
        of the form

        async def yourcallback(event: dict)

        Known events:

        scan_complete:
            Indicates the discovery of Powersensor devices has completed.
            Emitted in response to start() and rescan() calls.
            The number of found gateways (plugs) is reported.

            { event: "scan_complete", gateway_count: N }

        device_found:
            A new device found on the network.
            The order found devices are announced is not fixed.

            { event: "device_found",
              device_type: "plug" or "sensor",
              mac: "...",
            }

            An optional field named "via" is present for sensor devices, and
            shows the MAC address of the gateway the sensor is communicating
            via.

        device_lost:
            A device appears to no longer be present on the network.

            { event: "device_lost", mac: "..." }



        The events below all have the following common fields:

            { mac: "...", starttime_utc: X }
            
            and where applicable, also:

            { via: "..." }

        For brevity's sake they are not shown in the examples below, other
        then simply as ...


        battery_level:
            The battery level of a sensor.

            { ...,  event: "battery_level", volts: X.Y }

        voltage:
            The mains voltage as detected by a plug.

            { ..., event: "voltage", volts: X.Y }

        average_power:
            Reports the average power observed over the reporting duration.
            May be negative for e.g. solar sensors and house sensors when
            exporting solar to the grid.

            The summation_joules field is a summation style register which
            reports accumulated energy. This field is only useful for
            calculating the delta of energy between two events. The counter
            will reset to zero if the device is restarted, and is technically
            subject to overflow, though that is unlikely to be reached.
            The summation may be negative if solar export is present. The
            summation may increment or decrement depending on whether energy
            is being imported from or exported to the grid.

            { ..., event: "average_power",
              watts: X.Y,
              durations_s: N.M,
              summation_joules: J.K,
            }

            For reports from plugs, the following fields will also be present:

            {
              ...,
              volts: X.Y,
              current: C.D,
              active_current: E.F,
              reactive_current: G.H,
            }

            The (apparent) current, active_current and reactive_current fields
            are all reported in a unit of Amperes.

        uncalibrated_power:
            Powersensors require calibrations of their readings before they
            are able to be converted into a proper power reading. This event
            is issued for sensor readings prior to such calibration completing.
            The reported value has no inherent meaning beyond being an
            indication of the strength of the signal seen by the sensor. It
            is most definitely NOT in Watts. For most purposes, this event
            can (and should be) ignored.

            { ..., event: "uncalibrated_power",
              value: Y.Z,
              durations_s: N.M,
            }

        The start function returns the number of found gateway plugs.
        Powersensor devices aren't found directly as they are typically not
        on the network, but are instead detected when they relay data through
        a plug via long-range radio.
        """
        self._event_cb = async_event_cb
        await self._on_scanned(await self._ps.scan())
        self._timer = self._Timer(EXPIRY_CHECK_INTERVAL_S, self._on_timer)
        return len(self._ips)

    async def rescan(self):
        """Performs a fresh scan of the network to discover added devices,
        or devices which have changed their IP address for some reason."""
        await self._on_scanned(await self._ps.scan())

    async def stop(self):
        """Stops the event streaming and disconnects from the devices.
        To restart the event streaming, call start() again."""
        await self._ps.unsubscribe()
        await self._ps.stop()
        self._event_cb = None
        if self._timer:
            self._timer.terminate()
            self._timer = None

    def subscribe(self, mac):
        """Subscribes to events from the device with the given MAC address."""
        device = self._devices.get(mac)
        if device:
            device.subscribed = True

    def unsubscribe(self, mac):
        """Unsubscribes from events from the given MAC address."""
        device = self._devices.get(mac)
        if device:
            device.subscribed = False

    async def _on_scanned(self, ips):
        self._ips = ips
        if self._event_cb:
            ev = {
                'event': 'scan_complete',
                'gateway_count': len(ips),
            }
            await self._event_cb(ev)

        await self._ps.subscribe(self._on_msg)

    async def _on_msg(self, obj):
        mac = obj.get('mac')
        if mac and not self._devices.get(mac):
            typ = obj.get('device')
            via = obj.get('via')
            await self._add_device(mac, typ, via)

        device = self._devices[mac]
        device.mark_active()

        if self._event_cb and device.subscribed:
            evs = self._mk_events(obj)
            if len(evs) > 0:
                for ev in evs:
                    await self._event_cb(ev)

    async def _on_timer(self):
        devices = list(self._devices.values())
        for device in devices:
            if device.has_expired():
                await self._remove_device(device.mac)

    async def _add_device(self, mac, typ, via):
        self._devices[mac] = self._Device(mac, typ, via)
        if self._event_cb:
            ev = {
                'event': 'device_found',
                'device_type': typ,
                'mac': mac,
            }
            if via:
                ev['via'] = via
            await self._event_cb(ev)

    async def _remove_device(self, mac):
        if self._devices.get(mac):
            self._devices.pop(mac)
            if self._event_cb:
                ev = {
                    'event': 'device_lost',
                    'mac': mac
                }
                await self._event_cb(ev)

   ### Event formatting ###

    def _mk_events(self, obj):
        evs = []
        typ = obj.get('type')
        if typ == 'instant_power':
            unit = obj.get('unit')
            if unit == 'w' or unit == 'W':
                evs.append(self._mk_average_power_event(obj))
            elif unit == 'l' or unit == 'L':
                evs.append(self.mk_average_water_event(obj))
                pass # TODO, cl/min?
            elif unit == 'U':
                evs.append(self._mk_uncalib_power_event(obj))
            elif unit == 'I':
                pass # invalid data / sample failed

            if obj.get('voltage') is not None:
                evs.append(self._mk_voltage_event(obj))

            if obj.get('batteryMicrovolt') is not None:
                evs.append(self._mk_battery_event(obj))
        else:
            print(obj)

        for ev in evs:
            ev['mac'] = obj.get('mac')
            if obj.get('starttime'):
                ev['starttime_utc'] = obj.get('starttime')
            if obj.get('via'):
                ev['via'] = obj.get('via')

        return evs

    def _mk_average_power_event(self, obj):
        ev = {
            'event': 'average_power',
            'watts': obj.get('power'),
            'duration_s': obj.get('duration'),
            'summation_joules': obj.get('summation'),
        }
        if obj.get('device') == 'plug':
            ev['volts'] = obj.get('voltage')
            ev['current'] = obj.get('current')
            ev['active_current'] = obj.get('active_current')
            ev['reactive_current'] = obj.get('reactive_current')
        return ev

    def _mk_uncalib_power_event(self, obj):
        ev = {
            'event': 'uncalibrated_power',
            'value': obj.get('power'),
            'duration_s': obj.get('duration'),
        }
        return ev

    def _mk_voltage_event(self, obj):
        return {
            'event': 'voltage',
            'volts': obj.get('voltage'),
        }

    def _mk_battery_event(self, obj):
        return {
            'event': 'battery_level',
            'volts': float(obj.get('batteryMicrovolt'))/1000000.0,
        }


    ### Supporting classes ###

    class _Device:
        def __init__(self, mac, typ, via):
            self.mac = mac
            self.type = typ
            self.via = via
            self.subscribed = False
            self._last_active = datetime.now(timezone.utc)

        def mark_active(self):
            self._last_active = datetime.now(timezone.utc)

        def has_expired(self):
            now = datetime.now(timezone.utc)
            delta = now - self._last_active
            return delta.total_seconds() > EXPIRY_TIMEOUT_S

    class _Timer:
        def __init__(self, interval_s, callback):
            self._terminate = False
            self._interval = interval_s
            self._callback = callback
            self._task = asyncio.create_task(self._run())

        def terminate(self):
            self._terminate = True
            self._task.cancel()

        async def _run(self):
            while not self._terminate:
                await asyncio.sleep(self._interval)
                await self._callback()
