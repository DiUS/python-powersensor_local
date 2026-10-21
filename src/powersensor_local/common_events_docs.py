class CommonEventsDocs:
    """
    The following is a list of common events that may be emitted.

    The first few are discovery events, while the rest are data events.

    **device_found**
        A device has been discovered or re-discovered.

        Note that due to device hardware limitations, role information is NOT
        reliably available at this time, and therefore not included in this
        message. There are situations where role information will never become
        available, and therefore the API can make no promises otherwise. If a
        user requires role information, they must manage that themselves and
        also provide a mechanism for handling the situation of a device not
        being able to provide role information in the first place. If a device
        does supply a role at any point, it should be considered authoritative
        and override any user provided value. The event data comprises:

        - "event": "device_found"
        - "mac": The MAC address of the device.
        - "device_type": One of "plug" or "sensor".

    **device_lost**
        A device has definitively disappeared (plug), or been inactive long
        enough to expire (plug or sensor). An expired device that becomes
        active again is announced with a new device_found. The event data
        comprises:

        - "event": "device_lost"
        - "mac": The MAC address of the device.

    **average_power**
        An event denoting the average power seen over a short duration, such
        as 1 or 30 seconds typically. Both plugs and powersensors may originate
        these. The event data comprises:

        - "event": "average_power"
        - "mac": The MAC address of the device.
        - "role": The assigned role of the device, if known.
        - "via": The id of the relaying plug, if from a sensor.
        - "starttime_utc": Seconds since the Unix Epoch, in UTC.
        - "duration_s": The number of seconds the reading is calculated over.
        - "watts": The average power, in Watts. May be negative for e.g.
          solar sensors and house sensors when exporting solar to the grid.

    **average_power_components**
        An plug-only event providing additional information on the power
        components feeding into the power measurement. To be read in
        conjunction with the "average_power" message with the same
        starttime_utc value. Comprises:

        - "event": "average_power_components"
        - "mac": The MAC address of the device.
        - "role": The assigned role of the device, if known.
        - "starttime_utc": Seconds since the Unix Epoch, in UTC.
        - "apparent_current": The apparent current, in Amperes.
        - "active_current": The active current component, in Amperes.
        - "reactive_current": The reactive current component, in Amperes.
        - "volts": The mains voltage as seen by the plug, in Volts.

    **summation_energy**
        An event reporting an energy summation value. Issued for both plugs
        and sensors. Comprises:

        - "event": "summation_energy"
        - "mac": The MAC address of the device.
        - "role": The assigned role of the device, if known.
        - "via": The id of the relaying plug, if from a sensor.
        - "starttime_utc": Seconds since the Unix Epoch, in UTC.
        - "summation_joules": The summation value, in Joules (Watt seconds).
          This value may go backwards (and even become negative) if solar
          export is present. The summation may increment or decrement
          depending on whether energy is being imported from or exported
          to the grid.
        - "summation_resettime_utc": A timestamp denoting the last time the
          summation value reset. Summation values from before the reset time
          can not be safely compared or diffed with ones from after the reset
          time. The format is the same as for "starttime_utc" — seconds since
          the Unix Epoch, in UTC.

    **average_flow**
        An event denoting the average flow rate seen over a short duration,
        such as 1 or 30 seconds typically. Only originated by water sensors.
        The event data comprises:

        - "event": "average_flow"
        - "mac": The MAC address of the device.
        - "role": The assigned role of the device, if known.
        - "via": The id of the relaying plug.
        - "starttime_utc": Seconds since the Unix Epoch, in UTC.
        - "duration_s": The number of seconds the reading is calculated over.
        - "litres_per_minute": The average flow detected, in litres/min..

    **summation_volume**
        An event reporting a volume summation value. Issued only for water
        sensors. Comprises:

        - "event": "summation_volume"
        - "mac": The MAC address of the device.
        - "role": The assigned role of the device, if known.
        - "via": The id of the relaying plug.
        - "starttime_utc": Seconds since the Unix Epoch, in UTC.
        - "summation_litres": The summation value, in litres.
        - "summation_resettime_utc": A timestamp denoting the last time the
          summation value reset. Summation values from before the reset time
          can not be safely compared or diffed with ones from after the reset
          time. The format is the same as for "starttime_utc" — seconds since
          the Unix Epoch, in UTC.

    **uncalibrated_average_reading**
        An event denoting an reading with unknown unit, for an average over a
        short duration, such as 1 or 30 seconds typically. Issued by
        powersensors, prior to calibration. The event data comprises:

        - "event": "uncalibrated_average_reading"
        - "mac": The MAC address of the device.
        - "role": The assigned role of the device, if known.
        - "via": The id of the relaying plug.
        - "starttime_utc": Seconds since the Unix Epoch, in UTC.
        - "duration_s": The number of seconds the reading is calculated over.
        - "value": The value, in unspecified units. The only valid thing
          to use this value for is display it relative to other uncalibrated
          values from the same device. The magnitude of the value is an
          indication of the strength of the signal seen by the sensor, but
          the unit is most definitely NOT in Watts. For most purposes, this
          event can (and should be) ignored. Once the backend has successfully
          calibrated the sensor against one or more plugs, these events
          will be replaced by "average_power" events instead.

    **battery_level**
        An event reporting the battery level of a sensor. The event data
        comprises:

        - "event": "battery_level"
        - "mac": The MAC address of the device.
        - "role": The assigned role of the device, if known.
        - "via": The id of the relaying plug.
        - "starttime_utc": Seconds since the Unix Epoch, in UTC.
        - "volts": The current battery level, in Volts. Sensors operate
          on 3.7V nominally, with a fully charged battery at around 4.2V.
          Precise battery curves vary individually. It is intentional that
          we do not attempt to map these to a percentage value here, as
          between individual differences and environmental conditions they
          are bound to be inaccurate. Short of characterising each battery
          in its environment, any such mapping will be inaccurate. It can
          be argued that users wishing a simple percentage display are best
          off using a simple linear extrapolation across the middle part of
          the curve, e.g. 3.3V and 4.15V. It's not entirely accurate, but
          it's also not useless.

    **radio_signal_quality**
        An event reporting radio signal quality for a sensor. Note that this
        is for the long-range radio comms with the plug, not for the WiFi
        signal. The event comprises:

        - "event": "radio_signal_quality"
        - "mac": The MAC address of the device.
        - "role": The assigned role of the device, if known.
        - "via": The id of the relaying plug.
        - "starttime_utc": Seconds since the Unix Epoch, in UTC.
        - "duration_s": The number of seconds the reading is calculated over.
        - "average_rssi": The average of the RSSI in messages received
          during the reporting window. Values below -90 are considered poor
          reception.
        - "last_rssi": The most recent RSSI value.
    """
    pass
