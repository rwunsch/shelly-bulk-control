import aiohttp
import asyncio
from typing import Dict, Any, Optional, List
from ..models.device import Device, DeviceGeneration

class ConfigManager:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Initialize the config manager"""
        self._session = aiohttp.ClientSession()

    async def stop(self):
        """Clean up resources"""
        if self._session:
            await self._session.close()

    async def get_device_settings(self, device: Device) -> Dict[str, Any]:
        """Get current settings from a device"""
        if not self._session:
            raise RuntimeError("ConfigManager not started")

        if device.generation == DeviceGeneration.GEN1:
            url = f"http://{device.ip_address}/settings"
        else:  # GEN2
            url = f"http://{device.ip_address}/rpc/Shelly.GetConfig"

        async with self._session.get(url) as response:
            response.raise_for_status()
            return await response.json()

    async def apply_settings(self, device: Device, settings: Dict[str, Any]) -> bool:
        """Apply settings to a device"""
        if not self._session:
            raise RuntimeError("ConfigManager not started")

        if device.generation == DeviceGeneration.GEN1:
            url = f"http://{device.ip_address}/settings"
            async with self._session.post(url, json=settings) as response:
                response.raise_for_status()
                return True
        else:  # GEN2
            url = f"http://{device.ip_address}/rpc/Shelly.SetConfig"
            async with self._session.post(url, json={"config": settings}) as response:
                response.raise_for_status()
                return True

    async def apply_bulk_settings(self, devices: List[Device], settings: Dict[str, Any]) -> Dict[str, bool]:
        """Apply settings to multiple devices in parallel"""
        tasks = [self.apply_settings(device, settings) for device in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            device.id: isinstance(result, bool) and result 
            for device, result in zip(devices, results)
        } 