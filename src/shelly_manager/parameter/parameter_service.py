"""
Parameter management for Shelly devices.

This unified service handles parameter management for both capability-based
and direct device interactions.
"""
import asyncio
import aiohttp
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
import urllib.parse
from pathlib import Path

from ..utils.logging import get_logger
from ..models.device import Device, DeviceGeneration
from ..models.device_capabilities import device_capabilities, DeviceCapability
from ..models.device_registry import device_registry
from ..discovery.discovery_service import DiscoveryService
from ..grouping.group_manager import GroupManager
from ..models.parameters import ParameterDefinition, get_parameters_for_model, ParameterType
from ..models.parameter_mapping import ParameterMapper, parameter_manager
import time

logger = get_logger(__name__)

class ParameterService:
    """
    Service for managing device parameters.
    
    This service provides methods for getting and setting device parameters,
    as well as related operations like discovering available parameters.
    """
    
    def __init__(self):
        """Initialize the parameter service."""
        self.session = None
        self._parameter_cache = {}
        self._capabilities_cache = {}
        # Default timeout for HTTP requests
        self.http_timeout = 5  # seconds
    
    async def start(self):
        """Start the parameter service."""
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.http_timeout))
    
    async def initialize(self):
        """Initialize the parameter service.
        This is a wrapper around start() for consistent naming across services.
        """
        await self.start()
    
    async def stop(self):
        """Stop the parameter service."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def discover_device_parameters(self, device: Device) -> Dict[str, Any]:
        """
        Discover parameters available for a device using dynamic capability detection.
        
        Args:
            device: The device to discover parameters for
            
        Returns:
            Dictionary of parameter definitions
        """
        # Use the device capabilities system to get parameters
        capability = device_capabilities.get_capability_for_device(device)
        
        # If no existing capability is found, try to discover it
        if not capability:
            logger.info(f"No capability found for {device.id}, attempting discovery")
            discovery_service = DiscoveryService()
            await discovery_service.start()
            try:
                success = await discovery_service.discover_device_capabilities(device)
                if success:
                    capability = device_capabilities.get_capability_for_device(device)
                else:
                    logger.warning(f"Failed to discover capabilities for {device.id}")
            finally:
                await discovery_service.stop()
        
        # If we have a capability definition, return its parameters
        if capability:
            self._capabilities_cache[device.id] = capability
            result = {}
            
            # Extract parameters from capability
            for param_name, param_info in capability.parameters.items():
                # Skip read-only parameters unless we explicitly want them
                if param_info.get("read_only", False):
                    continue
                    
                # Convert to ParameterDefinition format
                result[param_name] = ParameterDefinition(
                    name=param_name,
                    display_name=param_name.replace("_", " ").title(),
                    parameter_type=self._map_parameter_type(param_info.get("type", "string")),
                    description=param_info.get("description", ""),
                    writable=not param_info.get("read_only", False),
                    api=param_info.get("api", ""),
                    parameter_path=param_info.get("parameter_path", param_name)
                )
            
            return result
        
        return {}
    
    def _map_parameter_type(self, type_str: str) -> ParameterType:
        """Map string parameter type to ParameterType enum."""
        type_map = {
            "boolean": ParameterType.BOOLEAN,
            "integer": ParameterType.INTEGER,
            "float": ParameterType.FLOAT,
            "string": ParameterType.STRING,
            "array": ParameterType.ARRAY,
            "object": ParameterType.OBJECT,
            "null": ParameterType.STRING
        }
        return type_map.get(type_str, ParameterType.STRING)
    
    async def get_all_parameters(self, include_device_ids: List[str] = None) -> Dict[str, Any]:
        """
        Get all available parameters across all devices or specified devices.
        
        Args:
            include_device_ids: Optional list of device IDs to include
            
        Returns:
            Dictionary with device types and parameters
        """
        # If specific devices are requested, get capabilities for those
        if include_device_ids:
            devices = []
            for device_id in include_device_ids:
                device = device_registry.get_device(device_id)
                if device:
                    devices.append(device)
        else:
            # Get capabilities for all known device types
            all_parameters = {}
            all_device_types = set()
            
            # Collect from capabilities system
            for cap_id, capability in device_capabilities.capabilities.items():
                all_device_types.add(cap_id)
                for param_name, param_details in capability.parameters.items():
                    if param_name not in all_parameters:
                        all_parameters[param_name] = {
                            "type": param_details.get("type", "unknown"),
                            "description": param_details.get("description", ""),
                            "supported_by": []
                        }
                    
                    all_parameters[param_name]["supported_by"].append(cap_id)
            
            return {
                "device_types": list(all_device_types),
                "parameters": all_parameters
            }
    
    async def get_all_device_parameters(self, device: Device) -> Dict[str, Dict[str, Any]]:
        """
        Get all parameters for a specific device based on its capabilities.
        
        Args:
            device: The device to get parameters for
            
        Returns:
            Dictionary of parameters with their details and current values
        """
        result = {}
        
        # Check if device has a specific capability type file
        capability = None
        device_type = device.raw_type
        
        # Try to get capability directly by device type
        if device_type:
            logger.debug(f"Looking for capability directly by type: {device_type}")
            capability = device_capabilities.get_capability(device_type)
        
        # If not found, try through the device capability mapping
        if not capability:
            logger.debug(f"Looking for capability through device mapping for {device.id}")
            capability = device_capabilities.get_capability_for_device(device)
            
        # If still no capability found, try to discover it
        if not capability:
            logger.info(f"No capability found for {device.id}, attempting discovery")
            discovery_service = DiscoveryService()
            try:
                await discovery_service.start()
                success = await discovery_service.discover_device_capabilities(device)
                if success:
                    capability = device_capabilities.get_capability_for_device(device)
                else:
                    logger.warning(f"Failed to discover capabilities for {device.id}")
            finally:
                await discovery_service.stop()
        
        # If we have a capability definition, get all parameters
        if capability:
            logger.info(f"Using capability definition for {device.id} (type: {capability.device_type})")
            # Only request parameters that are defined in the capability
            for param_name, param_info in capability.parameters.items():
                # Get current value if possible
                success, value = await self.get_parameter_value(device, param_name, log_warnings=False)
                
                result[param_name] = {
                    "type": param_info.get("type", "unknown"),
                    "description": param_info.get("description", ""),
                    "api": param_info.get("api", ""),
                    "read_only": param_info.get("read_only", True),
                    "parameter_path": param_info.get("parameter_path", param_name),
                    "value": value if success else None
                }
        else:
            # If no capability is available, get basic parameters from known endpoints
            logger.info(f"No capability definition found, using basic parameter detection for {device.id}")
            
            # Get general device info
            if device.generation == DeviceGeneration.GEN1:
                # For Gen1 devices, get settings and status
                params = await self._get_gen1_basic_parameters(device)
                result.update(params)
            else:
                # For Gen2 devices, use RPC methods
                params = await self._get_gen2_basic_parameters(device)
                result.update(params)
        
        return result
    
    async def _get_gen1_basic_parameters(self, device: Device) -> Dict[str, Dict[str, Any]]:
        """Get basic parameters from a Gen1 device without warnings."""
        result = {}
        
        # Try to get settings
        try:
            url = f"http://{device.ip_address}/settings"
            async with self.session.get(url, timeout=5) as response:
                if response.status == 200:
                    settings = await response.json()
                    
                    # Process each setting
                    for key, value in settings.items():
                        result[key] = {
                            "type": self._infer_parameter_type(value),
                            "description": f"Parameter {key}",
                            "api": "settings",
                            "read_only": False,  # Assume settings are writable by default
                            "value": value
                        }
        except Exception as e:
            logger.debug(f"Error getting settings for Gen1 device {device.id}: {str(e)}")
        
        # Try to get status
        try:
            url = f"http://{device.ip_address}/status"
            async with self.session.get(url, timeout=5) as response:
                if response.status == 200:
                    status = await response.json()
                    
                    # Process each status field
                    for key, value in status.items():
                        result[key] = {
                            "type": self._infer_parameter_type(value),
                            "description": f"Parameter {key}",
                            "api": "status",
                            "read_only": True,  # Status values are generally read-only
                            "value": value
                        }
        except Exception as e:
            logger.debug(f"Error getting status for Gen1 device {device.id}: {str(e)}")
        
        # Try to get Shelly info
        try:
            url = f"http://{device.ip_address}/shelly"
            async with self.session.get(url, timeout=5) as response:
                if response.status == 200:
                    info = await response.json()
                    
                    # Process each info field
                    for key, value in info.items():
                        result[key] = {
                            "type": self._infer_parameter_type(value),
                            "description": f"Parameter {key}",
                            "api": "shelly",
                            "read_only": False,  # Some Shelly info might be writable
                            "value": value
                        }
        except Exception as e:
            logger.debug(f"Error getting Shelly info for Gen1 device {device.id}: {str(e)}")
            
        return result
    
    async def _get_gen2_basic_parameters(self, device: Device) -> Dict[str, Dict[str, Any]]:
        """Get basic parameters from a Gen2 device without warnings."""
        result = {}
        
        # RPC methods to try
        methods = ["Shelly.GetStatus", "Shelly.GetConfig"]
        
        for method in methods:
            try:
                url = f"http://{device.ip_address}/rpc"
                payload = {
                    "id": 1,
                    "src": "shelly-bulk-control",
                    "method": method,
                    "params": {}
                }
                
                async with self.session.post(url, json=payload, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "result" in data:
                            # Flatten the result structure
                            self._flatten_json(data["result"], "", result, method)
            except Exception as e:
                logger.debug(f"Error calling {method} for Gen2 device {device.id}: {str(e)}")
                
        return result
    
    def _flatten_json(self, json_obj: Dict[str, Any], prefix: str, result: Dict[str, Dict[str, Any]], method: str):
        """
        Flatten a nested JSON object into parameter entries.
        
        Args:
            json_obj: The JSON object to flatten
            prefix: Current prefix for nested keys
            result: Result dictionary to update
            method: The RPC method that was called
        """
        for key, value in json_obj.items():
            new_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                # Recursively flatten nested objects
                self._flatten_json(value, new_key, result, method)
            else:
                # Add leaf values as parameters
                is_status = "Status" in method
                result[new_key] = {
                    "type": self._infer_parameter_type(value),
                    "description": f"Parameter {new_key}",
                    "api": method,
                    "read_only": is_status,  # Status values are read-only
                    "value": value
                }
    
    def _get_common_parameters_for_device_type(self, device_type: str) -> List[str]:
        """
        Get a list of common parameters that are likely to be supported by a device type.
        
        Args:
            device_type: The device type
            
        Returns:
            List of parameter names
        """
        # Get standard parameters from parameter manager
        common_params = []
        for param in parameter_manager.get_all_common_parameters():
            common_params.append(param.name)
            
        # Add basic device parameters that are commonly available
        basic_params = [
            "name", "type", "mac", "ip", "fw", "eco_mode", "cloud.enabled",
            "led_status_disable", "mqtt.enable", "mqtt.server"
        ]
        
        return list(set(common_params + basic_params))
    
    def _infer_parameter_type(self, value: Any) -> str:
        """Infer the parameter type from its value."""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, dict):
            return "object"
        elif isinstance(value, list):
            return "array"
        else:
            return "string"
    
    async def get_parameter_value(self, device: Device, parameter_name: str, log_warnings: bool = True) -> Tuple[bool, Any]:
        """
        Get the current value of a parameter from a device.
        
        Args:
            device: The device to get the parameter from
            parameter_name: The name of the parameter
            log_warnings: Whether to log warnings if parameter is not found
            
        Returns:
            Tuple of (success, value)
        """
        if not device.ip_address:
            logger.error(f"Cannot get parameter: Device {device.id} has no IP address")
            return False, None
            
        # Check if we have a capability for this device type
        capability = device_capabilities.get_capability_for_device(device)
        
        try:
            # Choose appropriate method based on device generation
            if device.generation == DeviceGeneration.GEN1:
                return await self._get_gen1_parameter(device, parameter_name, capability, log_warnings)
            else:
                return await self._get_gen2_parameter(device, parameter_name, capability, log_warnings)
                
        except Exception as e:
            logger.error(f"Error getting parameter {parameter_name} from device {device.id}: {str(e)}")
            return False, None
    
    async def _get_gen1_parameter(self, device: Device, parameter_name: str, 
                                 capability: Optional[DeviceCapability],
                                 log_warnings: bool = True) -> Tuple[bool, Any]:
        """
        Get a parameter from a Gen1 device.
        
        Args:
            device: The device
            parameter_name: Parameter name
            capability: Optional device capability
            log_warnings: Whether to log warnings if parameter is not found
            
        Returns:
            Tuple of (success, value)
        """
        # Determine API endpoint from capability if available
        api_path = None
        if capability:
            param_details = capability.get_parameter_details(parameter_name)
            if param_details:
                api_path = param_details.get("api")
        
        # If we have a specific API path from capability, use it
        if api_path:
            url = f"http://{device.ip_address}/{api_path}"
            try:
                async with self.session.get(url, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Parameter could be at the root or nested
                        parameter_parts = parameter_name.split('.')
                        value = data
                        try:
                            for part in parameter_parts:
                                if part in value:
                                    value = value[part]
                                else:
                                    if log_warnings:
                                        logger.warning(f"Parameter part '{part}' not found in response for {parameter_name}")
                                    return False, None
                            return True, value
                        except (KeyError, TypeError):
                            if log_warnings:
                                logger.warning(f"Could not extract parameter {parameter_name} from response")
                            return False, None
                    else:
                        logger.error(f"Error getting parameter from {url}: HTTP {response.status}")
                        return False, None
            except Exception as e:
                logger.error(f"Error accessing Gen1 API at {url}: {str(e)}")
                return False, None
        
        # Fallback to known endpoints
        # Try settings endpoint first
        url = f"http://{device.ip_address}/settings"
        try:
            async with self.session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if parameter_name in data:
                        return True, data[parameter_name]
        except Exception:
            pass
            
        # Try status endpoint next
        url = f"http://{device.ip_address}/status"
        try:
            async with self.session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if parameter_name in data:
                        return True, data[parameter_name]
                        
                    # Check in meters for power parameters
                    if 'meters' in data and parameter_name.startswith('power'):
                        try:
                            index = int(parameter_name.split('_')[1]) - 1
                            if index >= 0 and index < len(data['meters']):
                                return True, data['meters'][index]['power']
                        except (IndexError, ValueError):
                            pass
        except Exception:
            pass
            
        # Parameter not found
        if log_warnings:
            logger.warning(f"Parameter {parameter_name} not found for Gen1 device {device.id}")
        return False, None
    
    async def _get_gen2_parameter(self, device: Device, parameter_name: str, 
                                 capability: Optional[DeviceCapability],
                                 log_warnings: bool = True) -> Tuple[bool, Any]:
        """
        Get a parameter from a Gen2/Gen3 device.
        
        Args:
            device: The device
            parameter_name: Parameter name
            capability: Optional device capability
            log_warnings: Whether to log warnings if parameter is not found
            
        Returns:
            Tuple of (success, value)
        """
        # Determine RPC method from capability if available
        rpc_method = None
        path_in_response = None
        
        if capability:
            param_details = capability.get_parameter_details(parameter_name)
            if param_details:
                api_path = param_details.get("api")
                # Extract method and path from API info
                if api_path and api_path.startswith("rpc/"):
                    parts = api_path.split('/')
                    if len(parts) >= 2:
                        rpc_method = parts[1]
                        # If parameter has path info, use it
                        parameter_parts = parameter_name.split('.')
                        if len(parameter_parts) > 1:
                            path_in_response = parameter_parts
        
        # If we have capability info, use it
        if rpc_method:
            url = f"http://{device.ip_address}/rpc"
            payload = {
                "id": 1,
                "src": "shelly-bulk-control",
                "method": rpc_method,
                "params": {}
            }
            
            try:
                async with self.session.post(url, json=payload, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "result" in data:
                            result = data["result"]
                            
                            # If we have path info, navigate to the right place
                            if path_in_response:
                                try:
                                    current = result
                                    for part in path_in_response:
                                        if part in current:
                                            current = current[part]
                                        else:
                                            if log_warnings:
                                                logger.warning(f"Path part '{part}' not found in response")
                                            return False, None
                                    return True, current
                                except (KeyError, TypeError):
                                    if log_warnings:
                                        logger.warning(f"Could not extract parameter from RPC response")
                                    return False, None
                            
                            # Otherwise return the entire result
                            return True, result
                        else:
                            logger.error(f"Error in RPC response: {data}")
                            return False, None
                    else:
                        logger.error(f"Error calling RPC method {rpc_method}: HTTP {response.status}")
                        return False, None
            except Exception as e:
                logger.error(f"Error accessing Gen2/Gen3 RPC: {str(e)}")
                return False, None
        
        # Fallback to common methods if no capability info
        
        # Try Shelly.GetConfig first for settings
        url = f"http://{device.ip_address}/rpc"
        payload = {
            "id": 1,
            "src": "shelly-bulk-control",
            "method": "Shelly.GetConfig",
            "params": {}
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if "result" in data:
                        # For nested parameters like switch.0.name
                        parts = parameter_name.split('.')
                        current = data["result"]
                        
                        try:
                            for part in parts:
                                if part in current:
                                    current = current[part]
                                elif part.isdigit() and int(part) < len(current):
                                    current = current[int(part)]
                                else:
                                    # Parameter not found in this response
                                    break
                            else:
                                # If we got through all parts, we found it
                                return True, current
                        except (KeyError, TypeError, IndexError):
                            pass
        except Exception:
            pass
        
        # Try Shelly.GetStatus for power and other status values
        payload = {
            "id": 1,
            "src": "shelly-bulk-control",
            "method": "Shelly.GetStatus",
            "params": {}
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if "result" in data:
                        # For nested parameters like switch.0.output
                        parts = parameter_name.split('.')
                        current = data["result"]
                        
                        try:
                            for part in parts:
                                if part in current:
                                    current = current[part]
                                elif part.isdigit() and int(part) < len(current):
                                    current = current[int(part)]
                                else:
                                    # Parameter not found in this response
                                    break
                            else:
                                # If we got through all parts, we found it
                                return True, current
                        except (KeyError, TypeError, IndexError):
                            pass
        except Exception:
            pass
            
        # Parameter not found
        if log_warnings:
            logger.warning(f"Parameter {parameter_name} not found for Gen2/Gen3 device {device.id}")
        return False, None
    
    async def set_parameter_value(self, device: Device, parameter_name: str, value: Any, auto_restart: bool = False) -> Tuple[bool, Optional[Dict]]:
        """
        Set a parameter value on a device.
        
        Args:
            device: The device to set the parameter on
            parameter_name: The name of the parameter
            value: The new value for the parameter
            auto_restart: Whether to automatically restart the device if required
            
        Returns:
            Tuple of (success, response)
        """
        if not device.ip_address:
            logger.error(f"Cannot set parameter: Device {device.id} has no IP address")
            return False, None
            
        # Check if we have a capability for this device type
        capability = device_capabilities.get_capability_for_device(device)
        
        # Check if this is a restart-requiring parameter
        restart_required = False
        if capability and parameter_name in capability.parameters:
            restart_required = capability.parameters[parameter_name].get("requires_restart", False)
        
        try:
            # Choose appropriate method based on device generation
            if device.generation == DeviceGeneration.GEN1:
                success, response = await self._set_gen1_parameter(device, parameter_name, value, capability)
            else:
                success, response = await self._set_gen2_parameter(device, parameter_name, value, capability)
            
            # Handle automatic device restart if needed and requested
            if success and restart_required and auto_restart:
                logger.info(f"Parameter '{parameter_name}' requires device restart. Restarting {device.id}...")
                restart_success = await self._restart_device(device)
                if not restart_success:
                    logger.warning(f"Failed to restart device {device.id} after setting parameter")
                    # The parameter was set successfully, so we still return success=True
            
            return success, response
        except Exception as e:
            logger.error(f"Error setting parameter {parameter_name} on device {device.id}: {str(e)}")
            return False, None

    async def _set_gen1_parameter(self, device: Device, parameter_name: str, value: Any, 
                                 capability: Optional[DeviceCapability]) -> Tuple[bool, Optional[Dict]]:
        """
        Set a parameter on a Gen1 device.
        
        Args:
            device: The device
            parameter_name: Parameter name
            value: Value to set
            capability: Optional device capability
            
        Returns:
            Tuple of (success, response_data)
        """
        # Determine API endpoint from capability if available
        api_path = None
        gen1_parameter_name = parameter_name
        
        # Map standard parameter names to Gen1-specific names if needed
        if parameter_name == "eco_mode":
            gen1_parameter_name = "eco_mode_enabled"
        elif parameter_name in parameter_manager.standard_to_gen1:
            gen1_parameter_name = parameter_manager.standard_to_gen1[parameter_name]
            
        if capability:
            param_details = capability.get_parameter_details(gen1_parameter_name)
            if param_details:
                api_path = param_details.get("api")
                # Check if parameter is read-only
                if param_details.get("read_only", False):
                    logger.warning(f"Cannot set read-only parameter {gen1_parameter_name} on device {device.id}")
                    return False, {"error": "Parameter is read-only"}
        
        # Format value properly for Gen1 devices
        formatted_value = self._format_value_for_gen1(gen1_parameter_name, value)
        
        # For Gen1 devices, most settings are set via /settings endpoint
        url = f"http://{device.ip_address}/settings"
        
        # Some parameters might need special handling
        if parameter_name.startswith("switch") and "." in parameter_name:
            parts = parameter_name.split(".")
            if len(parts) >= 3:
                channel = parts[1]
                action = parts[2]
                if action == "turn":
                    # Handle switch on/off
                    url = f"http://{device.ip_address}/relay/{channel}"
                    params = {"turn": "on" if value else "off"}
                    async with self.session.get(url, params=params, timeout=5) as response:
                        if response.status == 200:
                            data = await response.json()
                            return True, data
                        else:
                            logger.error(f"Error setting switch parameter: HTTP {response.status}")
                            return False, {"error": f"HTTP error {response.status}"}
                
        # Default approach: use settings endpoint
        params = {gen1_parameter_name: formatted_value}
        
        try:
            logger.debug(f"Setting Gen1 parameter {gen1_parameter_name} = {formatted_value} for device {device.id}")
            async with self.session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    return True, data
                else:
                    logger.error(f"Error setting parameter: HTTP {response.status}")
                    return False, {"error": f"HTTP error {response.status}"}
        except Exception as e:
            logger.error(f"Error accessing Gen1 settings API: {str(e)}")
            return False, {"error": str(e)}
    
    def _format_value_for_gen1(self, parameter_name: str, value: Any) -> str:
        """Format a value for Gen1 devices."""
        # Format boolean values correctly
        if isinstance(value, bool):
            # For eco_mode specifically, use true/false instead of on/off
            if parameter_name == "eco_mode" or parameter_name == "eco_mode_enabled":
                return "true" if value else "false"
            else:
                return "on" if value else "off"
        elif isinstance(value, (int, float)):
            return str(value)
        else:
            return str(value)
    
    async def _set_gen2_parameter(self, device: Device, parameter_name: str, value: Any, 
                                 capability: Optional[DeviceCapability]) -> Tuple[bool, Optional[Dict]]:
        """
        Set a parameter on a Gen2/Gen3 device.
        
        Args:
            device: The device
            parameter_name: Parameter name
            value: Value to set
            capability: Optional device capability
            
        Returns:
            Tuple of (success, response_data)
        """
        # Determine RPC method from capability if available
        rpc_method = None
        parameter_path = None
        
        if capability:
            param_details = capability.get_parameter_details(parameter_name)
            if param_details:
                # Check if parameter is read-only
                if param_details.get("read_only", False):
                    logger.warning(f"Cannot set read-only parameter {parameter_name} on device {device.id}")
                    return False, {"error": "Parameter is read-only"}
                
                api_path = param_details.get("api")
                # Extract method and path from API info
                if api_path and api_path.startswith("rpc/"):
                    parts = api_path.split('/')
                    if len(parts) >= 2:
                        rpc_method = parts[1]
        
        # Extract parameters parts for nested parameters
        parameter_parts = parameter_name.split('.')
        
        # Special case for common parameters
        if parameter_name.startswith("switch") and len(parameter_parts) >= 3:
            channel = parameter_parts[1]
            action = parameter_parts[2]
            
            if action == "output" or action == "turn":
                # Handle switch on/off via Switch.Set
                url = f"http://{device.ip_address}/rpc"
                payload = {
                    "id": 1,
                    "src": "shelly-bulk-control",
                    "method": "Switch.Set",
                    "params": {
                        "id": int(channel),
                        "on": bool(value)
                    }
                }
                
                async with self.session.post(url, json=payload, timeout=5) as response:
                    if response.status == 200:
                        data = await response.json()
                        return True, data
                    else:
                        logger.error(f"Error setting switch parameter: HTTP {response.status}")
                        return False, {"error": f"HTTP error {response.status}"}
        
        # Handle Shelly.SetConfig parameters (most config parameters)
        # Build config structure based on parameter name
        config = {}
        current = config
        
        # Build nested config structure
        for i, part in enumerate(parameter_parts):
            if i == len(parameter_parts) - 1:
                # Last part is the actual parameter name
                current[part] = value
            else:
                # Check if this part represents an array index
                if part.isdigit():
                    # Convert string digit to actual index
                    idx = int(part)
                    # Create array if needed in the previous level
                    if i > 0 and isinstance(current.get(parameter_parts[i-1]), list):
                        # Ensure array is large enough
                        prev_key = parameter_parts[i-1]
                        while len(current[prev_key]) <= idx:
                            current[prev_key].append({})
                        current = current[prev_key][idx]
                    else:
                        # If we can't handle this, try the raw config approach
                        config = {parameter_name: value}
                        break
                else:
                    # Create nested object
                    current[part] = {}
                    current = current[part]
        
        # Send the config to the device
        url = f"http://{device.ip_address}/rpc"
        payload = {
            "id": 1,
            "src": "shelly-bulk-control",
            "method": "Shelly.SetConfig",
            "params": {"config": config}
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if "error" in data:
                        logger.error(f"Error in RPC response: {data['error']}")
                        return False, data
                    return True, data
                else:
                    logger.error(f"Error setting parameter: HTTP {response.status}")
                    return False, {"error": f"HTTP error {response.status}"}
        except Exception as e:
            logger.error(f"Error accessing Gen2/Gen3 RPC: {str(e)}")
            return False, {"error": str(e)}
    
    async def list_all_device_parameters(self, device: Device, include_readonly: bool = True) -> Dict[str, Dict[str, Any]]:
        """
        List all parameters for a device, including their current values.
        
        Args:
            device: The device to list parameters for
            include_readonly: Whether to include read-only parameters
            
        Returns:
            Dictionary of parameters with their details and values
        """
        all_params = await self.get_all_device_parameters(device)
        
        # Filter out read-only parameters if needed
        if not include_readonly:
            all_params = {
                param_name: param_info 
                for param_name, param_info in all_params.items() 
                if not param_info.get("read_only", True)
            }
            
        return all_params

    async def _restart_device(self, device: Device) -> bool:
        """
        Restart a device.
        
        Args:
            device: The device to restart
            
        Returns:
            True if restart was successful, False otherwise
        """
        if not device.ip_address:
            logger.error(f"Cannot restart device: Device {device.id} has no IP address")
            return False
        
        try:
            # Choose appropriate method based on device generation
            if device.generation == DeviceGeneration.GEN1:
                # Gen1 devices use /reboot endpoint
                url = f"http://{device.ip_address}/reboot"
                
                # Make the request
                if not self.session:
                    await self.start()
                    
                async with self.session.get(url) as response:
                    if response.status == 200:
                        logger.info(f"Successfully restarted device {device.id}")
                        return True
                    else:
                        logger.warning(f"Failed to restart device {device.id}: HTTP {response.status}")
                        return False
                    
            else:
                # Gen2 devices use Shelly.Reboot RPC method
                url = f"http://{device.ip_address}/rpc"
                
                # Create request data
                data = {
                    "id": 1,
                    "method": "Shelly.Reboot",
                    "params": {}
                }
                
                # Make the request
                if not self.session:
                    await self.start()
                    
                async with self.session.post(url, json=data) as response:
                    if response.status == 200:
                        try:
                            result = await response.json()
                            # Check if there's an error in the response
                            if "error" in result:
                                logger.warning(f"Error restarting device {device.id}: {result['error']}")
                                return False
                            logger.info(f"Successfully restarted device {device.id}")
                            return True
                        except Exception as e:
                            logger.warning(f"Error parsing restart response for device {device.id}: {str(e)}")
                            return False
                    else:
                        logger.warning(f"Failed to restart device {device.id}: HTTP {response.status}")
                        return False
                    
        except Exception as e:
            logger.error(f"Error restarting device {device.id}: {str(e)}")
            return False 