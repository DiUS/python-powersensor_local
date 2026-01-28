"""
This service creates a fake plug that:
- Advertises itself via Zeroconf on the domain specified in const.SERVICE_DOMAIN
- Manages multiple mock sensors that independently generate messages
"""

import asyncio
import logging

from ElectricitySensor import ElectricitySensor
from MockPlug import MockPlug
from MockPlugUDPService import MockPlugUDPService
from powersensor_local.mock.SolarSensor import SolarSensor
from powersensor_local.mock.WaterSensor import WaterSensor
from powersensor_local.mock.const import SENSOR_OFFSET_KEY
from powersensor_local.mock.get_network_offset import OffsetGetter
from powersensor_local.mock.random_mac import generate_random_mac

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    # optional block of code (it is a bit slow) but allows to match mock offsets to actual devices
    offset_getter = OffsetGetter()
    await offset_getter.async_collect_data(60)

    shared_state = {SENSOR_OFFSET_KEY : offset_getter.get_offset()}
    # if you want to toggle the offset off you can either create an empty dict for shared state or delete it from the arguments

    # Create a collection of mock sensors
    sensors = [
        # Examples of other sensor types
        # ElectricitySensor("mock0sensor1", role='house-net', update_interval=30.0, shared_state=shared_state),
        # SolarSensor("mock0sensor2", update_interval=30.0, shared_state=shared_state),
        # WaterSensor("mock0sensor3", update_interval=30.0, shared_state=shared_state),
        # ElectricitySensor("mock0sensor4", role='appliance', update_interval=30.0, shared_state=shared_state),

        ElectricitySensor("mock0sensor5", role='<unknown>', update_interval=30.0, shared_state=shared_state), # This is supposed to look like a sensor that's forgotten its role
        ElectricitySensor(generate_random_mac(), role='<unknown>', update_interval=30.0, shared_state=shared_state), # this generates a new semi-mac-like string...fights against HA's infinite memory
        ElectricitySensor(generate_random_mac(), role='unknown', update_interval=30.0, shared_state=shared_state),  # Should also trigger bug, but looks a little off in the reconfigure menu
        ElectricitySensor(generate_random_mac(), update_interval=30.0, shared_state=shared_state), # does not trigger bug as role is None
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
