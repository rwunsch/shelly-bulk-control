"""
Device capabilities management for Shelly devices.

This module provides classes for loading, querying, and discovering
the capabilities of different Shelly device types. It helps determine
which APIs, parameters, and settings are available for each device model.
"""
from typing import Dict, List, Any, Optional, Set
import os
import yaml
import json
import logging
from pathlib import Path
import aiohttp
import asyncio

from ..utils.logging import get_logger
from .device import Device, DeviceGeneration
from .parameter_mapping import ParameterMapper

# Get logger for this module
logger = get_logger(__name__)

class DeviceCapability:
    """
    Represents the capabilities of a specific device type.
    
    This includes the APIs it supports, parameters it accepts,
    and the data structure of its responses.
    """
    
    def __init__(self, 
                 device_type: str, 
                 name: str, 
                 generation: str,
                 data: Dict[str, Any] = None):
        """
        Initialize device capability.
        
        Args:
            device_type: Identifier for the device type (e.g., "Plus1PMMini")
            name: Human-readable name (e.g., "Shelly Plus 1PM Mini")
            generation: Device generation (gen1, gen2, gen3)
            data: Full capability data including APIs, parameters, etc.
        """
        self.device_type = device_type
        self.name = name
        self.generation = generation
        self.data = data or {}
        self.apis = self.data.get("apis", {})
        self.parameters = self.data.get("parameters", {})
    
    @property
    def supports_api(self) -> Set[str]:
        """Get a set of supported API endpoints."""
        return set(self.apis.keys())
    
    def has_api(self, api_name: str) -> bool:
        """
        Check if this device supports a specific API.
        
        Args:
            api_name: Name of the API to check (e.g., "Shelly.GetStatus")
            
        Returns:
            True if supported, False otherwise
        """
        return api_name in self.apis
    
    def get_api_details(self, api_name: str) -> Optional[Dict[str, Any]]:
        """
        Get details about a specific API.
        
        Args:
            api_name: Name of the API
            
        Returns:
            API details if found, None otherwise
        """
        return self.apis.get(api_name)
    
    def has_parameter(self, param_name: str) -> bool:
        """
        Check if this device supports a specific parameter.
        
        Args:
            param_name: Name of the parameter (e.g., "eco_mode")
            
        Returns:
            True if the parameter is supported, False otherwise
        """
        # First try direct parameter name
        if param_name in self.parameters:
            return True
            
        # For Gen1 devices, check mapped parameter name
        if self.generation == "gen1":
            gen1_param = ParameterMapper.to_gen1_parameter(param_name)
            return gen1_param in self.parameters
        
        return False
    
    def get_parameter_details(self, param_name: str) -> Optional[Dict[str, Any]]:
        """
        Get details about a specific parameter.
        
        Args:
            param_name: Name of the parameter
            
        Returns:
            Parameter details if found, None otherwise
        """
        # First try direct parameter name
        if param_name in self.parameters:
            return self.parameters.get(param_name)
            
        # For Gen1 devices, check mapped parameter name
        if self.generation == "gen1":
            gen1_param = ParameterMapper.to_gen1_parameter(param_name)
            if gen1_param in self.parameters:
                details = self.parameters.get(gen1_param).copy()
                # Add mapping information for reference
                details["mapped_from"] = param_name
                return details
        
        return None
    
    def get_parameter_api(self, param_name: str) -> Optional[str]:
        """
        Get the API endpoint used to set a specific parameter.
        
        Args:
            param_name: Name of the parameter
            
        Returns:
            API endpoint name if found, None otherwise
        """
        param_details = self.get_parameter_details(param_name)
        if param_details:
            return param_details.get("api")
        return None
        
    def get_writable_parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all writable parameters for this device.
        
        Returns:
            Dictionary of writable parameters and their details
        """
        return {name: details for name, details in self.parameters.items() 
                if not details.get("read_only", True)}
    
    def get_readable_parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all readable parameters for this device.
        
        Returns:
            Dictionary of readable parameters and their details
        """
        return self.parameters

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert capability to dictionary.
        
        Returns:
            Dictionary representation of capability
        """
        result = {
            "device_type": self.device_type,  # Use device_type consistently
            "id": self.device_type,           # Keep id for backward compatibility
            "name": self.name,
            "generation": self.generation,
            "apis": self.apis,
            "parameters": self.parameters
        }
        
        # Include type_mappings if present
        if "type_mappings" in self.data:
            result["type_mappings"] = self.data["type_mappings"]
            
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeviceCapability':
        """
        Create a capability instance from a dictionary.
        
        Args:
            data: Dictionary containing capability data
            
        Returns:
            DeviceCapability instance
        """
        # Support both 'id' and 'device_type' field names for compatibility
        device_type = data.get("device_type", data.get("id"))
        
        return cls(
            device_type=device_type,
            name=data.get("name"),
            generation=data.get("generation"),
            data=data
        )


class DeviceCapabilities:
    """
    Manages device capabilities for all known Shelly device types.
    
    This class is responsible for loading capability definitions from files,
    matching devices to their capabilities, and providing an interface to
    query capabilities.
    """
    
    def __init__(self, capabilities_dir: str = "config/device_capabilities"):
        """
        Initialize the capability manager.
        
        Args:
            capabilities_dir: Directory where capability files are stored
        """
        self.capabilities_dir = Path(capabilities_dir)
        self.capabilities: Dict[str, DeviceCapability] = {}
        self._type_to_capability: Dict[str, str] = {}  # Maps raw_type/raw_app to capability ID
        
        # Create directory if it doesn't exist
        os.makedirs(self.capabilities_dir, exist_ok=True)
        
        # Load all device capabilities
        self.load_all_capabilities()
    
    def load_all_capabilities(self) -> None:
        """Load all capability definitions from files."""
        self.capabilities = {}
        self._type_to_capability = {}
        loaded_count = 0
        
        if not os.path.exists(self.capabilities_dir):
            logger.debug(f"Capabilities directory {self.capabilities_dir} does not exist, creating")
            os.makedirs(self.capabilities_dir, exist_ok=True)
            return
        
        # Iterate through all YAML files in the directory
        for file_path in self.capabilities_dir.glob("*.yaml"):
            try:
                logger.debug(f"Loading capability from {file_path}")
                with open(file_path, 'r') as f:
                    try:
                        capability_data = yaml.safe_load(f)
                    except yaml.YAMLError as e:
                        logger.error(f"Failed to parse YAML in {file_path}: {e}")
                        continue
                
                if capability_data and "device_type" in capability_data:
                    # Create capability object
                    capability = DeviceCapability.from_dict(capability_data)
                    
                    # Add to capabilities dictionary
                    self.capabilities[capability.device_type] = capability
                    
                    # Add type mappings
                    if "type_mappings" in capability_data and isinstance(capability_data["type_mappings"], list):
                        for mapping in capability_data["type_mappings"]:
                            self._type_to_capability[mapping] = capability.device_type
                            logger.debug(f"Added mapping: {mapping} -> {capability.device_type}")
                    else:
                        logger.warning(f"No type_mappings found in {file_path}")
                    
                    loaded_count += 1
                    logger.debug(f"Loaded capability definition for {capability.device_type} from {file_path}")
                else:
                    logger.warning(f"Invalid capability data in file: {file_path}")
            
            except Exception as e:
                logger.error(f"Failed to load capability from {file_path}: {e}")
        
        logger.info(f"Loaded {loaded_count} device capability definitions")
        logger.debug(f"Capability mappings: {self._type_to_capability}")
    
    def get_capability_for_device(self, device: Device) -> Optional[DeviceCapability]:
        """
        Get capability definition for a specific device.
        
        Args:
            device: Device to get capabilities for
            
        Returns:
            DeviceCapability if found, None otherwise
        """
        logger.debug(f"Finding capability for device {device.id} (type={device.raw_type}, app={device.raw_app})")
        
        # First, try to map by explicit type
        if device.raw_type and device.raw_type in self._type_to_capability:
            cap_id = self._type_to_capability[device.raw_type]
            logger.debug(f"Found capability {cap_id} via raw_type '{device.raw_type}'")
            return self.capabilities.get(cap_id)
        
        # For Gen2/Gen3, try by raw_app
        if device.raw_app and device.raw_app in self._type_to_capability:
            cap_id = self._type_to_capability[device.raw_app]
            logger.debug(f"Found capability {cap_id} via raw_app '{device.raw_app}'")
            return self.capabilities.get(cap_id)
        
        # Try by device ID prefix (like "shellyplus1pmmini")
        if device.id:
            for prefix, cap_id in self._type_to_capability.items():
                if device.id.lower().startswith(prefix.lower()):
                    logger.debug(f"Found capability {cap_id} via ID prefix match '{prefix}'")
                    return self.capabilities.get(cap_id)
        
        logger.warning(f"No capability definition found for device {device.id} "
                     f"(type={device.raw_type}, app={device.raw_app})")
        logger.debug(f"Available mappings: {self._type_to_capability}")
        return None
    
    def get_capability(self, capability_id: str) -> Optional[DeviceCapability]:
        """
        Get capability by ID.
        
        Args:
            capability_id: ID of the capability to retrieve
            
        Returns:
            DeviceCapability if found, None otherwise
        """
        return self.capabilities.get(capability_id)
    
    def save_capability(self, capability: DeviceCapability) -> bool:
        """
        Save a capability definition to a file.
        
        Args:
            capability: DeviceCapability to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Make sure the directory exists
            os.makedirs(self.capabilities_dir, exist_ok=True)
            
            # Convert capability to dictionary
            capability_data = capability.to_dict()
            
            # Create filename
            filename = f"{capability.device_type}.yaml"
            filepath = self.capabilities_dir / filename
            
            # Save to file
            with open(filepath, 'w') as f:
                yaml.dump(capability_data, f, default_flow_style=False, sort_keys=False)
            
            # Update in-memory cache
            self.capabilities[capability.device_type] = capability
            
            # Update type mapping
            if "type_mappings" in capability_data:
                logger.debug(f"Processing type mappings for {capability.device_type}: {capability_data['type_mappings']}")
                for mapping in capability_data["type_mappings"]:
                    self._type_to_capability[mapping] = capability.device_type
                    logger.debug(f"Updated mapping: {mapping} -> {capability.device_type}")
            else:
                # Ensure we at least map the device type to itself
                self._type_to_capability[capability.device_type] = capability.device_type
                logger.debug(f"Added default mapping: {capability.device_type} -> {capability.device_type}")
            
            logger.debug(f"Saved capability definition for {capability.device_type} to {filepath}")
            logger.debug(f"Updated type mappings: {self._type_to_capability}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save capability for {capability.device_type}: {e}")
            return False


class CapabilityDiscovery:
    """
    Discovers and extracts device capabilities from live Shelly devices.
    
    This class can probe a device using its API to determine what
    features and parameters it supports, then generate a capability definition.
    """
    
    def __init__(self, capabilities_manager: DeviceCapabilities):
        """
        Initialize the capability discovery.
        
        Args:
            capabilities_manager: DeviceCapabilities instance to store discovered capabilities
        """
        self.capabilities_manager = capabilities_manager
        self.http_timeout = 5  # seconds
    
    async def discover_device_capabilities(self, device: Device) -> Optional[DeviceCapability]:
        """
        Probe a device to discover its capabilities.
        
        Args:
            device: Device to probe
            
        Returns:
            DeviceCapability if successful, None otherwise
        """
        if not device.ip_address:
            logger.error(f"Cannot discover capabilities: Device {device.id} has no IP address")
            return None
        
        try:
            # Determine device type and create capability object
            device_type = self._get_device_type_id(device)
            logger.info(f"Discovering capabilities for {device.id} as type {device_type}")
            
            capability = DeviceCapability(
                device_type=device_type,
                name=device.device_name or f"Shelly {device_type}",
                generation=str(device.generation).lower(),
                data={
                    "apis": {},
                    "parameters": {},
                    "type_mappings": []
                }
            )
            
            # Add mappings for device lookup
            if device.raw_type:
                capability.data["type_mappings"].append(device.raw_type)
                logger.debug(f"Added type mapping from raw_type: {device.raw_type}")
                
            if device.raw_app:
                capability.data["type_mappings"].append(device.raw_app)
                logger.debug(f"Added type mapping from raw_app: {device.raw_app}")
                
            # Extract generic device type from ID if needed (e.g. "shellyplug1pm" from "shellyplug1pm-abc123")
            if device.id and "-" in device.id:
                device_type_prefix = device.id.split('-')[0]
                if (device_type_prefix.lower() not in [m.lower() for m in capability.data["type_mappings"]] and
                    not any(char.isdigit() for char in device_type_prefix)):  # Avoid adding specific identifiers with digits
                    capability.data["type_mappings"].append(device_type_prefix.lower())
                    logger.debug(f"Added type mapping from ID prefix: {device_type_prefix.lower()}")
            
            # Gen1 devices use different APIs than Gen2/Gen3
            if device.generation == DeviceGeneration.GEN1:
                await self._discover_gen1_capabilities(device, capability)
            else:
                await self._discover_gen2_capabilities(device, capability)
            
            # Save the discovered capability
            logger.info(f"Saving discovered capability for {device.id} with mappings: {capability.data['type_mappings']}")
            self.capabilities_manager.save_capability(capability)
            
            return capability
            
        except Exception as e:
            logger.error(f"Error discovering capabilities for {device.id}: {e}")
            return None
    
    def _get_device_type_id(self, device: Device) -> str:
        """
        Determine the device type ID for a device.
        
        Args:
            device: Device to determine type for
            
        Returns:
            Device type ID string
        """
        # For Gen1 devices, use the raw_type
        if device.generation == DeviceGeneration.GEN1:
            if device.raw_type:
                return device.raw_type
        
        # For Gen2/Gen3 devices
        elif device.raw_app:
            return device.raw_app
        
        # Fallback: Extract from device ID
        if device.id and "-" in device.id:
            return device.id.split("-")[0]
        
        # Last resort: use the MAC address
        return f"unknown_{device.mac_address.replace(':', '')}"
    
    async def _discover_gen1_capabilities(self, device: Device, capability: DeviceCapability) -> None:
        """
        Discover capabilities for a Gen1 device.
        
        Args:
            device: Device to probe
            capability: DeviceCapability to update
        """
        # Gen1 Shelly devices have a different API structure
        apis = capability.data["apis"]
        parameters = capability.data["parameters"]
        
        # Expanded list of Gen1 endpoints to probe
        endpoints = [
            "/settings", "/status", "/shelly",
            # Add more core endpoints
            "/settings/actions", "/settings/ap", "/settings/light",
            "/settings/login", "/settings/mqtt", "/settings/network",
            # Add relay endpoints dynamically based on device outputs
            *[f"/settings/relay/{i}" for i in range(getattr(device, 'num_outputs', 1) or 1)],
            # Add meter endpoints
            *[f"/status/meters/{i}" for i in range(getattr(device, 'num_meters', 0) or 0)],
            # Add other potential endpoints
            "/settings/cloud", "/settings/device", "/settings/webhooks"
        ]
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.http_timeout)) as session:
            for endpoint in endpoints:
                try:
                    # Try to fetch the endpoint
                    url = f"http://{device.ip_address}{endpoint}"
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Store the endpoint and its response structure
                            api_name = endpoint.lstrip('/')
                            apis[api_name] = {
                                "description": f"Gen1 API endpoint: {api_name}",
                                "response_structure": self._parse_structure(data)
                            }
                            
                            # Extract ALL parameters from response
                            self._extract_all_gen1_parameters(data, parameters, api_name)
                except Exception as e:
                    logger.debug(f"Error probing Gen1 endpoint {endpoint} for {device.id}: {e}")
    
    def _extract_all_gen1_parameters(self, data: Dict[str, Any], parameters: Dict[str, Any], api_name: str) -> None:
        """
        Extract all parameters recursively from a Gen1 JSON response.
        
        Args:
            data: JSON response data
            parameters: Parameters dictionary to update
            api_name: API endpoint name
        """
        self._extract_parameters_recursive(data, parameters, api_name, "", [])
    
    def _extract_parameters_recursive(self, data: Dict[str, Any], parameters: Dict[str, Any], 
                                     api_name: str, path_prefix: str, path_parts: List[str]) -> None:
        """
        Recursively extract parameters from nested JSON data.
        
        Args:
            data: JSON data to extract parameters from
            parameters: Parameters dictionary to update
            api_name: API endpoint name
            path_prefix: Current path prefix for parameter paths
            path_parts: Current path parts list
        """
        if not isinstance(data, dict):
            return
            
        for key, value in data.items():
            current_path = path_prefix + ("." if path_prefix else "") + key
            current_parts = path_parts + [key]
            
            # Skip only internal fields that start with underscores
            # Don't skip wifi_sta and other fields as they may contain important parameters
            if key.startswith("_"):
                continue
                
            # Determine parameter type
            param_type = self._infer_parameter_type(value)
            
            # For any value (not just non-objects), register as potential parameter
            # Create parameter entry if it doesn't exist
            param_name = current_path.replace(".", "_")  # Use underscores for dots in parameter names
            
            # Check if parameter already exists
            if param_name not in parameters:
                # Determine if this parameter is likely writable
                is_read_only = self._is_likely_read_only(current_parts, param_type)
                
                # For settings APIs, many parameters are writable unless explicitly marked as read-only
                if "settings" in api_name and not is_read_only:
                    is_read_only = False
                
                parameters[param_name] = {
                    "type": param_type,
                    "description": f"Parameter {current_path}",
                    "api": api_name,
                    "parameter_path": current_path,
                    "read_only": is_read_only
                }
            
            # For objects, recurse to extract nested parameters
            if isinstance(value, dict):
                self._extract_parameters_recursive(value, parameters, api_name, current_path, current_parts)
            # For arrays, only extract if they contain objects
            elif isinstance(value, list) and value and isinstance(value[0], dict):
                # For the first item in the array as an example
                self._extract_parameters_recursive(value[0], parameters, api_name, current_path + "[0]", current_parts + ["[0]"])
    
    def _infer_parameter_type(self, value: Any) -> str:
        """
        Infer parameter type from value.
        
        Args:
            value: Value to infer type from
            
        Returns:
            String representing the parameter type
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "string"  # Default to string for unknown types
    
    def _is_likely_read_only(self, path_parts: List[str], param_type: str) -> bool:
        """
        Determine if a parameter is likely read-only based on its path and type.
        This is a heuristic approach that will be refined with actual testing.
        
        Args:
            path_parts: Parameter path parts
            param_type: Parameter type
            
        Returns:
            True if parameter is likely read-only, False otherwise
        """
        # Status endpoints are typically read-only data reporting
        if "status" in path_parts:
            return True
            
        # More precise read-only indicators - these are typically status/reporting values
        read_only_indicators = [
            "uptime", "timestamp", "ram", "fs", "has_update", 
            "current", "voltage", "power", "temperature", "humidity", 
            "energy", "total", "id", "mac", "serial", "fw_version",
            "time", "unixtime", "temperature", "overtemperature", "ttot"
        ]
        
        # Check if any path part contains a read-only indicator
        if any(any(indicator in part.lower() for indicator in read_only_indicators) for part in path_parts):
            return True
            
        # Some parameters in config/settings are never writable
        never_writable_settings = [
            "fw", "cloud_enabled", "discovering", "debug_enable", "device_type",
            "build_id", "factory_reset", "uptime", "ram_free", "ram_total", 
            "ram_size", "fs_free", "fs_size", "available_updates"
        ]
        
        if any(part in never_writable_settings for part in path_parts):
            return True
            
        # Arrays are typically for status reporting, but we can inspect their content if needed
        if param_type == "array":
            return True
            
        # Objects need more context, but many are writable (e.g., wifi_sta, mqtt config)
        if param_type == "object":
            # Only settings objects that aren't in any of our lists might be writable
            pass
            
        # Default to assuming it's writable for parameters in settings endpoints
        # This allows more parameters to be discovered and tested
        return False
    
    async def _discover_gen2_capabilities(self, device: Device, capability: DeviceCapability) -> None:
        """
        Discover capabilities for a Gen2/Gen3 device.
        
        Args:
            device: Device to probe
            capability: DeviceCapability to update
        """
        # Gen2/Gen3 Shelly devices use RPC API
        apis = capability.data["apis"]
        parameters = capability.data["parameters"]
        
        # Expanded list of Gen2/Gen3 RPC methods to try
        rpc_methods = [
            # Core methods
            "Shelly.GetStatus", "Shelly.GetConfig",
            "Sys.GetStatus", "Sys.GetConfig",
            # Component-specific methods based on device type
            "Switch.GetStatus", "Switch.GetConfig",
            "Light.GetStatus", "Light.GetConfig",
            "Cloud.GetStatus", "Cloud.GetConfig",
            "MQTT.GetConfig", "WiFi.GetConfig",
            # Add more methods
            "Eth.GetConfig", "BLE.GetConfig", "Input.GetStatus", 
            "Cover.GetStatus", "Cover.GetConfig",
            "Script.List", "Schedule.List"
        ]
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.http_timeout)) as session:
            for method in rpc_methods:
                try:
                    # Try to call the RPC method
                    url = f"http://{device.ip_address}/rpc/{method}"
                    async with session.post(url, json={}) as response:
                        if response.status == 200:
                            data = await response.json()
                            
                            # Store the method and its response structure
                            apis[method] = {
                                "description": f"Gen2/Gen3 RPC method: {method}",
                                "response_structure": self._parse_structure(data)
                            }
                            
                            # Extract all parameters from config methods
                            if "GetConfig" in method:
                                component = method.split('.')[0].lower()
                                self._extract_all_gen2_parameters(method, data, parameters, component)
                except Exception as e:
                    logger.debug(f"Error calling RPC method {method} for {device.id}: {e}")
            
            # Try to discover eco mode specifically
            await self._check_gen2_eco_mode(device, session, parameters)
    
    def _extract_all_gen2_parameters(self, method: str, data: Dict[str, Any], 
                                   parameters: Dict[str, Any], component: str) -> None:
        """
        Extract all parameters from Gen2/Gen3 configuration data.
        
        Args:
            method: RPC method that was called
            data: JSON response data
            parameters: Parameters dictionary to update
            component: Component name (e.g., 'sys', 'mqtt')
        """
        # Determine the corresponding SetConfig method
        set_method = method.replace("Get", "Set")
        
        # Extract all parameters recursively
        self._extract_gen2_parameters_recursive(data, parameters, set_method, "", component)
    
    def _extract_gen2_parameters_recursive(self, data: Dict[str, Any], parameters: Dict[str, Any],
                                        api: str, path_prefix: str, component: str) -> None:
        """
        Recursively extract parameters from Gen2/Gen3 configuration data.
        
        Args:
            data: JSON data to extract parameters from
            parameters: Parameters dictionary to update
            api: API method name
            path_prefix: Current path prefix for parameter paths
            component: Component name
        """
        if not isinstance(data, dict):
            return
            
        for key, value in data.items():
            current_path = path_prefix + ("." if path_prefix else "") + key
            
            # Determine parameter type
            param_type = self._infer_parameter_type(value)
            
            # For non-objects, register as parameter
            if param_type != "object" or not isinstance(value, dict):
                # Create standardized parameter name
                if path_prefix:
                    param_name = f"{component}_{current_path}".replace(".", "_")
                else:
                    param_name = f"{key}"
                
                # Check if parameter already exists
                if param_name not in parameters:
                    parameters[param_name] = {
                        "type": param_type,
                        "description": f"{component.capitalize()} {current_path}",
                        "api": api,
                        "parameter_path": current_path,
                        "component": component,
                        "read_only": False  # Assume Config parameters are writable by default
                    }
            
            # For objects, recurse
            if isinstance(value, dict):
                self._extract_gen2_parameters_recursive(value, parameters, api, current_path, component)
    
    async def _check_gen2_eco_mode(self, device: Device, session: aiohttp.ClientSession, 
                                  parameters: Dict[str, Any]) -> None:
        """
        Check specifically for eco mode support in Gen2/Gen3 devices.
        
        Args:
            device: Device to probe
            session: Active aiohttp session
            parameters: Parameters dictionary to update
        """
        try:
            url = f"http://{device.ip_address}/rpc/Sys.GetConfig"
            async with session.post(url, json={}) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if "device" in data and "eco_mode" in data["device"]:
                        parameters["eco_mode"] = {
                            "type": "boolean",
                            "description": "Energy saving mode",
                            "api": "Sys.SetConfig",
                            "parameter_path": "device.eco_mode"
                        }
        except Exception as e:
            logger.debug(f"Error checking eco mode for {device.id}: {e}")
    
    def _parse_structure(self, data: Any, max_depth: int = 3, current_depth: int = 0) -> Any:
        """
        Parse the structure of an API response.
        
        Args:
            data: Data to parse
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth
            
        Returns:
            Structure description of the data
        """
        if current_depth >= max_depth:
            return "..."  # Truncate at max depth
        
        if isinstance(data, dict):
            result = {}
            for k, v in data.items():
                result[k] = self._parse_structure(v, max_depth, current_depth + 1)
            return result
        elif isinstance(data, list):
            if len(data) > 0:
                # Use the first element as an example
                return [self._parse_structure(data[0], max_depth, current_depth + 1)]
            else:
                return []
        elif isinstance(data, bool):
            return "boolean"
        elif isinstance(data, int):
            return "integer"
        elif isinstance(data, float):
            return "float"
        elif isinstance(data, str):
            return "string"
        elif data is None:
            return "null"
        else:
            return str(type(data).__name__)


# Create a global instance
device_capabilities = DeviceCapabilities() 