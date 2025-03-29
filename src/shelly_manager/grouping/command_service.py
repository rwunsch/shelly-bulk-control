"""
Group command service for performing operations on device groups.
"""
import asyncio
import aiohttp
import json
from typing import Dict, Any, List, Optional, Set
import logging
from pathlib import Path

from ..utils.logging import get_logger
from ..discovery.discovery_service import DiscoveryService
from ..models.device import Device, DeviceGeneration
from ..models.device_registry import device_registry
from .group_manager import GroupManager

# Get logger for this module
logger = get_logger(__name__)

class GroupCommandService:
    """
    Service for executing commands on groups of Shelly devices.
    
    This service allows commands such as turning devices on/off, toggling,
    and rebooting to be executed on all devices within a specified group.
    """
    
    def __init__(self, group_manager: GroupManager, discovery_service: Optional[DiscoveryService] = None):
        """
        Initialize the group command service.
        
        Args:
            group_manager: Manager for device groups
            discovery_service: Optional service for device discovery
        """
        self.group_manager = group_manager
        self.discovery_service = discovery_service
        self.session = None
        logger.debug("GroupCommandService initialized")
    
    async def start(self):
        """Start the command service."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            logger.debug("HTTP session initialized")
            
        # If discovery service is provided and not started, start it
        if self.discovery_service and not getattr(self.discovery_service, "started", False):
            await self.discovery_service.start()
            logger.debug("Discovery service started")
    
    async def stop(self):
        """Stop the command service."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.debug("HTTP session closed")
    
    def get_devices_for_group(self, group_name: str) -> List[Device]:
        """
        Get devices for a specific group.
        
        Args:
            group_name: Name of the group
            
        Returns:
            List of devices in the group
            
        Raises:
            ValueError: If the group does not exist
        """
        group = self.group_manager.get_group(group_name)
        if not group:
            logger.error(f"Group '{group_name}' not found")
            raise ValueError(f"Group '{group_name}' not found")
        
        devices = []
        if self.discovery_service:
            # If discovery service is available, use it to get device details
            all_devices = self.discovery_service.get_devices()
            for device_id in group.device_ids:
                if device_id in all_devices:
                    devices.append(all_devices[device_id])
        else:
            # Use the device registry to load devices from files
            logger.debug(f"Loading devices from registry for group '{group_name}'")
            devices = device_registry.get_devices(group.device_ids)
            
            # If we still have missing devices, create minimal objects
            if len(devices) < len(group.device_ids):
                found_ids = {device.id for device in devices}
                for device_id in group.device_ids:
                    if device_id not in found_ids:
                        logger.warning(f"No device found in registry for {device_id}, creating minimal device")
                        generation = DeviceGeneration.GEN2 if device_id.startswith("shellyplus") or device_id.startswith("shellypro") else DeviceGeneration.GEN1
                        minimal_device = Device(
                            id=device_id,
                            name=device_id,
                            model=device_id.split("-")[0] if "-" in device_id else device_id,
                            generation=generation,
                            ip_address=None,  # IP not available
                            mac_address=device_id  # Use the ID as MAC address
                        )
                        devices.append(minimal_device)
        
        return devices
    
    async def send_command(self, device: Device, command: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send a command to a specific device.
        
        Args:
            device: The device to send the command to
            command: Command name
            parameters: Command parameters
            
        Returns:
            Command result or error information
        """
        if not parameters:
            parameters = {}
            
        try:
            if not self.session:
                await self.start()
                
            if device.ip_address is None:
                return {"success": False, "error": f"Device IP address unknown for {device.id}"}
                
            # Select appropriate method based on device generation
            if device.generation == DeviceGeneration.GEN1:
                return await self._send_gen1_command(device, command, parameters)
            else:
                return await self._send_gen2_command(device, command, parameters)
                
        except Exception as e:
            logger.error(f"Error sending command to device {device.id}: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _send_gen1_command(self, device: Device, command: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send command to Gen1 device.
        
        Args:
            device: Gen1 device
            command: Command name
            parameters: Command parameters
            
        Returns:
            Command result
        """
        # Map common commands to Gen1 endpoints
        endpoint_map = {
            "turn_on": "relay/0",
            "turn_off": "relay/0",
            "toggle": "relay/0",
            "status": "status",
            "reboot": "reboot",
            "set_brightness": "light/0"
        }
        
        # Map parameters based on command
        param_map = {}
        if command == "turn_on":
            param_map = {"turn": "on"}
        elif command == "turn_off":
            param_map = {"turn": "off"}
        elif command == "toggle":
            param_map = {"turn": "toggle"}
        elif command == "set_brightness":
            if "brightness" in parameters:
                param_map = {"brightness": parameters["brightness"]}
        else:
            # For other commands, use parameters as-is
            param_map = parameters
        
        # Determine endpoint
        endpoint = endpoint_map.get(command, command)
        
        # Build URL
        url = f"http://{device.ip_address}/{endpoint}"
        if param_map:
            # Add parameters to URL query string
            query_string = "&".join([f"{k}={v}" for k, v in param_map.items()])
            url = f"{url}?{query_string}"
        
        logger.debug(f"Sending Gen1 command to {device.id}: {url}")
        
        # Send the request
        try:
            async with self.session.get(url, timeout=5) as response:
                if response.status == 200:
                    response_data = await response.json()
                    return {"success": True, "result": response_data}
                else:
                    error_text = await response.text()
                    return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _send_gen2_command(self, device: Device, command: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send command to Gen2 device.
        
        Args:
            device: Gen2 device
            command: Command name
            parameters: Command parameters
            
        Returns:
            Command result
        """
        # Map common commands to Gen2 RPC methods
        method_map = {
            "turn_on": "Switch.Set",
            "turn_off": "Switch.Set",
            "toggle": "Switch.Toggle",
            "status": "Shelly.GetStatus",
            "reboot": "Shelly.Reboot",
            "set_brightness": "Light.Set"
        }
        
        # Map parameters based on command
        params_map = {}
        if command == "turn_on":
            params_map = {"id": 0, "on": True}
        elif command == "turn_off":
            params_map = {"id": 0, "on": False}
        elif command == "toggle":
            params_map = {"id": 0}
        elif command == "set_brightness":
            if "brightness" in parameters:
                # Convert 0-100 brightness to 0-100
                brightness = min(100, max(0, parameters["brightness"]))
                params_map = {"id": 0, "brightness": brightness}
        else:
            # For other commands, use parameters as-is
            params_map = parameters
        
        # Get RPC method
        method = method_map.get(command, command)
        
        # Build URL and payload
        url = f"http://{device.ip_address}/rpc"
        payload = {
            "id": 1,
            "src": "shelly-bulk-control",
            "method": method,
            "params": params_map
        }
        
        logger.debug(f"Sending Gen2 command to {device.id}: {method} with params {params_map}")
        
        # Send the request
        try:
            async with self.session.post(url, json=payload, timeout=5) as response:
                if response.status == 200:
                    response_data = await response.json()
                    if "error" in response_data:
                        return {"success": False, "error": response_data["error"]}
                    return {"success": True, "result": response_data.get("result", {})}
                else:
                    error_text = await response.text()
                    return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
        except asyncio.TimeoutError:
            return {"success": False, "error": "Request timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def operate_group(self, group_name: str, action: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Perform an operation on all devices in a group.
        
        Args:
            group_name: Name of the group
            action: Action to perform
            parameters: Additional parameters
            
        Returns:
            Operation results
        """
        if not parameters:
            parameters = {}
            
        try:
            # Get devices in the group
            devices = self.get_devices_for_group(group_name)
            
            if not devices:
                return {
                    "group": group_name,
                    "action": action,
                    "parameters": parameters,
                    "device_count": 0,
                    "warning": f"No devices found in group '{group_name}'"
                }
            
            # Execute operation on all devices concurrently
            tasks = []
            for device in devices:
                tasks.append(self.send_command(device, action, parameters))
            
            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            device_results = {}
            for device, result in zip(devices, results):
                if isinstance(result, Exception):
                    device_results[device.id] = {"success": False, "error": str(result)}
                else:
                    device_results[device.id] = result
            
            # Return consolidated results
            return {
                "group": group_name,
                "action": action,
                "parameters": parameters,
                "device_count": len(devices),
                "results": device_results
            }
            
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Error operating on group '{group_name}': {str(e)}")
            return {"error": f"Error: {str(e)}"}
    
    # Convenience methods for common operations
    
    async def turn_on_group(self, group_name: str) -> Dict[str, Any]:
        """Turn on all devices in a group."""
        return await self.operate_group(group_name, "turn_on")
    
    async def turn_off_group(self, group_name: str) -> Dict[str, Any]:
        """Turn off all devices in a group."""
        return await self.operate_group(group_name, "turn_off")
    
    async def toggle_group(self, group_name: str) -> Dict[str, Any]:
        """Toggle all devices in a group."""
        return await self.operate_group(group_name, "toggle")
    
    async def get_group_status(self, group_name: str) -> Dict[str, Any]:
        """Get status of all devices in a group."""
        return await self.operate_group(group_name, "status")
    
    async def reboot_group(self, group_name: str) -> Dict[str, Any]:
        """Reboot all devices in a group."""
        return await self.operate_group(group_name, "reboot")
    
    async def set_brightness_group(self, group_name: str, brightness: int) -> Dict[str, Any]:
        """Set brightness for all light devices in a group."""
        return await self.operate_group(group_name, "set_brightness", {"brightness": brightness})
        
    async def check_updates_group(self, group_name: str) -> Dict[str, Any]:
        """
        Check for firmware updates for all devices in a group.
        
        Args:
            group_name: Name of the group to check
            
        Returns:
            Dict with results of the operation
        """
        logger.info(f"Checking for firmware updates for group '{group_name}'")
        
        # Get devices for the group
        try:
            devices = self.get_devices_for_group(group_name)
        except ValueError as e:
            return {"error": str(e)}
        
        if not devices:
            return {
                "warning": f"No devices found in group '{group_name}'",
                "group": group_name,
                "action": "check_updates",
                "parameters": {},
                "device_count": 0,
                "results": {}
            }
        
        # Start HTTP session if needed
        if self.session is None:
            await self.start()
        
        results = {}
        
        # Check each device for updates
        for device in devices:
            try:
                if not device.ip_address:
                    results[device.id] = {
                        "success": False, 
                        "error": "IP address unknown"
                    }
                    continue
                
                # Use appropriate method based on device generation
                if device.generation == DeviceGeneration.GEN1:
                    update_info = await self._check_gen1_updates(device)
                else:
                    update_info = await self._check_gen2_updates(device)
                
                results[device.id] = {
                    "success": True,
                    "result": update_info
                }
            except Exception as e:
                logger.error(f"Error checking updates for {device.id}: {e}")
                results[device.id] = {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "group": group_name,
            "action": "check_updates",
            "parameters": {},
            "device_count": len(devices),
            "results": results
        }
    
    async def apply_updates_group(self, group_name: str, 
                               only_with_updates: bool = True) -> Dict[str, Any]:
        """
        Apply firmware updates to all devices in a group.
        
        Args:
            group_name: Name of the group to update
            only_with_updates: If True, only update devices with available updates
            
        Returns:
            Dict with results of the operation
        """
        logger.info(f"Applying firmware updates for group '{group_name}'")
        
        # Get devices for the group
        try:
            devices = self.get_devices_for_group(group_name)
        except ValueError as e:
            return {"error": str(e)}
        
        if not devices:
            return {
                "warning": f"No devices found in group '{group_name}'",
                "group": group_name,
                "action": "apply_updates",
                "parameters": {"only_with_updates": only_with_updates},
                "device_count": 0,
                "results": {}
            }
        
        # Start HTTP session if needed
        if self.session is None:
            await self.start()
        
        # First check which devices have updates available if needed
        updates_available = {}
        if only_with_updates:
            update_results = await self.check_updates_group(group_name)
            for device_id, result in update_results.get("results", {}).items():
                if result.get("success") and result.get("result", {}).get("has_update", False):
                    updates_available[device_id] = True
        
        results = {}
        
        # Apply updates to each device
        for device in devices:
            try:
                # Skip devices without updates if only_with_updates is True
                if only_with_updates and not updates_available.get(device.id, False):
                    results[device.id] = {
                        "success": True,
                        "result": "No update needed"
                    }
                    continue
                
                if not device.ip_address:
                    results[device.id] = {
                        "success": False, 
                        "error": "IP address unknown"
                    }
                    continue
                
                # Use appropriate method based on device generation
                if device.generation == DeviceGeneration.GEN1:
                    update_result = await self._apply_gen1_update(device)
                else:
                    update_result = await self._apply_gen2_update(device)
                
                results[device.id] = {
                    "success": True,
                    "result": update_result
                }
            except Exception as e:
                logger.error(f"Error applying update to {device.id}: {e}")
                results[device.id] = {
                    "success": False,
                    "error": str(e)
                }
        
        return {
            "group": group_name,
            "action": "apply_updates",
            "parameters": {"only_with_updates": only_with_updates},
            "device_count": len(devices),
            "results": results
        }
    
    async def _check_gen1_updates(self, device) -> Dict[str, Any]:
        """Check for updates on a Gen1 device."""
        url = f"http://{device.ip_address}/status"
        logger.debug(f"Checking Gen1 update status from {url}")
        
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract update information
                    update_info = data.get("update", {})
                    has_update = update_info.get("has_update", False)
                    
                    result = {
                        "has_update": has_update,
                        "current_version": update_info.get("old_version", device.firmware_version),
                        "new_version": update_info.get("new_version") if has_update else None
                    }
                    
                    return result
                else:
                    return {
                        "has_update": False,
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            logger.error(f"Error checking Gen1 updates: {e}")
            raise
    
    async def _check_gen2_updates(self, device) -> Dict[str, Any]:
        """Check for updates on a Gen2 device."""
        url = f"http://{device.ip_address}/rpc/Shelly.GetStatus"
        logger.debug(f"Checking Gen2 update status from {url}")
        
        try:
            async with self.session.post(url, json={}, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check for updates in different locations
                    has_update = False
                    new_version = None
                    
                    # PRIMARY CHECK: sys.available_updates
                    if "sys" in data and "available_updates" in data["sys"]:
                        available_updates = data["sys"]["available_updates"]
                        
                        # Check for stable updates
                        if "stable" in available_updates:
                            has_update = True
                            new_version = available_updates["stable"].get("version")
                    
                    # SECONDARY CHECK: cloud.available_updates
                    elif "cloud" in data and "available_updates" in data["cloud"]:
                        available_updates = data["cloud"]["available_updates"]
                        
                        # Check for stable updates
                        if "stable" in available_updates:
                            has_update = True
                            new_version = available_updates["stable"].get("version")
                    
                    # FALLBACK: cloud.new_fw field
                    elif "cloud" in data and "new_fw" in data["cloud"]:
                        has_update = bool(data["cloud"]["new_fw"])
                    
                    return {
                        "has_update": has_update,
                        "current_version": device.firmware_version,
                        "new_version": new_version
                    }
                else:
                    return {
                        "has_update": False,
                        "error": f"HTTP {response.status}"
                    }
        except Exception as e:
            logger.error(f"Error checking Gen2 updates: {e}")
            raise
    
    async def _apply_gen1_update(self, device) -> Dict[str, Any]:
        """Apply update on a Gen1 device."""
        url = f"http://{device.ip_address}/ota"
        logger.debug(f"Applying update to Gen1 device at {url}")
        
        try:
            async with self.session.get(url, timeout=30) as response:
                if response.status == 200:
                    return {
                        "message": "Update triggered successfully",
                        "status": response.status
                    }
                else:
                    error_text = await response.text()
                    return {
                        "error": f"HTTP {response.status}: {error_text}"
                    }
        except Exception as e:
            logger.error(f"Error applying Gen1 update: {e}")
            raise
    
    async def _apply_gen2_update(self, device) -> Dict[str, Any]:
        """Apply update on a Gen2 device."""
        url = f"http://{device.ip_address}/rpc"
        logger.debug(f"Applying update to Gen2 device at {url}")
        
        payload = {
            "id": 1,
            "src": "shelly-bulk-control",
            "method": "Shelly.Update",
            "params": {
                "stage": "stable"  # Only use stable updates for safety
            }
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if "error" in data:
                        return {
                            "error": data["error"]["message"],
                            "code": data["error"]["code"]
                        }
                    return {
                        "message": "Update triggered successfully",
                        "response": data
                    }
                else:
                    error_text = await response.text()
                    return {
                        "error": f"HTTP {response.status}: {error_text}"
                    }
        except Exception as e:
            logger.error(f"Error applying Gen2 update: {e}")
            raise 