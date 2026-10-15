Usage
=====

Basic Usage
-----------

Here's a simple example of how to use powersensor_local:

.. code-block:: python

   import asyncio
   import logging
   import signal

   from powersensor_local import PowersensorZeroconfDevices, Event
   from types import FrameType

   # Exceptions escaping the callback handler can be logged
   logger = logging.getLogger(__name__)

   # Create a zeroconf-based devices view, with logging enabled
   devs = PowersensorZeroconfDevices(logger = logger)

   # Sentinel for exiting cleanly
   exiting = False

   # All events from (and pertaining to) Powersensor devices end up here
   async def handle_event(ev: Event) -> None:
       event = ev.get("event")
       mac = ev.get("mac")
       match event:
           case "device_found":
               print(f"Device found: {mac}")
               # Subscribe to events from this device
               devs.subscribe(str(mac))
           case "device_lost":
               print(f"Device disappeared: {mac}")
               # Unsubscription happens automatically
           case "average_power":
               print(f"Power ({mac}): {ev['watts']}")
           # other events...

   # Main sequence startup
   async def main() -> None:
       # Commence mDNS discovery
       await devs.start(handle_event)
       # Everything happen asynchronously, so wait until time to exit
       while not exiting:
           await asyncio.sleep(0.5)
       # Be nice and unsubscribe and disconnect on exit
       await devs.stop()

   # Signal handler to flag that it's time to exit
   def flag_exit(signum: int, frame: FrameType) -> None:
       global exiting
       exiting = True
       signal.signal(signal.SIGINT, signal.SIG_DFL)

   if __name__ == "__main__":
       # Register ^C handler for graceful exit
       signal.signal(signal.SIGINT, flag_exit)
       # Run the main with an event loop
       asyncio.run(main())

Further reading
---------------

Refer to the example utilities `zc_events.py`, `events.py`, `plugevents.py`,
and `rawplug.py` for additional usage examples.
