import json
import pytest
from powersensor_local.xlatemsg import translate_raw_message

RELAY_MAC = '246f280487a4'

ROLE_HOUSENET = 'house-net'
ROLE_SOLAR = 'solar'
ROLE_WATER = 'water'

def test_raw_woh_sensor_msg():
    """Test normal whole-of-house message translation."""
    msg = json.loads('{"starttime": 1772164705, "raw_rssi": -91, "device": "sensor", "rssi": -89.0397534995969, "type": "instant_power", "summation_start": 1769972064, "batteryMicrovolt": 3803104, "mac": "bcddc247d1f5", "duration": 30, "role": "house-net", "power": 992, "unit": "w", "summation": -281230401}')
    res = translate_raw_message(msg, RELAY_MAC)

    average_power = {'mac': 'bcddc247d1f5', 'role': ROLE_HOUSENET, 'starttime_utc': 1772164705, 'watts': 992, 'duration_s': 30, 'via': RELAY_MAC}
    battery_level = {'mac': 'bcddc247d1f5', 'role': ROLE_HOUSENET, 'starttime_utc': 1772164705, 'volts': 3.803104, 'via': RELAY_MAC}
    radio_signal_quality = {'mac': 'bcddc247d1f5', 'role': ROLE_HOUSENET, 'starttime_utc': 1772164705, 'duration_s': 30, 'average_rssi': -89.0, 'last_rssi': -91, 'via': RELAY_MAC}
    summation_energy = {'mac': 'bcddc247d1f5', 'role': ROLE_HOUSENET, 'starttime_utc': 1772164705, 'summation_joules': -281230401, 'summation_resettime_utc': 1769972064, 'via': RELAY_MAC}

    assert(len(res) == 4)
    assert(res['average_power'] == average_power)
    assert(res['battery_level'] == battery_level)
    assert(res['radio_signal_quality'] == radio_signal_quality)
    assert(res['summation_energy'] == summation_energy)


def test_raw_woh_sensor_msg_no_summation_start():
    """Test legacy firmware without summation_start field."""
    msg = json.loads('{"starttime": 1772164705, "raw_rssi": -91, "device": "sensor", "rssi": -89.0397534995969, "type": "instant_power", "batteryMicrovolt": 3803104, "mac": "bcddc247d1f5", "duration": 30, "role": "house-net", "power": 992, "unit": "w", "summation": -281230401}')
    res = translate_raw_message(msg, RELAY_MAC)

    average_power = {'mac': 'bcddc247d1f5', 'role': ROLE_HOUSENET, 'starttime_utc': 1772164705, 'watts': 992, 'duration_s': 30, 'via': RELAY_MAC}
    battery_level = {'mac': 'bcddc247d1f5', 'role': ROLE_HOUSENET, 'starttime_utc': 1772164705, 'volts': 3.803104, 'via': RELAY_MAC}
    radio_signal_quality = {'mac': 'bcddc247d1f5', 'role': ROLE_HOUSENET, 'starttime_utc': 1772164705, 'duration_s': 30, 'average_rssi': -89.0, 'last_rssi': -91, 'via': RELAY_MAC}

    assert(len(res) == 3)
    assert(res['average_power'] == average_power)
    assert(res['battery_level'] == battery_level)
    assert(res['radio_signal_quality'] == radio_signal_quality)


def test_raw_woh_sensor_msg_malformed():
    """Verify reports with missing field raises an exception."""
    msg = json.loads('{"raw_rssi": -91, "device": "sensor", "rssi": -89.0397534995969, "type": "instant_power", "summation_start": 1769972064, "batteryMicrovolt": 3803104, "mac": "bcddc247d1f5", "duration": 30, "role": "house-net", "power": 992, "unit": "w", "summation": -281230401}')
    with pytest.raises(KeyError):
        translate_raw_message(msg, RELAY_MAC)


def test_raw_solar_sensor_msg():
    """Test regular solar sensor message translation."""
    msg = json.loads('{"starttime": 1772164915, "raw_rssi": -91, "device": "sensor", "rssi": -89.14350517179614, "type": "instant_power", "summation_start": 1770530454, "batteryMicrovolt": 4106208, "mac": "bcddc247d289", "duration": 30, "role": "solar", "power": -331, "unit": "w", "summation": -906357844}')
    res = translate_raw_message(msg, RELAY_MAC)

    average_power = {'mac': 'bcddc247d289', 'role': ROLE_SOLAR, 'starttime_utc': 1772164915, 'watts': -331, 'duration_s': 30, 'via': RELAY_MAC}
    battery_level = {'mac': 'bcddc247d289', 'role': ROLE_SOLAR, 'starttime_utc': 1772164915, 'volts': 4.106208, 'via': RELAY_MAC}
    radio_signal_quality = {'mac': 'bcddc247d289', 'role': ROLE_SOLAR, 'starttime_utc': 1772164915, 'duration_s': 30, 'average_rssi': -89.1, 'last_rssi': -91, 'via': RELAY_MAC}
    summation_energy = {'mac': 'bcddc247d289', 'role': ROLE_SOLAR, 'starttime_utc': 1772164915, 'summation_joules': -906357844, 'summation_resettime_utc': 1770530454, 'via': RELAY_MAC}

    assert(len(res) == 4)
    assert(res['average_power'] == average_power)
    assert(res['battery_level'] == battery_level)
    assert(res['radio_signal_quality'] == radio_signal_quality)
    assert(res['summation_energy'] == summation_energy)


def test_raw_solar_sensor_msg_uncalibrated():
    """Test uncalibrated solar sensor message translation."""
    msg = json.loads('{"starttime": 1772164915, "raw_rssi": -91, "device": "sensor", "rssi": -89.14350517179614, "type": "instant_power", "summation_start": 1770530454, "batteryMicrovolt": 4106208, "mac": "bcddc247d289", "duration": 30, "role": "solar", "power": -331, "unit": "U", "summation": -906357844}')
    res = translate_raw_message(msg, RELAY_MAC)

    battery_level = {'mac': 'bcddc247d289', 'role': 'solar', 'starttime_utc': 1772164915, 'volts': 4.106208, 'via': '246f280487a4'}
    radio_signal_quality = {'mac': 'bcddc247d289', 'role': 'solar', 'starttime_utc': 1772164915, 'duration_s': 30, 'average_rssi': -89.1, 'last_rssi': -91, 'via': '246f280487a4'}
    uncalibrated_average_reading = {'mac': 'bcddc247d289', 'role': 'solar', 'starttime_utc': 1772164915, 'value': -331, 'duration_s': 30, 'via': '246f280487a4'}

    assert(len(res) == 3)
    assert(res['battery_level'] == battery_level)
    assert(res['radio_signal_quality'] == radio_signal_quality)
    assert(res['uncalibrated_average_reading'] == uncalibrated_average_reading)


def test_raw_plug_power_msg():
    """Test regular plug message translation."""
    msg = json.loads('{"reactive_current": 0.006468, "type": "instant_power", "summation_start": 1770501947.113085, "count": 13, "duration": 1.039551, "role": "appliance", "power": 1.033781, "unit": "W", "device": "plug", "source": "BLE", "active_current": 0.004582, "mac": "246f280487a4", "voltage": 232.113508, "starttime": 1772164754.096228, "current": 0.14132, "borrowed_summation": 0.132574, "summation": 5103988.143331}')
    res = translate_raw_message(msg, RELAY_MAC)

    average_power = {'mac': '246f280487a4', 'role': 'appliance', 'starttime_utc': 1772164754.096, 'watts': 1.0, 'duration_s': 1.04}
    average_power_components = {'mac': '246f280487a4', 'role': 'appliance', 'starttime_utc': 1772164754.096, 'apparent_current': 0.141, 'active_current': 0.005, 'reactive_current': 0.006, 'volts': 232.114}
    summation_energy = {'mac': '246f280487a4', 'role': 'appliance', 'starttime_utc': 1772164754.096, 'summation_joules': 5103988.0, 'summation_resettime_utc': 1770501947.0}

    assert(len(res) == 3)
    assert(res['average_power'] == average_power)
    assert(res['average_power_components'] == average_power_components)
    assert(res['summation_energy'] == summation_energy)


def test_raw_sensor_invalid_sample_msg():
    """Test (rare) invalid sensor sample report."""
    msg = json.loads('{"starttime": 1772164705, "raw_rssi": -91, "device": "sensor", "rssi": -89.0397534995969, "type": "instant_power", "batteryMicrovolt": 3803104, "mac": "bcddc247d1f5", "duration": 30, "role": "house-net", "unit": "I"}')
    res = translate_raw_message(msg, RELAY_MAC)

    battery_level = {'mac': 'bcddc247d1f5', 'role': ROLE_HOUSENET, 'starttime_utc': 1772164705, 'volts': 3.803104, 'via': RELAY_MAC}
    radio_signal_quality = {'mac': 'bcddc247d1f5', 'role': ROLE_HOUSENET, 'starttime_utc': 1772164705, 'duration_s': 30, 'average_rssi': -89.0, 'last_rssi': -91, 'via': RELAY_MAC}

    assert(len(res) == 2)
    assert(res['battery_level'] == battery_level)
    assert(res['radio_signal_quality'] == radio_signal_quality)


def test_raw_water_sensor__msg():
    """Test regular water sensor message translation."""
    msg = json.loads('{"starttime": 1772164765, "raw_rssi": -89, "device": "sensor", "rssi": -87.03, "type": "instant_power", "summation_start": 1769972151, "batteryMicrovolt": 3612871, "mac": "bcddc247d338", "duration": 30, "role": "water", "power": 92, "unit": "L", "summation": 1321, "average_flow": 9.2, "summation_volume": 132.1}')
    res = translate_raw_message(msg, RELAY_MAC)

    average_flow = {'mac': 'bcddc247d338', 'role': ROLE_WATER, 'starttime_utc': 1772164765, 'litres_per_minute': 9.2, 'duration_s': 30, 'via': RELAY_MAC}
    battery_level = {'mac': 'bcddc247d338', 'role': ROLE_WATER, 'starttime_utc': 1772164765, 'volts': 3.612871, 'via': RELAY_MAC}
    radio_signal_quality = {'mac': 'bcddc247d338', 'role': ROLE_WATER, 'starttime_utc': 1772164765, 'duration_s': 30, 'average_rssi': -87.0, 'last_rssi': -89, 'via': RELAY_MAC}
    summation_volume = {'mac': 'bcddc247d338', 'role': ROLE_WATER, 'starttime_utc': 1772164765, 'summation_litres': 132.1, 'summation_resettime_utc': 1769972151, 'via': RELAY_MAC}

    assert(len(res) == 4)
    assert(res['average_flow'] == average_flow)
    assert(res['battery_level'] == battery_level)
    assert(res['radio_signal_quality'] == radio_signal_quality)
    assert(res['summation_volume'] == summation_volume)


def test_raw_water_sensor__msg_legacy():
    """Ensure old, unscaled water messages are suppressed cleanly."""
    msg = json.loads('{"starttime": 1772164765, "raw_rssi": -89, "device": "sensor", "rssi": -87.03, "type": "instant_power", "summation_start": 1769972151, "batteryMicrovolt": 3612871, "mac": "bcddc247d338", "duration": 30, "role": "water", "power": 92, "unit": "L", "summation": 1321}')
    res = translate_raw_message(msg, RELAY_MAC)

    battery_level = {'mac': 'bcddc247d338', 'role': ROLE_WATER, 'starttime_utc': 1772164765, 'volts': 3.612871, 'via': RELAY_MAC}
    radio_signal_quality = {'mac': 'bcddc247d338', 'role': ROLE_WATER, 'starttime_utc': 1772164765, 'duration_s': 30, 'average_rssi': -87.0, 'last_rssi': -89, 'via': RELAY_MAC}

    assert(len(res) == 2)
    assert(res['battery_level'] == battery_level)
    assert(res['radio_signal_quality'] == radio_signal_quality)


def test_unused_msg_auxiliary():
    """Test unused message type doesn't propagate."""
    msg = json.loads('{"starttime": 1772164705, "device": "plug", "type": "auxiliary", "mac": "bcddc247d1f5", "role": "appliance"}')
    res = translate_raw_message(msg, RELAY_MAC)
    assert(len(res) == 0)


def test_unused_msg_raw_waveform():
    """Test unused message type doesn't propagate."""
    msg = json.loads('{"starttime": 1772164705, "device": "plug", "type": "raw_waveform", "mac": "bcddc247d1f5", "role": "appliance"}')
    res = translate_raw_message(msg, RELAY_MAC)
    assert(len(res) == 0)


def test_unused_msg_adc():
    """Test unused message type doesn't propagate."""
    msg = json.loads('{"starttime": 1772164705, "device": "plug", "type": "adc", "mac": "bcddc247d1f5", "role": "appliance"}')
    res = translate_raw_message(msg, RELAY_MAC)
    assert(len(res) == 0)


def test_unused_msg_ble_stats():
    """Test unused message type doesn't propagate."""
    msg = json.loads('{"starttime": 1772164705, "device": "plug", "type": "ble_stats", "mac": "bcddc247d1f5", "role": "appliance"}')
    res = translate_raw_message(msg, RELAY_MAC)
    assert(len(res) == 0)


def test_unused_msg_sensor():
    """Test unused message type doesn't propagate."""
    msg = json.loads('{"starttime": 1772164705, "device": "plug", "type": "sensor", "mac": "bcddc247d1f5", "role": "appliance"}')
    res = translate_raw_message(msg, RELAY_MAC)
    assert(len(res) == 0)


def test_unused_msg_lrradio():
    """Test unused message type doesn't propagate."""
    msg = json.loads('{"starttime": 1772164705, "device": "plug", "type": "lrradio", "mac": "bcddc247d1f5", "role": "appliance"}')
    res = translate_raw_message(msg, RELAY_MAC)
    assert(len(res) == 0)


def test_unused_msg_plug_announce():
    """Test unused message type doesn't propagate."""
    msg = json.loads('{"starttime": 1772164705, "device": "plug", "type": "plug_announce", "mac": "bcddc247d1f5", "role": "appliance"}')
    res = translate_raw_message(msg, RELAY_MAC)
    assert(len(res) == 0)
