import asyncio
import signal
from abc import ABC, abstractmethod

class AbstractEventHandler(ABC):
    exiting: bool = False
    @abstractmethod
    async def on_exit(self):
        pass

    async def _do_exit(self):
        await self.on_exit()
        self.exiting = True

    @abstractmethod
    async def main(self):
        pass

    # Signal handler for Ctrl+C
    def register_sigint_handler(self):
        signal.signal(signal.SIGINT, self.__handle_sigint)

    def __handle_sigint(self, signum, frame):
        print(f"\nReceived signal: {signum}")
        print(f"Signal name: {signal.Signals(signum).name}")
        print(f"Interrupted at: {frame.f_code.co_filename}:{frame.f_lineno}")
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        asyncio.create_task(self._do_exit())

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.run(self.main())
        loop.stop()

    async def wait(self, seconds=1):
        # Keep the event loop running until Ctrl+C is pressed
        while not self.exiting:
            await asyncio.sleep(seconds)
