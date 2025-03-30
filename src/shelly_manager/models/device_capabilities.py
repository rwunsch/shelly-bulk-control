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
        
        # Try common Gen1 endpoints
        endpoints = [
            "/settings",
            "/status",
            "/shelly",
            "/settings/actions",
            "/settings/ap",
            "/settings/light",
            "/settings/login",
            "/settings/mqtt",
            "/settings/network",
            "/settings/relay/0",
            "/settings/cloud",
            "/settings/device"
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
                            
                            # Extract parameters from settings
                            if endpoint == "/settings":
                                self._extract_gen1_parameters(data, parameters)
                except Exception as e:
                    logger.debug(f"Error probing Gen1 endpoint {endpoint} for {device.id}: {e}")
    
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
        
        # Common RPC methods to try
        rpc_methods = [
            "Shelly.GetStatus",
            "Shelly.GetConfig",
            "Sys.GetStatus",
            "Switch.GetStatus",
            "Switch.GetConfig",
            "Light.GetStatus",
            "Light.GetConfig",
            "Cloud.GetStatus",
            "Cloud.GetConfig",
            "MQTT.GetConfig",
            "WiFi.GetConfig"
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
                            
                            # Extract parameters from config methods
                            if "GetConfig" in method:
                                self._extract_gen2_parameters(method, data, parameters)
                except Exception as e:
                    logger.debug(f"Error calling RPC method {method} for {device.id}: {e}")
            
            # Try to discover eco mode specifically
            await self._check_gen2_eco_mode(device, session, parameters)
    
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
    
    def _extract_gen1_parameters(self, data: Dict[str, Any], parameters: Dict[str, Any]) -> None:
        """
        Extract parameters from Gen1 device settings.
        
        Args:
            data: Settings data from the device
            parameters: Parameters dictionary to update
        """
        # Common parameters to look for in Gen1 devices
        param_mapping = {
            "name": {
                "path": "name",
                "type": "string",
                "description": "Device name"
            },
            "mqtt_enable": {
                "path": "mqtt.enable", 
                "type": "boolean",
                "description": "Enable MQTT"
            },
            "mqtt_server": {
                "path": "mqtt.server",
                "type": "string",
                "description": "MQTT server address"
            },
            "eco_mode_enabled": {  # Gen1-specific name
                "path": "eco_mode_enabled",
                "type": "boolean",
                "description": "Energy saving mode"
            },
            "max_power": {
                "path": "max_power",
                "type": "number",
                "description": "Maximum power in watts"
            }
        }
        
        # Check for each parameter and add it if found
        for param_name, param_info in param_mapping.items():
            path = param_info["path"].split(".")
            
            # Navigate to the parameter in the data
            value = data
            found = True
            for key in path:
                if key in value:
                    value = value[key]
                else:
                    found = False
                    break
            
            if found:
                # Map Gen1 parameter name to standard (Gen2+) parameter name for compatibility
                standard_param_name = ParameterMapper.to_standard_parameter(param_name)
                
                if standard_param_name != param_name:
                    logger.debug(f"Mapping Gen1 parameter {param_name} to standard parameter {standard_param_name}")
                
                parameters[standard_param_name] = {
                    "type": param_info["type"],
                    "description": param_info["description"],
                    "api": "settings",  # Gen1 devices use /settings endpoint
                    "parameter_path": param_info["path"]  # Keep the original path for API calls
                }
        
        # Even if we didn't directly find eco_mode_enabled in data, add it as a supported parameter
        # for ALL Gen1 devices as they generally support this function
        if "eco_mode" not in parameters and "eco_mode_enabled" not in parameters:
            logger.debug("Adding eco_mode parameter to Gen1 device (all Gen1 devices support this)")
            parameters["eco_mode"] = {
                "type": "boolean",
                "description": "Energy saving mode",
                "api": "settings",
                "parameter_path": "eco_mode_enabled"
            }
    
    def _extract_gen2_parameters(self, method: str, data: Dict[str, Any], 
                               parameters: Dict[str, Any]) -> None:
        """
        Extract parameters from Gen2 device config.
        
        Args:
            method: RPC method that was called
            data: Config data from the device
            parameters: Parameters dictionary to update
        """
        # Determine the corresponding SetConfig method
        set_method = method.replace("Get", "Set")
        
        # Common parameters in different config endpoints
        if method == "Shelly.GetConfig":
            if "name" in data:
                parameters["name"] = {
                    "type": "string",
                    "description": "Device name",
                    "api": set_method,
                    "parameter_path": "name"
                }
                
        elif method == "Sys.GetConfig":
            if "device" in data:
                device_cfg = data["device"]
                
                if "eco_mode" in device_cfg:
                    parameters["eco_mode"] = {
                        "type": "boolean",
                        "description": "Energy saving mode",
                        "api": set_method,
                        "parameter_path": "device.eco_mode"
                    }
                    
                if "max_power" in device_cfg:
                    parameters["max_power"] = {
                        "type": "number",
                        "description": "Maximum power in watts",
                        "api": set_method,
                        "parameter_path": "device.max_power"
                    }
                    
        elif method == "MQTT.GetConfig":
            mqtt_cfg = data
            
            if "enable" in mqtt_cfg:
                parameters["mqtt_enable"] = {
                    "type": "boolean",
                    "description": "Enable MQTT",
                    "api": set_method,
                    "parameter_path": "enable"
                }
                
            if "server" in mqtt_cfg:
                parameters["mqtt_server"] = {
                    "type": "string",
                    "description": "MQTT server address",
                    "api": set_method,
                    "parameter_path": "server"
                }
    
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