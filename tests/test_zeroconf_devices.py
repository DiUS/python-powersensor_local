import asyncio
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from powersensor_local import zeroconf_devices as zd
from powersensor_local.zeroconf_devices import PowersensorZeroconfDevices

TYPE = '_powersensor._udp.local.'
NAME = f'Powersensor-gateway-aabbccddeeff-civet.{TYPE}'


def fake_service_info(cached: bool, answers: bool) -> type[Any]:
  """A stand-in for AsyncServiceInfo with a controllable cache and plug response."""

  class FakeServiceInfo:
    requested = False

    def __init__(self, type_: str, name: str) -> None:
      self.port = 49476
      self.properties: dict[bytes, bytes] = {b'id': b'aabbccddeeff'}

    def load_from_cache(self, zc: Any) -> bool:
      return cached

    async def async_request(self, zc: Any, timeout: float) -> bool:
      FakeServiceInfo.requested = True
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
    await asyncio.gather(*list(devices._internal_callbacks))


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
