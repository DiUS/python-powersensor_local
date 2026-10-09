import pytest
from powersensor_local.async_event_emitter import AsyncEventEmitter
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def emitter() -> AsyncEventEmitter:
  return AsyncEventEmitter()

@pytest.mark.asyncio
async def test_basics(emitter: AsyncEventEmitter) -> None:
  mock = AsyncMock()
  # Ensure it calls it
  emitter.subscribe('test', mock)
  await emitter.emit('test')
  mock.assert_called_once()
  # Ensure it can call it again
  await emitter.emit('test')
  assert(mock.call_count == 2)
  # Ensure it doesn't get called after unsubscribe
  emitter.unsubscribe('test', mock)
  await emitter.emit('test')
  assert(mock.call_count == 2)


@pytest.mark.asyncio
async def test_empty_cov(emitter: AsyncEventEmitter) -> None:
  mock = AsyncMock()
  emitter.unsubscribe('test', mock)
  await emitter.emit('test')


@pytest.mark.asyncio
async def test_multiple_listeners(emitter: AsyncEventEmitter) -> None:
  mock1 = AsyncMock()
  mock2 = AsyncMock()
  emitter.subscribe('x', mock1)
  emitter.subscribe('x', mock2)
  await emitter.emit('x')
  mock1.assert_called_once()
  mock2.assert_called_once()


@pytest.mark.asyncio
async def test_different_events(emitter: AsyncEventEmitter) -> None:
  mock1 = AsyncMock()
  mock2 = AsyncMock()
  emitter.subscribe('x', mock1)
  emitter.subscribe('y', mock2)
  await emitter.emit('x')
  assert(mock1.call_count == 1)
  assert(mock2.call_count == 0)
  await emitter.emit('y')
  assert(mock1.call_count == 1)
  assert(mock2.call_count == 1)


@pytest.mark.asyncio
async def test_argument_passing(emitter: AsyncEventEmitter) -> None:
  mock = AsyncMock()
  emitter.subscribe('test', mock)
  await emitter.emit('test', 1, 'two', 3.01)
  mock.assert_called_with('test', 1, 'two', 3.01)


@pytest.mark.asyncio
async def test_exception_unhandled() -> None:
  logger = MagicMock()
  emitter = AsyncEventEmitter(logger)
  mock = AsyncMock()
  emitter.subscribe('e', mock)
  e = KeyError('oops')
  mock.side_effect = e
  await emitter.emit('e')
  mock.assert_called_once()
  logger.exception.assert_called_once_with("Logic error: exception escaped from callback: %s", e)
