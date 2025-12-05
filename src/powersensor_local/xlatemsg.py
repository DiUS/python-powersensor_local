"""Common message translation support."""
_MAC_TS_ROLE = [
  ('mac', 'mac', True),
  ('role', 'role', False),
  ('starttime', 'starttime_utc', True, 3),
]


# pylint: disable=R0913,R0917
def _pick_item(out: dict, message: dict, key: str, dstkey: str, req: bool, decis: int = None):
    val = message.get(key)
    if val is not None:
        if isinstance(val, float) and decis is not None:
            val = round(val, decis)
        out[dstkey] = val
    elif req:
        raise KeyError(f"Expected key '{key}' not found")
    return out

def _pick_list(out: dict, message: dict, items: list):
    for tup in items:
        _pick_item(out, message, *tup)
    return out

def _make_average_power_event(message: dict):
    ev = {}
    _pick_list(ev, message, _MAC_TS_ROLE)
    _pick_list(ev, message, [
        ('power', 'watts', True, 0),
        ('duration', 'duration_s', True, 3),
    ])
    return ev

def _make_average_power_components_event(message: dict):
    ev = {}
    _pick_list(ev, message, _MAC_TS_ROLE)
    _pick_list(ev, message, [
        ('current', 'apparent_current', True, 3),
        ('active_current', 'active_current', True, 3),
        ('reactive_current', 'reactive_current', True, 3),
        ('voltage', 'volts', True, 3),
    ])
    return ev

def _make_summation_energy_event(message: dict):
    ev = {}
    _pick_list(ev, message, _MAC_TS_ROLE)
    _pick_list(ev, message, [
        ('summation', 'summation_joules', True, 0),
        ('summation_start', 'summation_resettime_utc', True, 0),
    ])
    return ev

def _make_average_flow_event(message: dict):
    ev = {}
    _pick_list(ev, message, _MAC_TS_ROLE)
    _pick_list(ev, message, [
        ('duration', 'duration_s', True, 3),
    ])
    # report is in cl/min
    ev['litres_per_minute'] = round(float(message['power'])/100.0, 3)
    return ev

def _make_summation_volume_event(message: dict):
    ev = {}
    _pick_list(ev, message, _MAC_TS_ROLE)
    _pick_list(ev, message, [
        ('summation', 'summation_litres', True, 3),
        ('summation_start', 'summation_resettime_utc', True, 0),
    ])
    return ev

def _make_uncalibrated_event(message: dict):
    ev = {}
    _pick_list(ev, message, _MAC_TS_ROLE)
    _pick_list(ev, message, [
        ('power', 'value', True, None),
        ('duration', 'duration_s', True, 3),
    ])
    return ev

def _make_battery_level_event(message: dict):
    ev = {}
    _pick_list(ev, message, _MAC_TS_ROLE)
    ev['volts'] = round(float(message['batteryMicrovolt'])/1000000.0, 6)
    return ev

def _make_rssi_event(message: dict):
    ev = {}
    _pick_list(ev, message, _MAC_TS_ROLE)
    _pick_list(ev, message, [
        ('duration', 'duration_s', True, 3),
        ('rssi', 'average_rssi', True, 1),
        ('raw_rssi', 'last_rssi', True, 0),
    ])
    return ev

def _maybe_make_instant_power_events(out: dict, message: dict, dev: str):
    unit = message.get('unit')
    if unit in ('W', 'w'):
        out['average_power'] = _make_average_power_event(message)
        try:
            out['summation_energy'] = _make_summation_energy_event(message)
        except KeyError:
            pass # Old firmware doesn't provide the necessary summation_start
        if dev == 'plug':
            out['average_power_components'] = \
                _make_average_power_components_event(message)
    elif unit in ('L', 'l'):
        out['average_flow'] = _make_average_flow_event(message)
        out['summation_volume'] = _make_summation_volume_event(message)
    elif unit == 'U':
        out['uncalibrated_average_reading'] = _make_uncalibrated_event(message)
    elif unit == 'I':
        pass # Invalid data/sample failed

    if dev == 'sensor':
        out['battery_level'] = _make_battery_level_event(message)
        out['radio_signal_quality'] = _make_rssi_event(message)

def translate_raw_message(message: dict, relay_mac: str):
    """
    Translates raw messages from the plug API into stable, documented events.

    Args:
      - message: The raw message (decoded into a dict)
      - relay_mac: The id (MAC address) of the plug the message was received
        through. When the message origin is not the plug, the events returned
        from this function will have "via": relay_mac added to denote what
        plug is acting as the relay for them.

    Returns:
      A dictionary of events, quite possibly empty. The key is the event
      name that the event should be emitted under, with the value being
      the event data itself (a dict).

    Possible events returned:
      - "average_power": An event denoting the average power seen over a
        short duration, such as 1 or 30 seconds typically. Both plugs and
        powersensors may originate these. The event data comprises:
          - "mac": The MAC address of the device.
          - "role": The assigned role of the device, if known.
          - "via": The id of the relaying plug, if from a sensor.
          - "starttime_utc": Seconds since the Unix Epoch, in UTC.
          - "duration_s": The number of seconds the reading is calculated over.
          - "watts": The average power, in Watts. May be negative for e.g.
            solar sensors and house sensors when exporing solar to the grid.

      - "average_power_components": An plug-only event providing additional
        information on the power components feeding into the power measurement.
        To be read in conjunction with the "average_power" message with the
        same starttime_utc value. Comprises:
          - "mac": The MAC address of the device.
          - "role": The assigned role of the device, if known.
          - "starttime_utc": Seconds since the Unix Epoch, in UTC.
          - "apparent_current": The apparent current, in Amperes.
          - "active_current": The active current component, in Amperes.
          - "reactive_current": The reactive current component, in Amperes.
          - "volts": The mains voltage as seen by the plug, in Volts.

      - "summation_energy": An event reporting an energy summation value.
        Issued for both plugs and sensors. Comprises:
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
            summation value (may have) reset. The initial value on a reset is
            NOT zero. Summation values from before the reset time can not be
            safely compared or diffed with ones from after the reset time.
            The format is the same as for "starttime_utc" — seconds since the
            Unix Epoch, in UTC.

      - "average_flow": An event denoting the average flow rate seen over a
        short duration, such as 1 or 30 seconds typically. Only originated by
        water sensors. The event data comprises:
          - "mac": The MAC address of the device.
          - "role": The assigned role of the device, if known.
          - "via": The id of the relaying plug.
          - "starttime_utc": Seconds since the Unix Epoch, in UTC.
          - "duration_s": The number of seconds the reading is calculated over.
          - "litres_per_minute": The average flow detected, in litres/min..

      - "summation_volume": An event reporting a volume summation value.
        Issued only for water sensors. Comprises:
          - "mac": The MAC address of the device.
          - "role": The assigned role of the device, if known.
          - "via": The id of the relaying plug.
          - "starttime_utc": Seconds since the Unix Epoch, in UTC.
          - "summation_litres": The summation value, in litres.
          - "summation_resettime_utc": A timestamp denoting the last time the
            summation value (may have) reset. The initial value on a reset is
            NOT zero. Summation values from before the reset time can not be
            safely compared or diffed with ones from after the reset time.
            The format is the same as for "starttime_utc" — seconds since the
            Unix Epoch, in UTC.

      - "uncalibrated_average_reading": An event denoting an reading with
        unknown unit, for an average over a short duration, such as 1 or 30
        seconds typically. Issued by powersensors, prior to calibration.
        The event data comprises:
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

      - "battery_level": An event reporting the battery level of a sensor.
        The event data comprises:
          - "mac": The MAC address of the device.
          - "role": The assigned role of the device, if known.
          - "via": The id of the relaying plug.
          - "starttime_utc": Seconds since the Unix Epoch, in UTC.
          - "volts": The current battery level, in Volts. Sensors operate
          on 3.7V nominally, with a fully charged battery at around 4.2V.
          Precise battery curves vary individually.

      - "radio_signal_quality": An event reporting radio signal quality for
        a sensor. Note that this is for the long-range radio comms with the
        plug, not for the WiFi signal. The event comprises:
          - "mac": The MAC address of the device.
          - "role": The assigned role of the device, if known.
          - "via": The id of the relaying plug.
          - "starttime_utc": Seconds since the Unix Epoch, in UTC.
          - "duration_s": The number of seconds the reading is calculated over.
          - "average_rrsi": The average of the RSSI in messages received
            during the reporting window. Values below -90 are considered poor
            reception.
          - "last_rssi": The most recent RSSI value.

    """
    evs = {}
    typ = message.get('type')
    dev = message.get('device') # plug/sensor/ble_sensor

    # Primary message type, overloaded like nothing 😅
    if typ == 'instant_power':
        _maybe_make_instant_power_events(evs, message, dev)
    # External auxiliary linked device
    elif typ == 'auxiliary':
        # dev:ble_sensor; subtype: instant, ble_sensor_list
        pass
    # Debugging related messages
    elif typ == 'raw_waveform':
        pass
    elif typ == 'adc':
        pass
    elif typ == 'ble_stats':
        pass
    # Installation process related messages
    elif typ == 'lrradio':
        # subtype: 'sensor_joined', 'sensor_paired', 'sensor_not_paired',
        #   sensor_creds_request
        pass
    elif typ == 'sensor':
        # subtype: wifi_join, install_data
        pass
    elif typ == 'plug_announce':
        pass

    if dev != 'plug':
        for ev in evs.values():
            ev['via'] = relay_mac

    return evs
