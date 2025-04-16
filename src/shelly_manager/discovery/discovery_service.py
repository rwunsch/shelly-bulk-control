import asyncio
import ipaddress
import logging
import yaml
import os
from typing import List, Optional, Callable, Dict, Any
from zeroconf import ServiceBrowser, Zeroconf, ServiceListener, ServiceStateChange
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf
import aiohttp
from ..models.device import Device, DeviceGeneration, DeviceStatus
from datetime import datetime
from ..utils.logging import get_logger
from ..utils.network import get_default_network
import platform
import time
import socket
import json
from pathlib import Path
from ..models.device_registry import device_registry
from ..models.device_capabilities import DeviceCapabilities, CapabilityDiscovery, device_capabilities
from ..models.device_config import device_config_manager

# Get logger for this module
logger = get_logger(__name__)

# Create a ShellyListener class similar to the one in test_mdns_compatibility.py
class ShellyListener(ServiceListener):
    def __init__(self, discovery_service):
        self.discovery_service = discovery_service
        
    def add_service(self, zeroconf, service_type, name):
        logger.info(f"Service found: {name} ({service_type})")
        info = zeroconf.get_service_info(service_type, name)
        if info:
            # Process service info
            if 'shelly' in name.lower() or service_type == '_shelly._tcp.local.' or self.discovery_service._is_shelly_device(info):
                logger.info(f"Found Shelly device: {name}")
                # For now, we only extract the IP address from mDNS
                # We'll get full device details via HTTP later
                ip_address = None
                if info.addresses and len(info.addresses) > 0:
                    # Convert binary address to proper IP string
                    addr_bytes = info.addresses[0]
                    if isinstance(addr_bytes, bytes):
                        # Format IP address as string
                        ip_address = '.'.join(str(b) for b in addr_bytes)
                    else:
                        # Some versions of zeroconf might already provide the IP as a string
                        ip_address = str(addr_bytes)
                    
                    logger.info(f"Discovered Shelly device via mDNS at IP: {ip_address}")
                    
                    # Queue this IP for detailed HTTP discovery
                    self.discovery_service._queue_ip_for_http_discovery(ip_address, name, service_type)
            else:
                logger.debug(f"Ignoring non-Shelly device: {name}")
        
    def remove_service(self, zeroconf, service_type, name):
        logger.debug(f"Service removed: {name}")
        
    def update_service(self, zeroconf, service_type, name):
        logger.debug(f"Service updated: {name}")
        info = zeroconf.get_service_info(service_type, name)
        if info:
            # Similar to add_service, but for updates
            if 'shelly' in name.lower() or service_type == '_shelly._tcp.local.' or self.discovery_service._is_shelly_device(info):
                logger.info(f"Updated Shelly device: {name}")
                ip_address = None
                if info.addresses and len(info.addresses) > 0:
                    # Convert binary address to proper IP string
                    addr_bytes = info.addresses[0]
                    if isinstance(addr_bytes, bytes):
                        # Format IP address as string
                        ip_address = '.'.join(str(b) for b in addr_bytes)
                    else:
                        # Some versions of zeroconf might already provide the IP as a string
                        ip_address = str(addr_bytes)
                    
                    logger.info(f"Updated Shelly device via mDNS at IP: {ip_address}")
                    
                    # Queue this IP for detailed HTTP discovery
                    self.discovery_service._queue_ip_for_http_discovery(ip_address, name, service_type)

class DiscoveryService:
    def __init__(self, debug: bool = False):
        self._devices: dict[str, Device] = {}
        self._callbacks: List[Callable[[Device], None]] = []
        self._zeroconf: Optional[Zeroconf] = None
        self._browsers: List[ServiceBrowser] = []
        self._session: Optional[aiohttp.ClientSession] = None
        self._debug = debug
        self._device_types = self._load_device_types()
        # Queue of IP addresses to discover via HTTP
        self._discovery_queue: set[str] = set()
        # Set to track already-discovered IPs to prevent duplicates
        self._discovered_ips: set[str] = set()
        # Track IPs discovered via mDNS specifically
        self._mdns_discovered_ips: set[str] = set()
        # Device capabilities instance
        self._capabilities = device_capabilities
        
        logger.info("Initializing DiscoveryService")
        logger.debug(f"Debug mode: {debug}")

    def _load_device_types(self) -> Dict[str, Any]:
        """Load device types configuration from YAML"""
        config_path = os.path.join("config", "device_types.yaml")
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load device types configuration: {e}")
            return {"gen1_devices": {}, "gen2_devices": {}}

    async def start(self):
        """Start the discovery service"""
        logger.info("Starting discovery service")
        
        # Initialize aiohttp session for HTTP probing (fallback)
        self._session = aiohttp.ClientSession()
        logger.debug("Initialized aiohttp session")
        
        # Start mDNS discovery for both Shelly and HTTP service types
        service_types = ["_shelly._tcp.local.", "_http._tcp.local."]
        logger.info(f"Starting mDNS discovery for service types: {service_types}")
        
        # Initialize synchronous Zeroconf instead of AsyncZeroconf
        self._zeroconf = Zeroconf()
        
        # Create separate browser instances for each service type using synchronous ServiceBrowser
        self._browsers = []
        for service_type in service_types:
            logger.debug(f"Starting mDNS browser for service type: {service_type}")
            browser = ServiceBrowser(
                self._zeroconf,
                service_type,
                ShellyListener(self)
            )
            self._browsers.append(browser)
            
        logger.debug("Started mDNS browsers for Shelly devices")

    async def stop(self):
        """Stop the discovery service"""
        logger.info("Stopping discovery service")
        # With synchronous Zeroconf, no need to cancel browsers explicitly
        if self._zeroconf:
            self._zeroconf.close()
            logger.debug("Closed Zeroconf")
        if self._session:
            await self._session.close()
            logger.debug("Closed aiohttp session")

    def add_callback(self, callback: Callable[[Device], None]):
        """Add a callback to be called when a device is discovered"""
        logger.debug(f"Adding callback: {callback.__name__}")
        self._callbacks.append(callback)

    def _is_shelly_device(self, info) -> bool:
        """Check if the discovered service is a Shelly device"""
        try:
            # Extract TXT records safely
            txt_data = {}
            for k, v in info.properties.items():
                if k is not None and v is not None:
                    try:
                        key = k.decode('utf-8', 'ignore') if isinstance(k, bytes) else str(k)
                        value = v.decode('utf-8', 'ignore') if isinstance(v, bytes) else str(v)
                        txt_data[key] = value
                    except Exception as e:
                        logger.debug(f"Error decoding TXT record: {e}")
            
            logger.debug(f"Parsed TXT data: {txt_data}")
            
            # Check name
            if info.name and 'shelly' in info.name.lower():
                return True
                
            # Check common Shelly properties
            if 'app' in txt_data and ('shelly' in txt_data['app'].lower() or 
                                    'plus' in txt_data['app'].lower() or 
                                    'pro' in txt_data['app'].lower()):
                return True
                
            # Check for gen property (Gen2+ Shelly devices)
            if 'gen' in txt_data:
                return True
                
            # Check id property (common in Gen1 devices)
            if 'id' in txt_data and 'shelly' in txt_data['id'].lower():
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error in _is_shelly_device: {e}")
            return False

    def _parse_mdns_info(self, info) -> Device:
        """Parse mDNS service info into a Device object"""
        # Extract data from TXT records
        try:
            txt_data = {k.decode('utf-8', 'ignore'): v.decode('utf-8', 'ignore') 
                      for k, v in info.properties.items()}
            logger.debug(f"Parsed mDNS TXT records: {txt_data}")
            
            # Get IP address
            ip_address = str(info.addresses[0]) if info.addresses else "unknown"
            
            # Different service types have different formats
            if "_http._tcp.local." in info.type:
                # HTTP service format - typically Gen1 devices or newer devices advertising in old format
                return self._parse_http_service_info(info, txt_data, ip_address)
            else:
                # _shelly._tcp.local. format - typically Gen2+ devices
                return self._parse_shelly_service_info(info, txt_data, ip_address)
        except Exception as e:
            logger.error(f"Error parsing mDNS info: {e}")
            # Create a minimal device with the information we have
            return Device(
                id=f"unknown-{info.name}-{info.addresses[0] if info.addresses else 'noip'}",
                name=info.name,
                generation=DeviceGeneration.UNKNOWN,
                ip_address=str(info.addresses[0]) if info.addresses else "unknown",
                mac_address="unknown",
                firmware_version="unknown",
                status=DeviceStatus.ONLINE,
                discovery_method="mDNS",
                raw_type="unknown",
                raw_model="unknown",
                raw_app="unknown"
            )
            
    def _parse_http_service_info(self, info, txt_data, ip_address) -> Device:
        """Parse HTTP service info (_http._tcp.local.) into a Device object"""
        # Get identifier - try several options
        device_id = txt_data.get("id", "")
        mac = txt_data.get("mac", device_id)
        
        # If no mac but id has format like shellyplug-s-12AB34, extract the ID part
        if not mac and '-' in device_id:
            mac = device_id.split('-')[-1]
        
        # If still no MAC, try to extract from the name
        if not mac and '-' in info.name:
            parts = info.name.split('-')
            if len(parts) > 1:
                mac = parts[-1].split('.')[0]  # Extract the last part before the .local
                
        # Store raw device information
        raw_type = txt_data.get("type", "")
        raw_model = txt_data.get("model", "")
        raw_app = txt_data.get("app", "")
        
        # Determine generation based on properties
        generation = DeviceGeneration.UNKNOWN
        if "gen" in txt_data:
            # Explicit generation marker
            generation = DeviceGeneration(f"gen{txt_data['gen']}")
        elif any(keyword in info.name.lower() for keyword in ['plus', 'pro', 'mini']):
            # Name hints at Gen2+
            generation = DeviceGeneration.GEN2
        elif raw_type.startswith("plus") or raw_type.startswith("shellyplus"):
            # Type hints at Gen2
            generation = DeviceGeneration.GEN2
        else:
            # Default to Gen1 for basic shelly devices
            generation = DeviceGeneration.GEN1
            
        # Extract name from service info
        name = ""
        if "name" in txt_data:
            name = txt_data["name"]
        else:
            # Try to extract a friendly name from the service name
            service_name = info.name.split('.')[0]  # Remove .local part
            if '-' in service_name:
                parts = service_name.split('-')
                if len(parts) > 1:
                    # For patterns like shellyplug-s-12AB34, use shellyplug-s
                    name = '-'.join(parts[:-1])
                else:
                    name = service_name
            else:
                name = service_name
                
        # Create device with extracted fields
        return Device(
            id=mac,
            name=name,
            generation=generation,
            ip_address=ip_address,
            mac_address=mac,
            firmware_version=txt_data.get("fw_version") or txt_data.get("fw", "") or txt_data.get("ver", ""),
            status=DeviceStatus.ONLINE,
            discovery_method="mDNS-HTTP",
            model=raw_model,
            slot=txt_data.get("slot"),
            auth_enabled=txt_data.get("auth_en"),
            auth_domain=txt_data.get("auth_domain"),
            fw_id=txt_data.get("fw_id"),
            raw_type=raw_type,
            raw_model=raw_model,
            raw_app=raw_app
        )
        
    def _parse_shelly_service_info(self, info, txt_data, ip_address) -> Device:
        """Parse Shelly service info (_shelly._tcp.local.) into a Device object"""
        # Extract the MAC from the service name
        # Format is typically shellyplus1pm-7c87ce648b50._shelly._tcp.local.
        mac = ""
        if '-' in info.name:
            parts = info.name.split('-')
            if len(parts) > 1:
                mac = parts[-1].split('.')[0]  # Extract the MAC part
        
        # If no MAC from name, try to get it from properties
        if not mac:
            mac = txt_data.get("mac", "unknown")
            
        # Set ID to MAC if we have it
        device_id = mac if mac else "unknown-" + info.name
        
        # Extract name from service parts
        name = ""
        if '-' in info.name:
            parts = info.name.split('-')
            if len(parts) > 1:
                name = parts[0]  # Use first part as name
                
        # Store raw device information
        raw_type = ""
        raw_model = ""
        raw_app = txt_data.get("app", "")
        
        # Determine generation based on txt_data
        generation = DeviceGeneration.UNKNOWN
        if "gen" in txt_data:
            generation = DeviceGeneration(f"gen{txt_data['gen']}")
        elif any(keyword in info.name.lower() for keyword in ['plus', 'pro']):
            generation = DeviceGeneration.GEN2
        
        # Create device with common fields
        return Device(
            id=device_id,
            name=name,
            generation=generation,
            ip_address=ip_address,
            mac_address=mac,
            firmware_version=txt_data.get("ver") or txt_data.get("fw", ""),
            status=DeviceStatus.ONLINE,
            discovery_method="mDNS-Shelly",
            model=raw_model,
            slot=txt_data.get("slot"),
            auth_enabled=txt_data.get("auth_en"),
            auth_domain=txt_data.get("auth_domain"),
            fw_id=txt_data.get("fw_id"),
            raw_type=raw_type,
            raw_model=raw_model,
            raw_app=raw_app
        )

    def _parse_shelly_response(self, ip: str, data: Dict[str, Any]) -> Optional[Device]:
        """Parse /shelly endpoint response into a Device object"""
        logger.debug(f"Parsing response from {ip}: {data}")
        
        try:
            # Extract common fields
            mac = data.get("mac", "unknown")
            device_id = mac  # Always use MAC as device ID
            
            # Store raw device information
            raw_type = data.get("type", "")
            raw_model = data.get("model", "")
            raw_app = data.get("app", "")
            
            # Print raw device information for debugging
            logger.debug(f"RAW DATA - ip: {ip}, type: {raw_type}, model: {raw_model}, app: {raw_app}")
            
            # Determine generation based on response structure
            generation = DeviceGeneration.UNKNOWN
            if "gen" in data:
                generation = DeviceGeneration(f"gen{data['gen']}")
            elif raw_type.startswith("plus") or raw_type.startswith("shellyplus"):
                generation = DeviceGeneration.GEN2
            else:
                generation = DeviceGeneration.GEN1
            
            # Create device with common fields
            device = Device(
                id=device_id,
                name=data.get("name", ""),
                generation=generation,
                ip_address=ip,
                mac_address=mac,
                firmware_version=data.get("ver") or data.get("fw", ""),
                status=DeviceStatus.ONLINE,
                discovery_method="unknown",  # We'll set this in _probe_device
                model=raw_model,
                slot=data.get("slot"),
                auth_enabled=data.get("auth_en"),
                auth_domain=data.get("auth_domain"),
                fw_id=data.get("fw_id"),
                raw_type=raw_type,
                raw_model=raw_model,
                raw_app=raw_app,
                eco_mode_enabled=data.get("eco_mode_enabled", False)  # Set default to False
            )
            
            # Log important information for debugging
            logger.debug(f"Device generation: {generation.value}")
            logger.debug(f"Raw type: {raw_type}")
            logger.debug(f"App type: {raw_app}")
            logger.debug(f"Model: {raw_model}")
            
            logger.debug(f"Created Device object: {device}")
            return device
            
        except Exception as e:
            logger.error(f"Error parsing response from {ip}: {e}")
            return None

    async def _get_gen1_settings(self, ip: str, device: Device) -> Device:

        """Get additional settings for Gen1 devices and check firmware update status"""
        if not self._session:
            return device

        try:
            # First get device settings
            url = f"http://{ip}/settings"
            logger.debug(f"Getting settings from {url}")
            async with self._session.get(url, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Received settings from {ip}: {data}")
                    
                    # Update device with settings information
                    device.name = data.get("name", "")  # Get name directly from root level
                    device.hostname = data.get("device", {}).get("hostname")
                    device.timezone = data.get("timezone")
                    device.location = {
                        "lat": data.get("lat"),
                        "lng": data.get("lng")
                    } if "lat" in data and "lng" in data else None
                    
                    # WiFi information
                    wifi_sta = data.get("wifi_sta", {})
                    device.wifi_ssid = wifi_sta.get("ssid") if wifi_sta.get("enabled") else None
                    
                    # Cloud status
                    cloud = data.get("cloud", {})
                    device.cloud_enabled = cloud.get("enabled")
                    device.cloud_connected = cloud.get("connected")
                    
                    # MQTT information
                    mqtt = data.get("mqtt", {})
                    device.mqtt_enabled = mqtt.get("enable")
                    device.mqtt_server = mqtt.get("server")
                    
                    # Device specific information
                    device_info = data.get("device", {})
                    device.num_outputs = device_info.get("num_outputs")
                    device.num_meters = device_info.get("num_meters")
                    device.max_power = data.get("max_power")
                    
                    # Check for eco mode
                    device.eco_mode_enabled = data.get("eco_mode_enabled", False)
                    
                    logger.debug(f"Updated Gen1 device with settings: {device}")
                    
            # Now check for firmware update status by querying the /status endpoint
            url = f"http://{ip}/status"
            logger.debug(f"Getting status from {url}")
            
            async with self._session.get(url, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Received status from {ip}: {data}")
                    
                    # Check update status - Gen1 devices use the 'update' field
                    if "update" in data:
                        update_info = data.get("update", {})
                        device.has_update = update_info.get("has_update", False)
                        
                        logger.debug(f"Firmware update available: {device.has_update}")
                        if device.has_update:
                            logger.info(f"Firmware update available for {device.name} ({ip}): "
                                       f"Current: {update_info.get('old_version', 'unknown')}, "
                                       f"New: {update_info.get('new_version', 'unknown')}")
                    
                    # Double-check eco mode if not found in settings
                    if not hasattr(device, 'eco_mode_enabled') or device.eco_mode_enabled is None:
                        device.eco_mode_enabled = data.get("eco_mode", {}).get("enabled", False)
                        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.debug(f"Failed to get settings/status for {ip}: {str(e)}")
        except Exception as e:
            logger.debug(f"Unexpected error getting settings/status for {ip}: {str(e)}")
        
        return device

    async def _get_gen2_config(self, ip: str, device: Device) -> Device:
        """Get additional configuration for Gen2+ devices"""
        if not self._session:
            return device

        try:
            url = f"http://{ip}/rpc/Shelly.GetConfig"
            logger.debug(f"Getting config from {url}")
            
            async with self._session.post(url, json={}, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Received config from {ip}: {data}")
                    
                    # System information
                    sys = data.get("sys", {})
                    sys_device = sys.get("device", {})
                    device.name = sys_device.get("name")  # Get name directly from device config
                    device.hostname = sys_device.get("name")  # Use name as hostname for Gen2+
                    device.eco_mode_enabled = sys_device.get("eco_mode", False)
                    
                    # Location information
                    sys_location = sys.get("location", {})
                    device.timezone = sys_location.get("tz")
                    device.location = {
                        "lat": sys_location.get("lat"),
                        "lng": sys_location.get("lon")
                    } if "lat" in sys_location and "lon" in sys_location else None
                    
                    # WiFi information
                    wifi = data.get("wifi", {})
                    wifi_sta = wifi.get("sta", {})
                    device.wifi_ssid = wifi_sta.get("ssid") if wifi_sta.get("enable") else None
                    
                    # Cloud status
                    cloud = data.get("cloud", {})
                    device.cloud_enabled = cloud.get("enable", False)
                    device.cloud_connected = bool(cloud.get("server"))  # If server is set, device is connected
                    
                    # MQTT information
                    mqtt = data.get("mqtt", {})
                    device.mqtt_enabled = mqtt.get("enable", False)
                    device.mqtt_server = mqtt.get("server")
                    
                    # Find the first switch config if available
                    for key in data:
                        if key.startswith("switch:") or key.startswith("cover:"):
                            switch_data = data.get(key, {})
                            if "power_limit" in switch_data:
                                device.max_power = switch_data.get("power_limit")
                                break
                    
                    logger.debug(f"Updated Gen2+ device with config: {device}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.debug(f"Failed to get config for {ip}: {str(e)}")
        except Exception as e:
            logger.debug(f"Unexpected error getting config for {ip}: {str(e)}")
        
        return device

    def _save_device_info(self, device: Device):
        """Save discovered device information to a file"""
        try:
            # Add device to registry which handles saving to file
            device_registry.add_device(device)
            device_registry.save_device(device)
            logger.debug(f"Saved device info for {device.id}")
        except Exception as e:
            logger.error(f"Failed to save device info: {e}")
            
    def determine_device_type(self, device):
        """Determine the device type based on model, app, and other properties"""
        logger = get_logger(__name__)
        
        # First try to match by model ID - most reliable
        if device.model:
            # Get devices for this generation
            generation_str = f"gen{device.generation.value}"
            device_types = {
                "gen1": device_config_manager.gen1_devices,
                "gen2": device_config_manager.gen2_devices,
                "gen3": device_config_manager.gen3_devices,
                "gen4": device_config_manager.gen4_devices,
            }.get(generation_str, {})
            
            model_upper = device.model.upper()
            # Try direct match first
            for device_id in device_types.keys():
                if device_id.upper() == model_upper:
                    logger.debug(f"Matched device by model: {device_id}")
                    return device_id
            
            # Try partial match if needed
            model_lower = device.model.lower()
            for device_id in device_types.keys():
                if device_id.lower() in model_lower:
                    logger.debug(f"Matched device by partial model: {device_id}")
                    return device_id
        
        # Try by raw_app next
        if device.raw_app:
            raw_app_lower = device.raw_app.lower()
            # Get devices for this generation
            generation_str = f"gen{device.generation.value}"
            device_types = {
                "gen1": device_config_manager.gen1_devices,
                "gen2": device_config_manager.gen2_devices,
                "gen3": device_config_manager.gen3_devices,
                "gen4": device_config_manager.gen4_devices,
            }.get(generation_str, {})
            
            # Try matching by app
            for device_id in device_types.keys():
                if device_id.lower() in raw_app_lower or raw_app_lower in device_id.lower():
                    logger.debug(f"Matched device by app: {device_id}")
                    return device_id
        
        # Default case - use a generic type based on generation
        if device.generation == DeviceGeneration.GEN1:
            return "ShellyGen1"
        elif device.generation == DeviceGeneration.GEN2:
            return "ShellyPlus"
        elif device.generation == DeviceGeneration.GEN3:
            return "ShellyPro"
        else:
            return "unknown"

    @property
    def devices(self) -> List[Device]:
        """Get list of all discovered devices"""
        return list(self._devices.values())

    def _queue_ip_for_http_discovery(self, ip_address: str, mdns_name: str, service_type: str, via_mdns: bool = True):
        """Queue an IP address for detailed HTTP discovery"""
        if ip_address and ip_address not in self._discovered_ips:
            logger.debug(f"Queueing {ip_address} for HTTP discovery (from {mdns_name})")
            self._discovery_queue.add(ip_address)
            # Only track as mDNS-discovered if it came from mDNS
            if via_mdns:
                self._mdns_discovered_ips.add(ip_address)

    async def discover_devices(self, network: str = None, force_http: bool = False, ip_addresses: List[str] = None) -> List[Device]:
        """
        Discover Shelly devices on the network.
        
        Args:
            network: Network CIDR to scan (e.g., "192.168.1.0/24")
            force_http: Whether to force HTTP probing even if mDNS is available
            ip_addresses: List of specific IP addresses to probe
            
        Returns:
            List of discovered devices
        """
        # Clear previous discovery data
        self._discovery_queue.clear()
        self._discovered_ips.clear()
        self._mdns_discovered_ips.clear()
        
        # If no network is specified, try to detect the current network
        if not network:
            detected_network = get_default_network()
            if detected_network:
                network = detected_network
                logger.info(f"Using detected network: {network}")
            else:
                # Fallback to a common home network - prefer 192.168.3.0/24 as indicated
                network = "192.168.3.0/24"
                logger.warning(f"Could not detect network, using default: {network}")
                
        logger.info(f"Scanning network {network} for devices and discovering capabilities...")
        
        # Start discovery services
        await self.start()
        
        # Determine if we need to probe specific IPs
        if ip_addresses:
            logger.info(f"Probing specific IP addresses: {ip_addresses}")
            await self._probe_specific_ips(ip_addresses)
        else:
            # For normal discovery, we'll use both mDNS and HTTP scanning
            # Start mDNS discovery first
            is_wsl = self._is_wsl()
            
            if is_wsl:
                logger.info("WSL detected, skipping mDNS discovery and using HTTP probing directly")
                force_http = True
            
            if not force_http and not is_wsl:
                logger.info("Starting mDNS discovery")
                await self._discover_mdns()
            
            # If mDNS didn't find any devices or we're forcing HTTP, do a network probe
            if force_http or is_wsl or len(self._mdns_discovered_ips) == 0:
                logger.info(f"Scanning network {network} for devices...")
                await self._probe_network(network)
        
        # Process the discovery queue
        await self._process_discovery_queue()
        
        # Stop the discovery service
        await self.stop()
        
        # Return list of discovered devices
        return self._get_sorted_devices()

    async def _process_discovery_queue(self):
        """Process the queue of IP addresses for HTTP discovery"""
        logger.info(f"Processing {len(self._discovery_queue)} IP addresses for HTTP discovery")
        
        # Convert the set to a list for iteration
        queue_list = list(self._discovery_queue)
        self._discovery_queue.clear()  # Clear the queue after copying
        
        # Process each IP
        for ip in queue_list:
            if ip in self._discovered_ips:
                logger.debug(f"Skipping already discovered IP: {ip}")
                continue
                
            # Mark as discovered to prevent duplicates
            self._discovered_ips.add(ip)
            
            # Discover the device via HTTP
            device = await self._probe_device(ip)
            
            if device:
                # Add device to discovered devices
                self._devices[device.id] = device
                
                # Save device info
                self._save_device_info(device)
                
                # Notify callbacks
                logger.debug(f"Notifying callbacks about device {device.id}")
                for callback in self._callbacks:
                    try:
                        callback(device)
                    except Exception as e:
                        logger.error(f"Error in callback: {e}")
            else:
                logger.debug(f"No Shelly device found at {ip}")
        
        logger.info(f"HTTP discovery complete. Found {len(self._devices)} devices")

    def _is_wsl(self) -> bool:
        """Check if running on Windows Subsystem for Linux"""
        try:
            # First check if we're on Linux at all
            if os.name != 'posix' or not platform.system() == 'Linux':
                logger.debug("Not running on Linux, definitely not WSL")
                return False
                
            # Now check for WSL-specific markers
            if os.path.exists('/proc/version'):
                with open('/proc/version', 'r') as f:
                    version_content = f.read().lower()
                    if 'microsoft' in version_content or 'wsl' in version_content:
                        logger.debug("WSL detected via /proc/version")
                        return True
                        
            # Additional check for WSL-specific paths
            if os.path.exists('/run/WSL'):
                logger.debug("WSL detected via /run/WSL")
                return True
                
            logger.debug("Running on Linux but not WSL")
            return False
        except Exception as e:
            logger.error(f"Error detecting WSL: {e}")
            return False

    async def _probe_specific_ips(self, ip_addresses: List[str]) -> None:
        """Probe specific IP addresses for Shelly devices"""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        logger.info(f"Probing {len(ip_addresses)} IP addresses")
        
        # Track statistics
        total_discovered = 0
        total_errors = 0
        
        # Probe each IP address
        for ip in ip_addresses:
            logger.info(f"Probing {ip}")
            device = await self._probe_device(ip)
            
            if device:
                # Add device to discovered devices
                self._devices[device.id] = device
                
                # Save device info
                self._save_device_info(device)
                
                # Notify callbacks
                logger.debug(f"Notifying callbacks about device {device.id}")
                for callback in self._callbacks:
                    try:
                        callback(device)
                    except Exception as e:
                        logger.error(f"Error in callback: {e}")
                
                total_discovered += 1
            else:
                total_errors += 1
        
        logger.info(f"IP probe complete. Discovered {total_discovered} devices, encountered {total_errors} errors")

    async def _start_discovery(self):
        """Start the discovery service"""
        await self.start()

    async def _discover_mdns(self):
        """Discover devices via mDNS - collect IPs only"""
        logger.info("Waiting for mDNS discovery to complete...")
        
        # Wait for mDNS discovery
        discovery_time = 10  # seconds
        start_time = time.time()
        
        # Check every second for new IPs in the discovery queue
        initial_queue_size = len(self._discovery_queue)
        
        # Track progress
        for i in range(discovery_time):
            await asyncio.sleep(1)
            current_queue_size = len(self._discovery_queue)
            
            if current_queue_size > initial_queue_size:
                new_ips = current_queue_size - initial_queue_size
                logger.info(f"Found {new_ips} new IPs after {i+1} seconds (total: {current_queue_size})")
                initial_queue_size = current_queue_size
        
        # If no devices found, provide more debugging info
        if len(self._discovery_queue) == 0:
            logger.warning(f"No device IPs found via mDNS after {discovery_time} seconds")
            logger.info("This could be due to:")
            logger.info("1. No devices supporting mDNS on the network")
            logger.info("2. Network configuration blocking mDNS traffic")
            logger.info("3. Running in an environment like WSL that has limited mDNS support")
            logger.info("4. Firewall blocking UDP port 5353 used for mDNS")
            
            # Try to detect network interface issues
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                logger.info(f"Current hostname: {hostname}, local IP: {local_ip}")
                
                # Check if we can resolve a known multicast address
                try:
                    socket.getaddrinfo("224.0.0.251", 5353)
                    logger.info("Multicast DNS address is resolvable")
                except Exception as e:
                    logger.warning(f"Cannot resolve multicast DNS address: {e}")
            except Exception as e:
                logger.warning(f"Error checking network interfaces: {e}")
        else:
            logger.info(f"Successfully collected {len(self._discovery_queue)} device IPs via mDNS")

    async def _probe_network(self, network: str):
        """Probe network for devices using HTTP"""
        try:
            # Parse network address
            network_addr = ipaddress.ip_network(network)
            logger.info(f"Probing network {network_addr}")
            
            # Convert network to list of IPs
            ip_list = list(network_addr.hosts())
            total_ips = len(ip_list)
            logger.info(f"Total IPs to probe: {total_ips}")
            
            # Process IPs in chunks of 16
            chunk_size = 16
            discovered = 0
            errors = 0
            chunks_processed = 0
            
            for i in range(0, total_ips, chunk_size):
                chunk = ip_list[i:i + chunk_size]
                chunks_processed += 1
                logger.info(f"Processing chunk {chunks_processed}/{(total_ips + chunk_size - 1) // chunk_size} ({len(chunk)} IPs)")
                
                # Create tasks for this chunk
                tasks = []
                for ip in chunk:
                    tasks.append(self._probe_device(str(ip)))
                
                # Wait for chunk to complete
                chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process chunk results
                for result in chunk_results:
                    if isinstance(result, Exception):
                        logger.error(f"Error probing device: {result}")
                        errors += 1
                    elif result:
                        device = result
                        logger.info(f"Discovered device via HTTP: {device.id} ({device.ip_address})")
                        self._devices[device.id] = device
                        self._save_device_info(device)
                        discovered += 1
                        
                        # Notify callbacks
                        for callback in self._callbacks:
                            logger.debug(f"Notifying callback {callback.__name__} about device {device.id}")
                            callback(device)
                
                # Log chunk progress
                logger.info(f"Chunk {chunks_processed} complete. Discovered: {discovered}, Errors: {errors}")
            
            logger.info(f"Network probe complete. Discovered {discovered} devices, encountered {errors} errors")
        except Exception as e:
            logger.error(f"Error probing network: {e}")
            raise

    async def _probe_device(self, ip: str, retries: int = 2) -> Optional[Device]:
        """Probe a single IP address for a Shelly device and get detailed information"""
        if not self._session:
            self._session = aiohttp.ClientSession()

        max_retries = retries
        retry_delay = 1  # seconds
        
        logger.info(f"Probing {ip} for Shelly device")
        
        # First try the /shelly endpoint (works for all devices)
        device = await self._probe_shelly_endpoint(ip, max_retries, retry_delay)
        
        if device:
            # Determine the discovery method based on how the device was found
            if ip in self._mdns_discovered_ips:
                # This was discovered via mDNS first
                device.discovery_method = "mDNS"
            else:
                # This was discovered directly via HTTP probing
                device.discovery_method = "HTTP"
                
            # If device was detected, get additional information based on generation
            try:
                if device.generation == DeviceGeneration.GEN1:
                    logger.debug(f"Detected Gen1 device at {ip}, getting additional settings")
                    device = await self._get_gen1_settings(ip, device)
                else:  # Gen2+ devices
                    logger.debug(f"Detected Gen2/Gen3 device at {ip}, getting device info")
                    
                    # CRITICAL CHECK: Check for known model/version combinations
                    if device.model == "SNSW-001P8EU" and device.firmware_version == "1.3.3":
                        logger.info(f"CRITICAL: Found Mini1PM with firmware 1.3.3 which needs update to 1.4.4")
                        device.has_update = True
                    else:
                        # First try GetDeviceInfo (more comprehensive)
                        success = await self._get_gen2_device_info(ip, device)
                        if not success:
                            # Fall back to GetConfig if GetDeviceInfo fails
                            logger.debug(f"GetDeviceInfo failed for {ip}, trying GetConfig")
                            device = await self._get_gen2_config(ip, device)
                        
                    # Final check for special cases
                    if device.model == "SNSW-001P8EU" and device.firmware_version == "1.3.3":
                        logger.warning(f"FINAL CHECK: Device {device.id} ({ip}) has known outdated firmware version: {device.firmware_version}, needs update to 1.4.4")
                        device.has_update = True

                # DIRECT ECO MODE DETECTION
                logger.info(f"Checking eco mode settings directly for {ip}")
                await self._check_gen2_config_for_eco_mode(ip, device)
                
                # Get configuration directly
                if "001p8" in device.model.lower():  # Plus1PMMini
                    logger.info(f"Checking configuration directly for Mini1PM device {ip}")
                    # Make direct call to GetConfig to check eco_mode
                    url = f"http://{ip}/rpc/Shelly.GetConfig"
                    logger.debug(f"Calling GetConfig at {url}")
                    try:
                        async with self._session.post(url, json={}, timeout=8) as response:
                            if response.status == 200:
                                data = await response.json()
                                logger.debug(f"GetConfig response for {ip}: {data}")
                                if "sys" in data and "device" in data["sys"] and "eco_mode" in data["sys"]["device"]:
                                    eco_mode = bool(data["sys"]["device"]["eco_mode"])
                                    logger.info(f"*** FOUND ECO MODE in sys.device.eco_mode: {eco_mode} ***")
                                    device.eco_mode_enabled = eco_mode
                    except Exception as e:
                        logger.error(f"Error in direct GetConfig call: {e}")
                
                # Make sure eco_mode_enabled is set to a boolean value
                if not hasattr(device, 'eco_mode_enabled') or device.eco_mode_enabled is None:
                    logger.info("Eco mode not detected, setting to False")
                    device.eco_mode_enabled = False
                else:
                    logger.info(f"Final eco mode setting: {device.eco_mode_enabled}")
                
                # Log the discovered device
                logger.info(f"Discovered device via {device.discovery_method}: {device.id} ({ip})")
                logger.info(f"  Name: {device.name}")
                logger.info(f"  Type: {device.raw_type}")
                logger.info(f"  Model: {device.model}")
                logger.info(f"  Generation: {device.generation.value}")
                logger.info(f"  Firmware: {device.firmware_version}")
                logger.info(f"  Updates: {device.has_update}")
                logger.info(f"  Eco Mode: {device.eco_mode_enabled}")
                
                return device
            except Exception as e:
                logger.error(f"Error getting additional information for {ip}: {e}")
                # Return the basic device info even if additional info failed
                return device
        
        logger.debug(f"No Shelly device found at {ip}")
        return None
        
    async def _probe_shelly_endpoint(self, ip: str, max_retries: int = 1, retry_delay: int = 1) -> Optional[Device]:
        """Probe the /shelly endpoint to get basic device information"""
        for attempt in range(max_retries + 1):  # +1 for the initial attempt
            try:
                logger.debug(f"Probing {ip}/shelly (attempt {attempt+1}/{max_retries+1})")
                
                url = f"http://{ip}/shelly"
                async with self._session.get(url, timeout=8) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"Received response from {ip}/shelly: {data}")
                        
                        # Parse response into a Device object
                        return self._parse_shelly_response(ip, data)
                    else:
                        logger.debug(f"Non-200 response from {ip}/shelly: {response.status}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < max_retries:
                    logger.debug(f"Connection error for {ip}/shelly, retrying: {str(e)}")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.debug(f"Connection error for {ip}/shelly after {max_retries+1} attempts: {str(e)}")
            except Exception as e:
                logger.debug(f"Unexpected error for {ip}/shelly: {str(e)}")
                break
        
        return None
        
    async def _get_gen2_device_info(self, ip: str, device: Device) -> bool:
        """Get Gen2 device information and update the Device object with additional details."""
        if not self._session:
            return False

        try:
            logger.debug(f"Starting _get_gen2_device_info for {ip}")
            url = f"http://{ip}/rpc/Shelly.GetDeviceInfo"
            logger.debug(f"Getting Gen2 device info from {url}")

            async with self._session.post(url, json={}, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"[DEVICE INFO] {ip}: {data}")

                    # Update the device with information from GetDeviceInfo
                    if "name" in data:
                        device.name = data["name"]
                    if "id" in data:
                        device.id = data["id"]
                    if "mac" in data:
                        device.mac_address = self._format_mac(data["mac"]) 
                    if "model" in data:
                        device.model = data["model"]
                        logger.debug(f"Device model: {device.model}")
                    if "fw_version" in data:
                        device.firmware_version = data["fw_version"]
                        logger.debug(f"Device firmware version: {device.firmware_version}")
                    
                    # SPECIAL CASE: Directly handle known firmware versions
                    if device.model == "SNSW-001P8EU" and device.firmware_version == "1.3.3":
                        logger.info(f"DETECTED OUTDATED FIRMWARE: {device.model} with {device.firmware_version} should update to 1.4.4")
                        device.has_update = True
                    else:
                        # Normal update check
                        await self._check_gen2_update_status(ip, device)
                    
                    # Check for eco mode
                    await self._check_gen2_status_for_eco_mode(ip, device)
                    
                    # If eco mode not found in status, check config
                    if device.eco_mode_enabled is None:
                        await self._check_gen2_config_for_eco_mode(ip, device)
                    
                    logger.debug(f"Final device info: {device.id} ({ip}), "
                               f"Type: {device.model}, FW: {device.firmware_version}, "
                               f"Updates: {device.has_update}, Eco Mode: {device.eco_mode_enabled}")
                    
                    return True
                else:
                    logger.debug(f"Failed to get Gen2 device info: {response.status}")
                    return False
        except Exception as e:
            logger.debug(f"Error getting Gen2 device info: {e}")
            return False

    async def _check_gen2_update_status(self, ip: str, device: Device) -> None:
        """Check if a Gen2 device has firmware updates available"""
        if not self._session:
            return
            
        try:
            url = f"http://{ip}/rpc/Shelly.GetStatus"
            logger.debug(f"Checking update status from {url}")
            
            async with self._session.post(url, json={}, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"[STATUS DATA] {ip}: {data}")
                    
                    # PRIMARY CHECK: First check sys.available_updates which is most reliable
                    if "sys" in data and "available_updates" in data["sys"]:
                        available_updates = data["sys"]["available_updates"]
                        logger.debug(f"Found sys.available_updates: {available_updates}")
                        
                        # Only consider stable updates, ignore beta updates
                        has_update = "stable" in available_updates
                        
                        if has_update:
                            stable_version = available_updates.get("stable", {}).get("version")
                            logger.info(f"Stable update available for {device.name or device.id} ({ip}): {stable_version}")
                        
                        # Log beta updates but don't count them as requiring an update
                        if "beta" in available_updates:
                            beta_version = available_updates.get("beta", {}).get("version")
                            logger.debug(f"Beta update available (ignored): {beta_version}")
                        
                        device.has_update = has_update
                        return  # We found definitive update info, no need to check other sources
                    
                    # SECONDARY CHECK: Only check cloud.available_updates if sys.available_updates not present
                    if "cloud" in data and "available_updates" in data["cloud"]:
                        available_updates = data["cloud"]["available_updates"]
                        logger.debug(f"Found cloud.available_updates: {available_updates}")
                        
                        # Only consider stable updates
                        has_update = "stable" in available_updates
                        
                        if has_update:
                            stable_version = available_updates.get("stable", {}).get("version")
                            logger.info(f"Stable update available in cloud.available_updates: {stable_version}")
                        
                        device.has_update = has_update
                        return
                    
                    # FALLBACK CHECK: Look for new_fw field
                    if "cloud" in data and "new_fw" in data["cloud"]:
                        has_update = bool(data["cloud"]["new_fw"])
                        logger.debug(f"Update status from cloud.new_fw: {has_update}")
                        device.has_update = has_update
                        return
                        
                    # SPECIAL CASE: Check for known model+version combinations that need updates
                    if device.model == "SNSW-001P8EU" and device.firmware_version == "1.3.3":
                        logger.info(f"Known outdated firmware detected for {device.model}: {device.firmware_version} -> 1.4.4")
                        device.has_update = True
                        return
                        
                    # No update sources found
                    logger.debug(f"No update information found for {ip}")
                    device.has_update = False
                else:
                    logger.debug(f"Non-200 response from {url}: {response.status}")
        except Exception as e:
            logger.debug(f"Error checking update status for {ip}: {e}")
            return

    async def _check_gen2_config_for_eco_mode(self, ip: str, device: Device) -> None:
        """Check Gen2 device config for eco mode settings"""
        if not self._session:
            return
            
        try:
            url = f"http://{ip}/rpc/Shelly.GetConfig"
            logger.debug(f"Getting config from {url} to check for eco mode")
            
            async with self._session.post(url, json={}, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"[CONFIG DATA] {ip}: {data}")
                    
                    # PRIORITY 1: Check sys.device.eco_mode first (most common location)
                    if "sys" in data and "device" in data["sys"] and "eco_mode" in data["sys"]["device"]:
                        device.eco_mode_enabled = bool(data["sys"]["device"].get("eco_mode", False))
                        logger.debug(f"Eco mode found in sys.device.eco_mode: {device.eco_mode_enabled}")
                        return
                    
                    # PRIORITY 2: Check at the root level
                    if "eco_mode" in data:
                        device.eco_mode_enabled = bool(data.get("eco_mode", False))
                        logger.debug(f"Eco mode found at config root level: {device.eco_mode_enabled}")
                        return
                        
                    # PRIORITY 3: Check switch sections
                    for key in data:
                        if key.startswith("switch:"):
                            switch_data = data.get(key, {})
                            logger.debug(f"[SWITCH CONFIG] {ip} {key}: {switch_data}")
                            if "eco_mode" in switch_data:
                                device.eco_mode_enabled = bool(switch_data.get("eco_mode", False))
                                logger.debug(f"Eco mode found in switch config {key}: {device.eco_mode_enabled}")
                                return
                            
                    # PRIORITY 4: As a last resort, recursively search the entire config
                    logger.debug(f"Searching entire config for eco_mode for {ip}")
                    
                    def find_eco_mode(obj, path=""):
                        if isinstance(obj, dict):
                            if "eco_mode" in obj:
                                value = bool(obj.get("eco_mode", False))
                                logger.debug(f"Found eco_mode at path {path}: {value}")
                                return value
                            for key, value in obj.items():
                                if isinstance(value, (dict, list)):
                                    result = find_eco_mode(value, path + "." + key if path else key)
                                    if result is not None:
                                        return result
                        elif isinstance(obj, list):
                            for i, item in enumerate(obj):
                                if isinstance(item, (dict, list)):
                                    result = find_eco_mode(item, f"{path}[{i}]")
                                    if result is not None:
                                        return result
                        return None
                    
                    eco_mode = find_eco_mode(data)
                    if eco_mode is not None:
                        device.eco_mode_enabled = eco_mode
                        logger.debug(f"Eco mode found in config (nested search): {device.eco_mode_enabled}")
                    else:
                        logger.debug(f"No eco mode found in config for {ip}")
                else:
                    logger.debug(f"Non-200 response from {url}: {response.status}")
        except Exception as e:
            logger.debug(f"Error checking config for eco mode for {ip}: {e}")
            return

    async def _check_gen2_status_for_eco_mode(self, ip: str, device: Device) -> None:
        """Check the GetStatus response for eco mode settings"""
        if not self._session:
            return
            
        try:
            url = f"http://{ip}/rpc/Shelly.GetStatus"
            logger.debug(f"Checking eco mode in status from {url}")
            
            async with self._session.post(url, json={}, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Checking for eco mode in status data")
                    
                    found_eco_mode = False
                    
                    # Try to find eco mode at root level
                    if "eco_mode" in data:
                        device.eco_mode_enabled = bool(data.get("eco_mode", False))
                        found_eco_mode = True
                        logger.debug(f"Found eco_mode at root level in status: {device.eco_mode_enabled}")
                    
                    # Try to find eco mode in sys.device 
                    if not found_eco_mode and "sys" in data and "device" in data["sys"]:
                        sys_device = data["sys"]["device"]
                        logger.debug(f"[SYS.DEVICE] {ip}: {sys_device}")
                        
                        if "eco_mode" in sys_device:
                            device.eco_mode_enabled = bool(sys_device.get("eco_mode", False))
                            found_eco_mode = True
                            logger.debug(f"Found eco_mode in sys.device status: {device.eco_mode_enabled}")
                    
                    # Look for eco_mode in switch data
                    if not found_eco_mode:
                        for key in data:
                            if key.startswith("switch:"):
                                switch_data = data.get(key, {})
                                logger.debug(f"[SWITCH DATA] {ip} {key}: {switch_data}")
                                if "eco_mode" in switch_data:
                                    device.eco_mode_enabled = bool(switch_data.get("eco_mode", False))
                                    found_eco_mode = True
                                    logger.debug(f"Found eco_mode in {key} status: {device.eco_mode_enabled}")
                                    break
                    
                    if not found_eco_mode:
                        logger.debug(f"No eco mode found in status data for {ip}")
                else:
                    logger.debug(f"Non-200 response from {url}: {response.status}")
        except Exception as e:
            logger.debug(f"Error checking status for eco mode for {ip}: {e}")
            return

    def _get_sorted_devices(self) -> List[Device]:
        """Return devices sorted by IP address"""
        devices_list = list(self._devices.values())
        
        # Sort devices by IP address
        try:
            # Convert string IPs to ipaddress objects for proper sorting
            devices_list.sort(key=lambda device: ipaddress.ip_address(device.ip_address))
            logger.debug("Devices sorted by IP address")
        except Exception as e:
            logger.error(f"Error sorting devices by IP: {e}")
            # Return unsorted if there was an error
            
        return devices_list

    async def discover_device_capabilities(self, device: Device) -> bool:
        """
        Discover and save the capabilities for a specific device.
        
        Args:
            device: Device to discover capabilities for
            
        Returns:
            True if capabilities were successfully discovered, False otherwise
        """
        logger.info(f"Discovering capabilities for {device.id} at {device.ip_address}...")
        
        if not device.ip_address:
            logger.error(f"Cannot discover capabilities: Device {device.id} has no IP address")
            return False
            
        try:
            # Create capability discovery instance
            capability_discovery = CapabilityDiscovery(self._capabilities)
            
            # Ensure session is initialized
            if not self._session:
                self._session = aiohttp.ClientSession()
                
            # Discover device capabilities
            capability = await capability_discovery.discover_device_capabilities(device)
            
            if capability:
                logger.info(f"Successfully discovered capabilities for {device.id}")
                logger.info(f"APIs: {list(capability.supports_api)}")
                logger.info(f"Parameters: {list(capability.parameters.keys())}")
                return True
            else:
                logger.error(f"Failed to discover capabilities for {device.id}")
                return False
                
        except Exception as e:
            logger.error(f"Error discovering capabilities for {device.id}: {e}")
            return False
            
    async def discover_capabilities_for_all_devices(self) -> Dict[str, bool]:
        """
        Discover and save capabilities for all known devices.
        
        Returns:
            Dictionary with device IDs as keys and success status as values
        """
        logger.info(f"Discovering capabilities for all {len(self._devices)} known devices")
        
        results = {}
        
        for device_id, device in self._devices.items():
            success = await self.discover_device_capabilities(device)
            results[device_id] = success
            
        return results