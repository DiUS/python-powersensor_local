"""Common helper for small commandline utils."""
import asyncio
import signal
from abc import ABC, abstractmethod

class AbstractEventHandler(ABC):
    """Base class to handle signals and the asyncio loop.

    Subclasses must implement :py:meth:`on_exit` and :py:meth:`main`.  The
    ``run`` method starts an event loop, registers a SIGINT handler and
    executes the :py:meth:`main` coroutine.  The loop is stopped when a
    SIGINT is received and the :py:meth:`on_exit` coroutine has finished.
    """
    exiting: bool = False
    @abstractmethod
    async def on_exit(self):
        """Called when a SIGINT is received.

        Subclasses should override this method to perform any cleanup
        (e.g. closing connections, flushing buffers).  It is awaited before
        the handler sets :pyattr:`exiting` to ``True``.
        """

    async def _do_exit(self):
        """Internal helper that runs ``on_exit`` and marks the handler as
        exiting.  This coroutine is scheduled by :py:meth:`__handle_sigint`
        when a SIGINT signal arrives.
        """
        await self.on_exit()
        self.exiting = True

    @abstractmethod
    async def main(self):
        """Main coroutine to be executed by the event loop.

        Subclasses must implement this method.  It should contain the
        application's primary logic and can call :py:meth:`wait` to keep
        the loop alive until a SIGINT is received.
        """

    # Signal handler for Ctrl+C
    def register_sigint_handler(self):
        """Register the SIGINT (Ctrl‑C) handler.

        This method sets :py:meth:`__handle_sigint` as the callback for
        ``signal.SIGINT``.  It should be called before :py:meth:`run` if
        a custom handler is required.
        """
        signal.signal(signal.SIGINT, self.__handle_sigint)

    def __handle_sigint(self, signum, frame):
        """Internal SIGINT callback.

        Prints diagnostic information and schedules :py:meth:`_do_exit`
        as a task in the running event loop.  After the first SIGINT
        the default handler is restored to allow a second Ctrl‑C to
        terminate immediately.
        """
        print(f"\nReceived signal: {signum}")
        print(f"Signal name: {signal.Signals(signum).name}")
        print(f"Interrupted at: {frame.f_code.co_filename}:{frame.f_lineno}")
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        asyncio.create_task(self._do_exit())

    def run(self):
        """Start the event loop and execute :py:meth:`main`.

        A new event loop is created, the SIGINT handler is registered,
        and :py:meth:`main` is run with ``asyncio.run``.  The loop is
        stopped once the coroutine completes (normally or after a SIGINT).
        """
        loop = asyncio.new_event_loop()
        asyncio.run(self.main())
        loop.stop()

    async def wait(self, seconds=1):
        """Keep the event loop alive until a SIGINT is received.

        Parameters
        ----------
        seconds : int, optional
            Number of seconds to sleep between checks.  The default is
            ``1`` which balances responsiveness with CPU usage.

        This coroutine can be awaited by subclasses in their
        :py:meth:`main` implementation to block until the handler
        exits.
        """
        while not self.exiting:
            await asyncio.sleep(seconds)
