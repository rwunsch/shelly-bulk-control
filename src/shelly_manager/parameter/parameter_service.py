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
from ..models.parameters import ParameterDefinition, get_parameters_for_model

logger = get_logger(__name__)

class ParameterService:
    """
    Service for managing device parameters.
    
    This unified service provides functionality for:
    - Discovering available parameters for devices
    - Getting and setting parameter values
    - Applying parameter values to groups of devices
    - Loading device information from storage when possible
    - Using device capabilities to determine parameter handling
    """
    
    def __init__(self, group_manager: GroupManager, discovery_service: Optional[DiscoveryService] = None):
        """
        Initialize the parameter service.
        
        Args:
            group_manager: Group manager for resolving device groups
            discovery_service: Discovery service for finding devices (optional)
        """
        self.group_manager = group_manager
        self.discovery_service = discovery_service
        self.http_timeout = 5  # seconds
        self.session = None
        self._parameter_cache: Dict[str, Dict[str, ParameterDefinition]] = {}
        self._device_cache: Dict[str, Device] = {}
        logger.debug("Unified ParameterService initialized")
    
    async def start(self):
        """Start the parameter service."""
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.http_timeout))
            logger.debug("HTTP session initialized")
            
        # If discovery service is provided and not started, start it
        if self.discovery_service and not getattr(self.discovery_service, "started", False):
            await self.discovery_service.start()
            logger.debug("Discovery service started")
    
    async def stop(self):
        """Stop the parameter service."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.debug("HTTP session closed")
    
    async def list_parameters(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List available parameters for a device or all known device types.
        
        Args:
            device_id: Optional device ID to get parameters for
            
        Returns:
            Dictionary of parameters and their details
        """
        if device_id:
            # Get parameters for a specific device
            device = await self._get_device(device_id)
            if not device:
                return {"error": f"Device '{device_id}' not found"}
            
            # Try capabilities-based approach first
            capability = device_capabilities.get_capability_for_device(device)
            if capability:
                # Return parameters for this device type
                return {
                    "device_id": device_id,
                    "device_type": capability.device_type,
                    "parameters": capability.parameters
                }
            else:
                # Fall back to legacy parameter definitions
                parameters = self.get_device_parameters(device)
                return {
                    "device_id": device_id,
                    "device_type": device.model or device.raw_type or "unknown",
                    "parameters": {name: param.__dict__ for name, param in parameters.items()}
                }
        else:
            # Get parameters for all known device types
            all_parameters = {}
            all_device_types = set()
            
            # First collect from capabilities system
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
            
            # Add any legacy parameters
            # TODO: Add logic to include legacy parameters if needed
            
            return {
                "device_types": list(all_device_types),
                "parameters": all_parameters
            }

    def get_device_parameters(self, device: Device) -> Dict[str, ParameterDefinition]:
        """
        Get parameter definitions for a device using legacy approach.
        
        Args:
            device: The device to get parameters for
            
        Returns:
            Dictionary of parameter definitions by name
        """
        # Check cache first
        if device.id in self._parameter_cache:
            return self._parameter_cache[device.id]
        
        # Get parameters based on device model
        parameters = get_parameters_for_model(device.model)
        
        # Cache the parameters
        self._parameter_cache[device.id] = parameters
        
        return parameters
    
    async def get_parameter(self, device_id: str, parameter: str) -> Dict[str, Any]:
        """
        Get the current value of a parameter for a device.
        
        Args:
            device_id: Device ID
            parameter: Parameter name
            
        Returns:
            Dictionary with parameter value and details
        """
        if not self.session:
            await self.start()
            
        # Get the device
        device = await self._get_device(device_id)
        if not device:
            return {"error": f"Device '{device_id}' not found"}
        
        # Try capabilities-based approach first
        capability = device_capabilities.get_capability_for_device(device)
        if capability and capability.has_parameter(parameter):
            # Get parameter details
            param_details = capability.get_parameter_details(parameter)
            
            # Handle different device generations
            try:
                if capability.generation == "gen1":
                    value = await self._get_gen1_parameter(device, param_details)
                else:
                    value = await self._get_gen2_parameter(device, param_details)
                    
                return {
                    "device_id": device_id,
                    "parameter": parameter,
                    "value": value,
                    "type": param_details.get("type", "unknown"),
                    "description": param_details.get("description", "")
                }
            except Exception as e:
                logger.error(f"Error getting parameter '{parameter}' for device {device_id}: {e}")
                return {"error": f"Failed to get parameter: {str(e)}"}
        else:
            # Fall back to legacy approach
            legacy_success, legacy_value = await self.get_parameter_value(device, parameter)
            if legacy_success:
                return {
                    "device_id": device_id,
                    "parameter": parameter,
                    "value": legacy_value
                }
            else:
                return {"error": f"Parameter '{parameter}' not supported or could not be retrieved"}
    
    async def set_parameter(self, device_id: str, parameter: str, value: Any) -> Dict[str, Any]:
        """
        Set a parameter value for a device.
        
        Args:
            device_id: Device ID
            parameter: Parameter name
            value: Parameter value
            
        Returns:
            Dictionary with result of the operation
        """
        if not self.session:
            await self.start()
            
        # Get the device
        device = await self._get_device(device_id)
        if not device:
            return {"error": f"Device '{device_id}' not found"}
        
        # Try capabilities-based approach first
        capability = device_capabilities.get_capability_for_device(device)
        if capability and capability.has_parameter(parameter):
            # Get parameter details
            param_details = capability.get_parameter_details(parameter)
            
            # Convert value to the correct type
            value = self._convert_value(value, param_details.get("type", "string"))
            
            # Handle different device generations
            try:
                if capability.generation == "gen1":
                    result = await self._set_gen1_parameter(device, param_details, value)
                else:
                    result = await self._set_gen2_parameter(device, param_details, value)
                    
                # Update device if relevant parameter (like eco_mode)
                if parameter == "eco_mode":
                    device.eco_mode_enabled = bool(value)
                    device_registry.save_device(device)
                
                return {
                    "device_id": device_id,
                    "parameter": parameter,
                    "value": value,
                    "result": result
                }
            except Exception as e:
                logger.error(f"Error setting parameter '{parameter}' for device {device_id}: {e}")
                return {"error": f"Failed to set parameter: {str(e)}"}
        else:
            # Fall back to legacy approach
            legacy_success = await self.set_parameter_value(device, parameter, value)
            if legacy_success:
                return {
                    "device_id": device_id,
                    "parameter": parameter,
                    "value": value,
                    "success": True
                }
            else:
                return {"error": f"Parameter '{parameter}' not supported or could not be set"}
    
    async def apply_parameter(self, group_name: str, parameter: str, value: Any) -> Dict[str, Any]:
        """
        Apply a parameter to all devices in a group.
        
        Args:
            group_name: Name of the group
            parameter: Parameter name
            value: Parameter value
            
        Returns:
            Dictionary with results for each device
        """
        # Get the group
        group = self.group_manager.get_group(group_name)
        if not group:
            logger.error(f"Group '{group_name}' not found")
            return {"error": f"Group '{group_name}' not found"}
        
        # Get devices from storage or discovery service
        devices = await self.load_devices_for_group(group_name)
        
        if not devices:
            return {"error": f"No devices found in group '{group_name}'"}
        
        # Apply parameter to each device
        results = {}
        supported_count = 0
        success_count = 0
        
        for device in devices:
            device_id = device.id
            # Try to set the parameter
            capability = device_capabilities.get_capability_for_device(device)
            
            if capability and capability.has_parameter(parameter):
                supported_count += 1
                result = await self.set_parameter(device_id, parameter, value)
                results[device_id] = result
                
                if "error" not in result:
                    success_count += 1
            else:
                # Try legacy approach
                legacy_success = await self.set_parameter_value(device, parameter, value)
                if legacy_success:
                    supported_count += 1
                    success_count += 1
                    results[device_id] = {
                        "success": True,
                        "value": value
                    }
                else:
                    results[device_id] = {
                        "error": f"Parameter '{parameter}' not supported for this device"
                    }
        
        return {
            "group": group_name,
            "parameter": parameter,
            "value": value,
            "device_count": len(devices),
            "supported_count": supported_count,
            "success_count": success_count,
            "results": results
        }
    
    async def apply_parameter_to_group(self, group_name: str, parameter_name: str, value: Any) -> Dict[str, Any]:
        """
        Legacy method for applying parameter to a group - redirects to new apply_parameter method.
        
        Args:
            group_name: Name of the group
            parameter_name: Name of the parameter 
            value: Value to set
            
        Returns:
            Dictionary with operation results
        """
        return await self.apply_parameter(group_name, parameter_name, value)

    async def load_devices_for_group(self, group_name: str) -> List[Device]:
        """
        Load devices for a specific group from storage and probe them to update.
        
        Args:
            group_name: Name of the group
            
        Returns:
            List of devices in the group
        """
        # Get the group
        group = self.group_manager.get_group(group_name)
        if not group:
            logger.error(f"Group '{group_name}' not found")
            return []
        
        # Load devices
        devices = []
        for device_id in group.device_ids:
            device = await self._get_device(device_id)
            if device:
                devices.append(device)
            else:
                logger.warning(f"Device {device_id} not found")
        
        # Probe devices to update their information
        if devices:
            await self._probe_devices(devices)
        
        return devices
    
    async def _probe_devices(self, devices: List[Device]):
        """
        Probe devices to update their information.
        
        Args:
            devices: List of devices to probe
        """
        if not self.session:
            await self.start()
        
        # Create tasks for each device
        tasks = []
        for device in devices:
            # Skip devices with no IP address
            if not device.ip_address:
                logger.warning(f"Device {device.id} has no IP address, skipping")
                continue
                
            # Use capability-based probing if possible
            capability = device_capabilities.get_capability_for_device(device)
            if capability:
                if capability.generation == "gen1":
                    tasks.append(self._probe_gen1_device(device))
                else:
                    tasks.append(self._probe_gen2_device(device))
            else:
                # Fall back to generation-based probing
                if device.generation == DeviceGeneration.GEN1:
                    tasks.append(self._probe_gen1_device(device))
                else:
                    tasks.append(self._probe_gen2_device(device))
        
        # Wait for all tasks to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _probe_gen1_device(self, device: Device):
        """
        Probe a Gen1 device to update its information.
        
        Args:
            device: The device to probe
        """
        try:
            # Query settings
            settings_url = f"http://{device.ip_address}/settings"
            async with self.session.get(settings_url, timeout=self.http_timeout) as response:
                if response.status == 200:
                    settings = await response.json()
                    
                    # Update device information
                    if "device" in settings:
                        device.name = settings["device"].get("hostname", device.name)
                        device.firmware_version = settings["device"].get("fw_version", device.firmware_version)
                    
                    # Update eco mode status
                    device.eco_mode_enabled = settings.get("eco_mode", False)
                    
                    # Save device
                    device_registry.save_device(device)
                    
                    logger.debug(f"Successfully probed Gen1 device {device.id}")
                else:
                    logger.warning(f"HTTP error {response.status} probing Gen1 device {device.id}")
        except Exception as e:
            logger.error(f"Error probing Gen1 device {device.id}: {str(e)}")
    
    async def _probe_gen2_device(self, device: Device):
        """
        Probe a Gen2 device to update its information.
        
        Args:
            device: The device to probe
        """
        try:
            # Query config
            config_url = f"http://{device.ip_address}/rpc"
            config_payload = {
                "id": 1,
                "src": "shelly-bulk-control",
                "method": "Shelly.GetConfig",
                "params": {}
            }
            
            async with self.session.post(config_url, json=config_payload, timeout=self.http_timeout) as response:
                if response.status == 200:
                    config_data = await response.json()
                    
                    if "result" in config_data:
                        config = config_data["result"]
                        
                        # Update device information
                        if "sys" in config:
                            device.name = config["sys"].get("name", device.name)
                            
                            # Update eco mode status
                            device.eco_mode_enabled = config["sys"].get("device", {}).get("eco_mode", False)
                        
                        # Save device
                        device_registry.save_device(device)
                        
                        logger.debug(f"Successfully probed Gen2 device {device.id}")
                else:
                    logger.warning(f"HTTP error {response.status} probing Gen2 device {device.id}")
        except Exception as e:
            logger.error(f"Error probing Gen2 device {device.id}: {str(e)}")
    
    async def get_parameter_value(self, device: Device, parameter_name: str) -> Tuple[bool, Any]:
        """
        Legacy method to get the current value of a parameter.
        
        Args:
            device: The device to get the parameter from
            parameter_name: The name of the parameter
            
        Returns:
            Tuple of (success, value)
        """
        if not self.session:
            await self.start()
            
        # Get parameter definition
        parameters = self.get_device_parameters(device)
        if parameter_name not in parameters:
            logger.warning(f"Parameter '{parameter_name}' not defined for device {device.id}")
            return False, None
            
        parameter = parameters[parameter_name]
        
        try:
            if device.generation == DeviceGeneration.GEN1:
                return await self._get_gen1_parameter_legacy(device, parameter)
            else:
                return await self._get_gen2_parameter_legacy(device, parameter)
        except Exception as e:
            logger.error(f"Error getting parameter '{parameter_name}' from device {device.id}: {str(e)}")
            return False, None
    
    async def _get_gen1_parameter_legacy(self, device: Device, parameter: ParameterDefinition) -> Tuple[bool, Any]:
        """
        Legacy method to get a parameter value from a Gen1 device.
        
        Args:
            device: The Gen1 device
            parameter: Parameter definition
            
        Returns:
            Tuple of (success, value)
        """
        if not parameter.gen1_endpoint or not parameter.gen1_property:
            logger.warning(f"Parameter '{parameter.name}' does not have Gen1 mapping")
            return False, None
        
        # Build URL
        url = f"http://{device.ip_address}/{parameter.gen1_endpoint}"
        
        try:
            async with self.session.get(url, timeout=self.http_timeout) as response:
                if response.status == 200:
                    response_data = await response.json()
                    
                    # Extract property, which might be nested
                    value = response_data
                    for prop in parameter.gen1_property.split('.'):
                        if prop not in value:
                            return False, None
                        value = value[prop]
                    
                    # Handle boolean conversion for Gen1 devices which might use "on"/"off"
                    if parameter.parameter_type.name == "BOOLEAN" and isinstance(value, str):
                        value = value.lower() == "on" or value.lower() == "true"
                    
                    return True, value
                else:
                    logger.warning(f"HTTP error {response.status} getting parameter from {device.id}")
                    return False, None
        except Exception as e:
            logger.error(f"Error getting Gen1 parameter: {str(e)}")
            return False, None
    
    async def _get_gen2_parameter_legacy(self, device: Device, parameter: ParameterDefinition) -> Tuple[bool, Any]:
        """
        Legacy method to get a parameter value from a Gen2 device.
        
        Args:
            device: The Gen2 device
            parameter: Parameter definition
            
        Returns:
            Tuple of (success, value)
        """
        if not parameter.gen2_method or not parameter.gen2_component or not parameter.gen2_property:
            logger.warning(f"Parameter '{parameter.name}' does not have Gen2 mapping")
            return False, None
        
        # We need to use Shelly.GetConfig for getting configuration values
        method = "Shelly.GetConfig"
        
        # Build URL and payload
        url = f"http://{device.ip_address}/rpc"
        payload = {
            "id": 1,
            "src": "shelly-bulk-control",
            "method": method,
            "params": {}
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=self.http_timeout) as response:
                if response.status == 200:
                    response_data = await response.json()
                    
                    if "error" in response_data:
                        logger.warning(f"RPC error getting parameter from {device.id}: {response_data['error']}")
                        return False, None
                    
                    # Extract value from component and property
                    if "result" not in response_data:
                        return False, None
                    
                    result = response_data["result"]
                    if parameter.gen2_component not in result:
                        return False, None
                    
                    component = result[parameter.gen2_component]
                    
                    # Extract property, which might be nested
                    value = component
                    for prop in parameter.gen2_property.split('.'):
                        if prop not in value:
                            return False, None
                        value = value[prop]
                    
                    return True, value
                else:
                    logger.warning(f"HTTP error {response.status} getting parameter from {device.id}")
                    return False, None
        except Exception as e:
            logger.error(f"Error getting Gen2 parameter: {str(e)}")
            return False, None
    
    async def set_parameter_value(self, device: Device, parameter_name: str, value: Any) -> bool:
        """
        Legacy method to set a parameter value on a device.
        
        Args:
            device: The device to set the parameter on
            parameter_name: The name of the parameter
            value: The value to set
            
        Returns:
            True if successful, False otherwise
        """
        if not self.session:
            await self.start()
            
        # Get parameter definition
        parameters = self.get_device_parameters(device)
        if parameter_name not in parameters:
            logger.warning(f"Parameter '{parameter_name}' not defined for device {device.id}")
            return False
            
        parameter = parameters[parameter_name]
        
        # Validate the value if validation method exists
        if hasattr(parameter, 'validate_value') and callable(parameter.validate_value):
            if not parameter.validate_value(value):
                logger.warning(f"Invalid value for parameter '{parameter_name}': {value}")
                return False
            
        try:
            if device.generation == DeviceGeneration.GEN1:
                return await self._set_gen1_parameter_legacy(device, parameter, value)
            else:
                return await self._set_gen2_parameter_legacy(device, parameter, value)
        except Exception as e:
            logger.error(f"Error setting parameter '{parameter_name}' on device {device.id}: {str(e)}")
            return False
    
    async def _set_gen1_parameter_legacy(self, device: Device, parameter: ParameterDefinition, value: Any) -> bool:
        """
        Legacy method to set a parameter value on a Gen1 device.
        
        Args:
            device: The Gen1 device
            parameter: Parameter definition
            value: The value to set
            
        Returns:
            True if successful, False otherwise
        """
        if not parameter.gen1_endpoint or not parameter.gen1_property:
            logger.warning(f"Parameter '{parameter.name}' does not have Gen1 mapping")
            return False
        
        # Format the value for Gen1 API
        if hasattr(parameter, 'format_value_for_gen1') and callable(parameter.format_value_for_gen1):
            formatted_value = parameter.format_value_for_gen1(value)
        elif parameter.parameter_type.name == "BOOLEAN":
            formatted_value = "on" if value else "off"
        else:
            formatted_value = value
        
        # Build URL
        url = f"http://{device.ip_address}/{parameter.gen1_endpoint}?{parameter.gen1_property}={formatted_value}"
        
        try:
            async with self.session.get(url, timeout=self.http_timeout) as response:
                if response.status == 200:
                    response_data = await response.json()
                    logger.debug(f"Successfully set parameter '{parameter.name}' on Gen1 device {device.id}")
                    return True
                else:
                    logger.warning(f"HTTP error {response.status} setting parameter on {device.id}")
                    return False
        except Exception as e:
            logger.error(f"Error setting Gen1 parameter: {str(e)}")
            return False
    
    async def _set_gen2_parameter_legacy(self, device: Device, parameter: ParameterDefinition, value: Any) -> bool:
        """
        Legacy method to set a parameter value on a Gen2 device.
        
        Args:
            device: The Gen2 device
            parameter: Parameter definition
            value: The value to set
            
        Returns:
            True if successful, False otherwise
        """
        if not parameter.gen2_method or not parameter.gen2_component or not parameter.gen2_property:
            logger.warning(f"Parameter '{parameter.name}' does not have Gen2 mapping")
            return False
        
        # Format the value for Gen2 API
        if hasattr(parameter, 'format_value_for_gen2') and callable(parameter.format_value_for_gen2):
            formatted_value = parameter.format_value_for_gen2(value)
        else:
            formatted_value = value
        
        # Build URL and payload
        url = f"http://{device.ip_address}/rpc"
        
        # For nested properties, build the config object
        config = {}
        props = parameter.gen2_property.split('.')
        
        # Handle nested properties by building a nested object
        if len(props) == 1:
            # Simple case, just one level
            config[props[0]] = formatted_value
        else:
            # Build nested object
            current = config
            for i, prop in enumerate(props[:-1]):
                current[prop] = {}
                current = current[prop]
            current[props[-1]] = formatted_value
        
        payload = {
            "id": 1,
            "src": "shelly-bulk-control",
            "method": parameter.gen2_method,
            "params": {
                "config": {
                    parameter.gen2_component: config
                }
            }
        }
        
        try:
            async with self.session.post(url, json=payload, timeout=self.http_timeout) as response:
                if response.status == 200:
                    response_data = await response.json()
                    
                    if "error" in response_data:
                        logger.warning(f"RPC error setting parameter on {device.id}: {response_data['error']}")
                        return False
                    
                    logger.debug(f"Successfully set parameter '{parameter.name}' on Gen2 device {device.id}")
                    
                    # Update eco mode status if this was the parameter being set
                    if parameter.name == "eco_mode":
                        device.eco_mode_enabled = value
                        device_registry.save_device(device)
                    
                    return True
                else:
                    logger.warning(f"HTTP error {response.status} setting parameter on {device.id}")
                    return False
        except Exception as e:
            logger.error(f"Error setting Gen2 parameter: {str(e)}")
            return False

    async def _get_gen1_parameter(self, device: Device, param_details: Dict[str, Any]) -> Any:
        """
        Get a parameter value from a Gen1 device using capabilities approach.
        
        Args:
            device: Device to get parameter from
            param_details: Parameter details
            
        Returns:
            Parameter value
        """
        if not device.ip_address:
            raise ValueError(f"Device {device.id} has no IP address")
        
        # Gen1 devices use HTTP GET endpoints
        param_path = param_details.get("parameter_path", "")
        api = param_details.get("api", "")
        
        # Build the endpoint URL based on the API
        if api == "settings":
            endpoint = "/settings"
        elif api == "status":
            endpoint = "/status"
        else:
            endpoint = f"/{api}"
        
        # Make the request
        url = f"http://{device.ip_address}{endpoint}"
        async with self.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                
                # Navigate to the parameter in the response
                path_parts = param_path.split(".")
                value = data
                for part in path_parts:
                    if part in value:
                        value = value[part]
                    else:
                        raise ValueError(f"Path '{param_path}' not found in response")
                
                return value
            else:
                raise ValueError(f"HTTP error {response.status}: {await response.text()}")
    
    async def _set_gen1_parameter(self, device: Device, param_details: Dict[str, Any], value: Any) -> Dict[str, Any]:
        """
        Set a parameter value on a Gen1 device using capabilities approach.
        
        Args:
            device: Device to set parameter on
            param_details: Parameter details
            value: Parameter value
            
        Returns:
            Result of the operation
        """
        if not device.ip_address:
            raise ValueError(f"Device {device.id} has no IP address")
        
        # Gen1 devices use HTTP GET for setting parameters (with query parameters)
        param_path = param_details.get("parameter_path", "")
        api = param_details.get("api", "")
        
        # Build the endpoint URL based on the API
        if api == "settings":
            endpoint = "/settings"
        else:
            endpoint = f"/{api}"
        
        # Build query parameters
        params = {}
        path_parts = param_path.split(".")
        
        # Construct nested parameters (e.g., "mqtt.enable" becomes {"mqtt": {"enable": value}})
        if len(path_parts) > 1:
            # Build the nested structure
            current = params
            for i, part in enumerate(path_parts[:-1]):
                current[part] = {}
                current = current[part]
            current[path_parts[-1]] = value
        else:
            # Simple parameter
            params[param_path] = value
        
        # Flatten nested params for Gen1 devices
        flat_params = self._flatten_params(params)
        
        # Make the request
        url = f"http://{device.ip_address}{endpoint}"
        async with self.session.get(url, params=flat_params) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                raise ValueError(f"HTTP error {response.status}: {await response.text()}")
    
    async def _get_gen2_parameter(self, device: Device, param_details: Dict[str, Any]) -> Any:
        """
        Get a parameter value from a Gen2/Gen3 device using capabilities approach.
        
        Args:
            device: Device to get parameter from
            param_details: Parameter details
            
        Returns:
            Parameter value
        """
        if not device.ip_address:
            raise ValueError(f"Device {device.id} has no IP address")
        
        # Gen2/Gen3 devices use RPC API
        param_path = param_details.get("parameter_path", "")
        api = param_details.get("api", "")
        
        # Convert SetConfig method to GetConfig for fetching
        get_api = api.replace("Set", "Get")
        
        # Make the request
        url = f"http://{device.ip_address}/rpc/{get_api}"
        async with self.session.post(url, json={}) as response:
            if response.status == 200:
                data = await response.json()
                
                # Navigate to the parameter in the response
                path_parts = param_path.split(".")
                value = data
                for part in path_parts:
                    if part in value:
                        value = value[part]
                    else:
                        raise ValueError(f"Path '{param_path}' not found in response")
                
                return value
            else:
                raise ValueError(f"HTTP error {response.status}: {await response.text()}")
    
    async def _set_gen2_parameter(self, device: Device, param_details: Dict[str, Any], value: Any) -> Dict[str, Any]:
        """
        Set a parameter value on a Gen2/Gen3 device using capabilities approach.
        
        Args:
            device: Device to set parameter on
            param_details: Parameter details
            value: Parameter value
            
        Returns:
            Result of the operation
        """
        if not device.ip_address:
            raise ValueError(f"Device {device.id} has no IP address")
        
        # Gen2/Gen3 devices use RPC API
        param_path = param_details.get("parameter_path", "")
        api = param_details.get("api", "")
        
        # Special handling for action parameters (like switch_output)
        if param_details.get("action", False):
            target = param_details.get("target", "")
            if not target:
                raise ValueError("No target specified for action parameter")
            
            # Action parameters use a different format
            params = {
                "id": int(target.split(":")[1]) if ":" in target else 0,
                param_path: value
            }
        else:
            # Build the params object based on the parameter path
            params = {}
            path_parts = param_path.split(".")
            
            # Construct nested parameters (e.g., "device.eco_mode" becomes {"device": {"eco_mode": value}})
            if len(path_parts) > 1:
                # Build the nested structure
                current = params
                for i, part in enumerate(path_parts[:-1]):
                    current[part] = {}
                    current = current[part]
                current[path_parts[-1]] = value
            else:
                # Simple parameter
                params[param_path] = value
        
        # Make the request
        url = f"http://{device.ip_address}/rpc/{api}"
        async with self.session.post(url, json=params) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                raise ValueError(f"HTTP error {response.status}: {await response.text()}")
    
    async def _get_device(self, device_id: str) -> Optional[Device]:
        """
        Get a device by ID, either from registry, cache, or discovery.
        
        Args:
            device_id: Device ID to get
            
        Returns:
            Device if found, None otherwise
        """
        # Check cache first
        if device_id in self._device_cache:
            return self._device_cache[device_id]
            
        # Then try from registry
        device = device_registry.get_device(device_id)
        if device:
            # Cache for future use
            self._device_cache[device_id] = device
            return device
            
        # If not found and we have discovery service, try to discover
        if not device and self.discovery_service:
            # Look for the device using discovery service
            logger.debug(f"Device {device_id} not found in registry, attempting discovery")
            
            # Try to find the device by ID
            await self.discovery_service.start()
            devices = await self.discovery_service.discover_devices()
            for d in devices:
                if d.id == device_id:
                    device = d
                    device_registry.save_device(device)  # Save for future reference
                    self._device_cache[device_id] = device  # Cache for future use
                    break
        
        return device
    
    def _convert_value(self, value: Any, type_name: str) -> Any:
        """
        Convert a value to the correct type.
        
        Args:
            value: Value to convert
            type_name: Type name to convert to
            
        Returns:
            Converted value
        """
        if type_name == "boolean":
            if isinstance(value, bool):
                return value
            return value.lower() in ("true", "yes", "1", "t", "y")
        elif type_name == "integer":
            return int(value)
        elif type_name == "float" or type_name == "number":
            return float(value)
        else:
            return str(value)
    
    def _flatten_params(self, params: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
        """
        Flatten nested parameters for Gen1 devices.
        
        Args:
            params: Nested parameters
            prefix: Prefix for keys
            
        Returns:
            Flattened parameters
        """
        result = {}
        for key, value in params.items():
            new_key = f"{prefix}{key}" if prefix else key
            if isinstance(value, dict):
                # Recursively flatten nested dictionaries
                nested = self._flatten_params(value, f"{new_key}.")
                result.update(nested)
            else:
                # Add leaf values
                result[new_key] = str(value)
        return result 