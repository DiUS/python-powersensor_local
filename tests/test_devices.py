from unittest.mock import MagicMock, patch

import pytest

from powersensor_local import devices as devices_module
from powersensor_local.plug_api import PlugApi
from powersensor_local.xlatemsg import Event
from powersensor_local.zeroconf_devices import PowersensorZeroconfDevices

PLUG = 'aabbccddeeff'
SENSOR = '112233445566'


async def with_plug(events: list[Event]) -> PowersensorZeroconfDevices:
  """Return devices with one plug discovered, recording every event.

  Like a typical caller, it subscribes to each device it is told about.
  """
  devices = PowersensorZeroconfDevices(zeroconf_instance=MagicMock())

  async def on_event(event: Event) -> None:
    events.append(dict(event))
    if event['event'] == 'device_found':
      devices.subscribe(str(event['mac']))

  devices._event_cb = on_event
  await devices._on_zc_add(PLUG, '192.0.2.10', 49476)
  return devices


async def expire_all(devices: PowersensorZeroconfDevices) -> None:
  """Run the expiry check as if every device had been silent too long."""
  with patch.object(devices_module, 'EXPIRY_TIMEOUT_S', -1):
    await devices._on_timer()


@pytest.mark.asyncio
async def test_expired_plug_is_announced_again_when_its_data_resumes() -> None:
  events: list[Event] = []
  with patch.object(PlugApi, 'connect'):
    devices = await with_plug(events)
    await expire_all(devices)
    # The plug keeps its PlugApi, so its data resuming is the only sign it is
    # back; discovery does not announce it again at an unchanged address.
    await devices._on_zc_update(PLUG, '192.0.2.10', 49476)
    await devices._reemit('average_power', {'mac': PLUG, 'watts': 5.0})
    await devices.stop()
  assert [(e['event'], e['mac']) for e in events] == [
    ('device_found', PLUG),
    ('device_lost', PLUG),
    ('device_found', PLUG),
    ('average_power', PLUG),
  ]


@pytest.mark.asyncio
async def test_data_for_an_unknown_device_is_not_announced() -> None:
  events: list[Event] = []
  with patch.object(PlugApi, 'connect'):
    devices = await with_plug(events)
    # A sensor is announced by now_relaying_for, not by its measurements.
    await devices._reemit('average_power', {'mac': SENSOR, 'watts': 5.0})
    await devices.stop()
  assert [(e['event'], e['mac']) for e in events] == [('device_found', PLUG)]
