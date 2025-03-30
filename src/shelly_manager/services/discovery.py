import asyncio
from typing import List
from log import logger

class DiscoveryService:
    async def discover_specific_devices(self, device_ids: List[str], scan_timeout: int = 5):
        """
        Discover specific devices by ID without scanning the entire network.
        
        Args:
            device_ids: List of device IDs to look for
            scan_timeout: Timeout in seconds for mDNS discovery
        """
        if not self.started:
            await self.start()

        # Normalize device IDs (remove colons, convert to uppercase)
        normalized_ids = [device_id.replace(":", "").upper() for device_id in device_ids]
        logger.info(f"Looking for specific devices: {', '.join(normalized_ids)}")
        
        # Only start mDNS discovery, without IP scanning
        if not self.mdns_browser:
            self._start_mdns_discovery()
            
        # Short wait to see if devices appear via mDNS
        logger.debug(f"Waiting for {scan_timeout} seconds for mDNS responses")
        await asyncio.sleep(scan_timeout)
        
        # Check if we found the devices
        found_devices = []
        for device_id in normalized_ids:
            if device_id in self.devices:
                found_devices.append(device_id)
                
        if found_devices:
            logger.info(f"Found {len(found_devices)} out of {len(normalized_ids)} requested devices: {', '.join(found_devices)}")
        else:
            logger.info(f"None of the requested devices found via mDNS")
            
        return [self.devices.get(device_id) for device_id in normalized_ids if device_id in self.devices] 