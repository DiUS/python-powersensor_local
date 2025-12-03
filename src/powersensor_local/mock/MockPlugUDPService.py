import asyncio
import logging
import socket
from typing import Optional, List

from zeroconf import Zeroconf, ServiceInfo

from MockPlug import MockPlug
from MockSensor import MockSensor
from const import SERVICE_DOMAIN

logger = logging.getLogger(__name__)


class MockPlugUDPService:
    """
    Main service that manages zeroconf advertisement and UDP protocol.
    """

    def __init__(
        self,
        mac: str = "mock0plug123",
        gateway_id: str = "Powersensor-gateway-mock0plug123-civet",
        port: int = 49476,
        sensors: Optional[List[MockSensor]] = None,
        protocol_class: type = MockPlug,
        properties: Optional[dict] = None
    ):
        self.mac = mac
        self.gateway_id = gateway_id
        self.port = port
        self.sensors = sensors or []
        self.protocol_class = protocol_class
        self.properties = properties or {}

        self.zeroconf = None
        self.service_info = None
        self.transport = None
        self.protocol = None

    def _get_local_ip(self) -> str:
        """Get the local IP address"""
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    async def start(self):
        """Start the mock gateway service"""
        logger.info(f"Starting Mock Gateway Service: {self.gateway_id}")
        logger.info(f"Configured with {len(self.sensors)} sensors")

        # Start UDP server with sensors
        loop = asyncio.get_running_loop()
        self.transport, self.protocol = await loop.create_datagram_endpoint(
            lambda: self.protocol_class(self.mac,self.gateway_id, self.sensors),
            local_addr=('0.0.0.0', self.port)
        )

        # Set up Zeroconf advertisement
        await self._setup_zeroconf()

        logger.info(f"Mock Gateway {self.gateway_id} is now running and discoverable")

    async def _setup_zeroconf(self):
        """Set up zeroconf service advertisement (IPv4 only)"""
        local_ip = self._get_local_ip()

        # Prepare properties
        props = {
            'gateway_id': self.gateway_id,
            'version': '1.0',
            'sensor_count': str(len(self.sensors)),
            **self.properties
        }

        # Create service info
        service_name = f"{self.gateway_id}.{SERVICE_DOMAIN}"

        self.service_info = ServiceInfo(
            SERVICE_DOMAIN,
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=self.port,
            properties=props,
            server=f"{self.gateway_id}.local."
        )

        # Register service in a thread (zeroconf is blocking) - IPv4 only
        self.zeroconf = Zeroconf(interfaces=[local_ip])
        await asyncio.get_running_loop().run_in_executor(
            None,
            self.zeroconf.register_service,
            self.service_info
        )

        logger.info(f"Zeroconf service registered (IPv4): {service_name} at {local_ip}:{self.port}")

    async def stop(self):
        """Stop the mock gateway service"""
        logger.info(f"Stopping Mock Gateway {self.gateway_id}")

        # Stop protocol (cancels sensor tasks)
        if self.protocol:
            self.protocol.stop()

        # Unregister zeroconf with proper timeout
        if self.zeroconf and self.service_info:
            try:
                await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(
                        None,
                        self._unregister_zeroconf
                    ),
                    timeout=2.0
                )
            except asyncio.TimeoutError:
                logger.warning("Zeroconf unregister timed out")
            except Exception as e:
                logger.warning(f"Error unregistering zeroconf: {e}")

        # Close UDP transport
        if self.transport:
            self.transport.close()

        logger.info(f"Mock Gateway {self.gateway_id} stopped")

    def _unregister_zeroconf(self):
        """Synchronous helper to unregister zeroconf"""
        try:
            self.zeroconf.unregister_service(self.service_info)
            self.zeroconf.close()
        except Exception as e:
            logger.warning(f"Error in zeroconf cleanup: {e}")