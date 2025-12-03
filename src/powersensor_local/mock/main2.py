"""
Mock Gateway Service for Home Assistant Integration Testing

This service creates a fake gateway that:
- Advertises itself via Zeroconf (_mockersensor._udp.local.)
- Listens on UDP port 31415
- Manages multiple mock sensors that independently generate messages
- Provides a DatagramProtocol for easy extension
"""

import asyncio
import logging


from get_network_offset import OffsetGetter

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point - demonstrates creating a gateway with multiple sensors"""
    offset_getter = OffsetGetter()
    await offset_getter.async_collect_data(60)



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service terminated")
