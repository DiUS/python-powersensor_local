"""
Mock Gateway Service for Home Assistant Integration Testing

This service creates a fake gateway that:
- Advertises itself via Zeroconf (_mydevice._udp.local.)
- Listens on UDP port 31415
- Manages multiple mock sensors that independently generate messages
- Provides a DatagramProtocol for easy extension
"""

import asyncio
import logging

from ElectricitySensor import ElectricitySensor
from MockPlug import MockPlug
from MockPlugUDPService import MockPlugUDPService


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point - demonstrates creating a gateway with multiple sensors"""

    # Create a collection of mock sensors
    sensors = [
        ElectricitySensor("mock0sensor1", role='house-net', update_interval=30.0),
    ]

    # Create gateway with sensors
    mac = "mock0plug123"
    gateway_id = f"Powersensor-gateway-{mac}-civet"
    gateway = MockPlugUDPService(
        gateway_id=gateway_id,
        port=49476,
        sensors=sensors,
        protocol_class=MockPlug,
        properties={
            "version": "1",
            "id": mac,
        }
    )

    await gateway.start()

    logger.info("=" * 60)
    logger.info("Mock Gateway is running!")
    logger.info(f"Gateway ID: {gateway.gateway_id}")
    logger.info(f"Sensors: {len(sensors)}")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)

    # Keep running until interrupted
    try:
        await asyncio.Event().wait()  # Wait forever
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await gateway.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service terminated")
