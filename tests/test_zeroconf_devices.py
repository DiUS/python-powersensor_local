import asyncio
import logging
from typing import Any, NoReturn
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import zeroconf
from zeroconf.asyncio import AsyncServiceInfo

from powersensor_local import zeroconf_devices as zd
from powersensor_local.zeroconf_devices import PowersensorZeroconfDevices

TYPE = '_powersensor._udp.local.'
NAME = f'Powersensor-gateway-aabbccddeeff-civet.{TYPE}'

# The zeroconf instance is a MagicMock rather than a real Zeroconf.  _Listener
# only hands it to AsyncServiceInfo, which the tests replace, and the tests call
# the listener directly instead of starting a browser, so nothing reads it.  A
# real instance would also open multicast sockets on port 5353 and send queries
# onto the local network, making the tests slow and dependent on the host's
# network setup.


class FakeServiceInfo(AsyncServiceInfo):
  """An AsyncServiceInfo with a controllable cache and plug response.

  If gate is given, the plug only answers once the gate is set.  Keyword
  arguments override the plug's record, as passed to ServiceInfo.
  """

  def __init__(
    self, cached: bool, answers: bool, gate: asyncio.Event | None = None,
    **record: Any,
  ) -> None:
    super().__init__(TYPE, NAME, **{
      'port': 49476,
      'properties': {b'id': b'aabbccddeeff'},
      'parsed_addresses': ['192.0.2.10'],
      **record,
    })
    self.cached = cached
    self.answers = answers
    self.gate = gate
    self.requested = False
    self.requests = 0

  def load_from_cache(self, zc: zeroconf.Zeroconf, now: float | None = None) -> bool:
    return self.cached

  async def async_request(
    self, zc: zeroconf.Zeroconf, timeout: float, *args: Any, **kwargs: Any,
  ) -> bool:
    self.requested = True
    self.requests += 1
    if self.gate is not None:
      await self.gate.wait()
    return self.answers


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
  zc = MagicMock()
  devices = PowersensorZeroconfDevices(zeroconf_instance=zc)
  info = FakeServiceInfo(cached=True, answers=False)
  with patch.object(zd, 'AsyncServiceInfo', return_value=info), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add:
    zd._Listener(devices).add_service(zc, TYPE, NAME)
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
  zc = MagicMock()
  devices = PowersensorZeroconfDevices(zeroconf_instance=zc)
  info = FakeServiceInfo(cached=False, answers=True)
  with patch.object(zd, 'AsyncServiceInfo', return_value=info), \
       patch.object(devices, handler, AsyncMock()) as on_resolved:
    getattr(zd._Listener(devices), method)(zc, TYPE, NAME)
    await settle(devices)
  assert info.requested
  on_resolved.assert_awaited_once_with('aabbccddeeff', '192.0.2.10', 49476)


@pytest.mark.asyncio
async def test_unanswered_request_is_logged(caplog: pytest.LogCaptureFixture) -> None:
  zc = MagicMock()
  devices = PowersensorZeroconfDevices(
    zeroconf_instance=zc, logger=logging.getLogger('test'),
  )
  info = FakeServiceInfo(cached=False, answers=False)
  with caplog.at_level(logging.WARNING), \
       patch.object(zd, 'AsyncServiceInfo', return_value=info), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add:
    zd._Listener(devices).add_service(zc, TYPE, NAME)
    await settle(devices)
  on_add.assert_not_awaited()
  assert f'No response from {NAME}' in caplog.text


@pytest.mark.asyncio
async def test_removal_before_answer_cancels_lookup(caplog: pytest.LogCaptureFixture) -> None:
  zc = MagicMock()
  devices = PowersensorZeroconfDevices(
    zeroconf_instance=zc, logger=logging.getLogger('test'),
  )
  gate = asyncio.Event()
  info = FakeServiceInfo(cached=False, answers=True, gate=gate)
  with caplog.at_level(logging.WARNING), \
       patch.object(zd, 'AsyncServiceInfo', return_value=info), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add, \
       patch.object(devices, '_on_zc_remove', AsyncMock()) as on_remove:
    listener = zd._Listener(devices)
    listener.add_service(zc, TYPE, NAME)
    await let_run()
    listener.remove_service(zc, TYPE, NAME)
    gate.set()
    await settle(devices)
  # The plug was never dispatched, so there is nothing to remove either.
  on_add.assert_not_awaited()
  on_remove.assert_not_awaited()
  assert 'removal ignored' not in caplog.text


@pytest.mark.asyncio
async def test_one_lookup_per_plug_at_a_time() -> None:
  zc = MagicMock()
  devices = PowersensorZeroconfDevices(zeroconf_instance=zc)
  gate = asyncio.Event()
  info = FakeServiceInfo(cached=False, answers=True, gate=gate)
  with patch.object(zd, 'AsyncServiceInfo', return_value=info), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add, \
       patch.object(devices, '_on_zc_update', AsyncMock()) as on_update:
    listener = zd._Listener(devices)
    listener.add_service(zc, TYPE, NAME)
    await let_run()
    listener.update_service(zc, TYPE, NAME)
    gate.set()
    await settle(devices)
  assert info.requests == 1
  on_add.assert_awaited_once_with('aabbccddeeff', '192.0.2.10', 49476)
  on_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_removal_after_answer_is_debounced() -> None:
  zc = MagicMock()
  devices = PowersensorZeroconfDevices(zeroconf_instance=zc)
  info = FakeServiceInfo(cached=False, answers=True)
  with patch.object(zd, 'AsyncServiceInfo', return_value=info), \
       patch.object(devices, '_on_zc_add', AsyncMock()), \
       patch.object(devices, '_on_zc_remove', AsyncMock()) as on_remove:
    listener = zd._Listener(devices)
    listener.add_service(zc, TYPE, NAME)
    await settle(devices)
    listener.remove_service(zc, TYPE, NAME)
    await settle(devices)
  on_remove.assert_awaited_once_with('aabbccddeeff')


@pytest.mark.asyncio
@pytest.mark.parametrize('cached', [True, False], ids=['cached', 'requested'])
@pytest.mark.parametrize(
  ('record', 'message'),
  [
    ({'parsed_addresses': []}, 'No addresses in zeroconf record'),
    ({'properties': {}}, "Missing 'id' property"),
    ({'properties': {b'id': None}}, 'has no value'),
    ({'port': None}, 'No port in zeroconf record'),
    ({'properties': {b'id': b'\xff\xfe'}}, 'is not valid UTF-8'),
  ],
  ids=['no-addresses', 'no-id', 'id-without-value', 'no-port', 'non-utf8-id'],
)
async def test_invalid_record_is_ignored(
  cached: bool, record: dict[str, Any], message: str,
  caplog: pytest.LogCaptureFixture,
) -> None:
  zc = MagicMock()
  devices = PowersensorZeroconfDevices(
    zeroconf_instance=zc, logger=logging.getLogger('test'),
  )
  info = FakeServiceInfo(cached=cached, answers=True, **record)
  with caplog.at_level(logging.WARNING), \
       patch.object(zd, 'AsyncServiceInfo', return_value=info), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add:
    zd._Listener(devices).add_service(zc, TYPE, NAME)
    await settle(devices)
  on_add.assert_not_awaited()
  assert message in caplog.text


# Browser callbacks must never raise (see _Listener): zeroconf does not catch
# their exceptions, which would disrupt other listeners on a shared instance.

@pytest.mark.asyncio
async def test_malformed_service_name_is_ignored() -> None:
  # Stands in for AsyncServiceInfo rejecting a name.  The real constructor is
  # not used because, under coverage, zeroconf's compiled modules can raise a
  # copy of the exception class that is not zeroconf.BadTypeInNameException.
  def reject(type_: str, name: str) -> NoReturn:
    raise zeroconf.BadTypeInNameException

  zc = MagicMock()
  devices = PowersensorZeroconfDevices(zeroconf_instance=zc)
  with patch.object(zd, 'AsyncServiceInfo', reject), \
       patch.object(devices, '_on_zc_add', AsyncMock()) as on_add:
    zd._Listener(devices).add_service(zc, TYPE, NAME)
    await settle(devices)
  on_add.assert_not_awaited()
  assert not devices._internal_callbacks

