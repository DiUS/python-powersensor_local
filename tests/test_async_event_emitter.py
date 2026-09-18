import pytest
from powersensor_local.async_event_emitter import AsyncEventEmitter
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def emitter():
  return AsyncEventEmitter()

@pytest.mark.asyncio
async def test_basics(emitter):
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
async def test_multiple_listeners(emitter):
  mock1 = AsyncMock()
  mock2 = AsyncMock()
  emitter.subscribe('x', mock1)
  emitter.subscribe('x', mock2)
  await emitter.emit('x')
  mock1.assert_called_once()
  mock2.assert_called_once()


@pytest.mark.asyncio
async def test_different_events(emitter):
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
async def test_argument_passing(emitter):
  mock = AsyncMock()
  emitter.subscribe('test', mock)
  await emitter.emit('test', 1, 'two', 3.01)
  mock.assert_called_with('test', 1, 'two', 3.01)


@pytest.mark.asyncio
async def test_exception_unhandled():
  logger = MagicMock()
  emitter = AsyncEventEmitter(logger)
  mock = AsyncMock()
  emitter.subscribe('e', mock)
  mock.side_effect = KeyError('oops')
  await emitter.emit('e')
  mock.assert_called_once()
  logger.exception.assert_called_once_with("Discarding unhandled exception: 'oops'")


@pytest.mark.asyncio
async def test_exception_handler(emitter):
  mock = AsyncMock()
  emitter.subscribe('e', mock)
  e = KeyError('oops')
  mock.side_effect = e
  mock_exc = AsyncMock()
  emitter.subscribe('exception', mock_exc)
  await emitter.emit('e')
  mock.assert_called_once()
  mock_exc.assert_called_once_with('exception', e)


@pytest.mark.asyncio
async def test_exception_handler_exception():
  logger = MagicMock()
  emitter = AsyncEventEmitter(logger)
  mock = AsyncMock()
  emitter.subscribe('e', mock)
  mock.side_effect = KeyError('oops')
  mock_exc = AsyncMock()
  emitter.subscribe('exception', mock_exc)
  mock_exc.side_effect = ValueError('doh')
  await emitter.emit('e')
  mock.assert_called_once()
  mock_exc.assert_called_once()
  logger.exception.assert_called_once_with("Exception handling callback raised an exception itself, discarding it: doh")


@pytest.mark.asyncio
async def test_multiple_exception_handlers():
  logger = MagicMock()
  emitter = AsyncEventEmitter(logger)
  trigger = AsyncMock()
  e = ValueError('overflow')
  trigger.side_effect = e
  emitter.subscribe('e', trigger)
  handlers = [ AsyncMock() for _ in range(5) ]
  for handler in handlers:
    emitter.subscribe('exception', handler)
  bad_handlers = handlers[1::2] # pick every other
  for handler in bad_handlers:
    handler.side_effect = e
  await emitter.emit('e')
  trigger.assert_called_once()
  for handler in handlers:
    handler.assert_called_once()
  assert(logger.exception.call_count == len(bad_handlers))
