import asyncio
import logging
from typing import Any, NoReturn
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import zeroconf

from powersensor_local import zeroconf_devices as zd
from powersensor_local.zeroconf_devices import PowersensorZeroconfDevices

TYPE = '_powersensor._udp.local.'
NAME = f'Powersensor-gateway-aabbccddeeff-civet.{TYPE}'


def fake_service_info(
  cached: bool, answers: bool, id_: bytes = b'aabbccddeeff',
  gate: asyncio.Event | None = None,
) -> type[Any]:
  """A stand-in for AsyncServiceInfo with a controllable cache and plug response.

  If gate is given, the plug only answers once the gate is set.
  """

  class FakeServiceInfo:
    requested = False
    requests = 0

    def __init__(self, type_: str, name: str) -> None:
      self.port = 49476
      self.properties: dict[bytes, bytes] = {b'id': id_}

    def load_from_cache(self, zc: Any) -> bool:
      return cached

    async def async_request(self, zc: Any, timeout: float) -> bool:
      FakeServiceInfo.requested = True
      FakeServiceInfo.requests += 1
      if gate is not None:
        await gate.wait()
      return answers

    def parsed_addresses(self) -> list[str]:
      return ['192.0.2.10']

  return FakeServiceInfo


async def settle(devices: PowersensorZeroconfDevices) -> None:
  """Wait for the listener's internal tasks, including any they schedule."""
  for _ in range(10):
    await asyncio.sleep(0)
    if not devices._internal_callbacks:
      return
    await asyncio.gather(*list(devices._internal_callbacks), return_exceptions=True)


async def let_run() -> None:
  """Let scheduled tasks run up to their next wait, without waiting for them."""
  for _ in range(5):
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_add_service_uses_cached_records() -> None:
  devices = PowersensorZeroconfDevices(zeroconf_instance=MagicMock())
  info = fake_service_info(cached=True, answers=False)
  with patch.object(zd, 'AsyncServiceInfo', info), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add:
    zd._Listener(devices).add_service(MagicMock(), TYPE, NAME)
    await settle(devices)
  on_add.assert_awaited_once_with('aabbccddeeff', '192.0.2.10', 49476)
  assert not info.requested


@pytest.mark.asyncio
@pytest.mark.parametrize(
  ('method', 'handler'),
  [('add_service', '_on_zc_add'), ('update_service', '_on_zc_update')],
)
async def test_records_missing_from_cache_are_requested(method: str, handler: str) -> None:
  # A browser started on a shared zeroconf instance is seeded from cached PTR
  # records, whose SRV and A records may already have expired.
  devices = PowersensorZeroconfDevices(zeroconf_instance=MagicMock())
  info = fake_service_info(cached=False, answers=True)
  with patch.object(zd, 'AsyncServiceInfo', info), \
       patch.object(devices, handler, AsyncMock()) as on_resolved:
    getattr(zd._Listener(devices), method)(MagicMock(), TYPE, NAME)
    await settle(devices)
  assert info.requested
  on_resolved.assert_awaited_once_with('aabbccddeeff', '192.0.2.10', 49476)


@pytest.mark.asyncio
async def test_unanswered_request_is_logged(caplog: pytest.LogCaptureFixture) -> None:
  devices = PowersensorZeroconfDevices(
    zeroconf_instance=MagicMock(), logger=logging.getLogger('test'),
  )
  info = fake_service_info(cached=False, answers=False)
  with caplog.at_level(logging.WARNING), \
       patch.object(zd, 'AsyncServiceInfo', info), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add:
    zd._Listener(devices).add_service(MagicMock(), TYPE, NAME)
    await settle(devices)
  on_add.assert_not_awaited()
  assert f'No response from {NAME}' in caplog.text


@pytest.mark.asyncio
async def test_removal_before_answer_cancels_lookup(caplog: pytest.LogCaptureFixture) -> None:
  devices = PowersensorZeroconfDevices(
    zeroconf_instance=MagicMock(), logger=logging.getLogger('test'),
  )
  gate = asyncio.Event()
  info = fake_service_info(cached=False, answers=True, gate=gate)
  with caplog.at_level(logging.WARNING), \
       patch.object(zd, 'AsyncServiceInfo', info), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add, \
       patch.object(devices, '_on_zc_remove', AsyncMock()) as on_remove:
    listener = zd._Listener(devices)
    listener.add_service(MagicMock(), TYPE, NAME)
    await let_run()
    listener.remove_service(MagicMock(), TYPE, NAME)
    gate.set()
    await settle(devices)
  # The plug was never dispatched, so there is nothing to remove either.
  on_add.assert_not_awaited()
  on_remove.assert_not_awaited()
  assert 'removal ignored' not in caplog.text


@pytest.mark.asyncio
async def test_one_lookup_per_plug_at_a_time() -> None:
  devices = PowersensorZeroconfDevices(zeroconf_instance=MagicMock())
  gate = asyncio.Event()
  info = fake_service_info(cached=False, answers=True, gate=gate)
  with patch.object(zd, 'AsyncServiceInfo', info), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add, \
       patch.object(devices, '_on_zc_update', AsyncMock()) as on_update:
    listener = zd._Listener(devices)
    listener.add_service(MagicMock(), TYPE, NAME)
    await let_run()
    listener.update_service(MagicMock(), TYPE, NAME)
    gate.set()
    await settle(devices)
  assert info.requests == 1
  on_add.assert_awaited_once_with('aabbccddeeff', '192.0.2.10', 49476)
  on_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_removal_after_answer_is_debounced() -> None:
  devices = PowersensorZeroconfDevices(zeroconf_instance=MagicMock())
  info = fake_service_info(cached=False, answers=True)
  with patch.object(zd, 'AsyncServiceInfo', info), \
       patch.object(devices, '_on_zc_add', AsyncMock()), \
       patch.object(devices, '_on_zc_remove', AsyncMock()) as on_remove:
    listener = zd._Listener(devices)
    listener.add_service(MagicMock(), TYPE, NAME)
    await settle(devices)
    listener.remove_service(MagicMock(), TYPE, NAME)
    await settle(devices)
  on_remove.assert_awaited_once_with('aabbccddeeff')


# Browser callbacks must never raise (see _Listener): zeroconf does not catch
# their exceptions, which would disrupt other listeners on a shared instance.

@pytest.mark.asyncio
async def test_malformed_service_name_is_ignored() -> None:
  # Stands in for AsyncServiceInfo rejecting a name.  The real constructor is
  # not used because, under coverage, zeroconf's compiled modules can raise a
  # copy of the exception class that is not zeroconf.BadTypeInNameException.
  def reject(type_: str, name: str) -> NoReturn:
    raise zeroconf.BadTypeInNameException

  devices = PowersensorZeroconfDevices(zeroconf_instance=MagicMock())
  with patch.object(zd, 'AsyncServiceInfo', reject), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add:
    zd._Listener(devices).add_service(MagicMock(), TYPE, NAME)
    await settle(devices)
  on_add.assert_not_awaited()
  assert not devices._internal_callbacks


@pytest.mark.asyncio
async def test_non_utf8_id_is_ignored(caplog: pytest.LogCaptureFixture) -> None:
  devices = PowersensorZeroconfDevices(
    zeroconf_instance=MagicMock(), logger=logging.getLogger('test'),
  )
  info = fake_service_info(cached=True, answers=False, id_=b'\xff\xfe')
  with caplog.at_level(logging.ERROR), \
       patch.object(zd, 'AsyncServiceInfo', info), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add:
    zd._Listener(devices).add_service(MagicMock(), TYPE, NAME)
    await settle(devices)
  on_add.assert_not_awaited()
  assert 'is not valid UTF-8' in caplog.text

