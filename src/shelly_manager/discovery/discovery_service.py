import asyncio
import ipaddress
import logging
import yaml
import os
from typing import List, Optional, Callable, Dict, Any
from zeroconf import ServiceBrowser, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf
import aiohttp
from ..models.device import Device, DeviceGeneration, DeviceStatus
from datetime import datetime
from ..utils.logging import get_logger

# Get logger for this module
logger = get_logger(__name__)

class DiscoveryService:
    def __init__(self, debug: bool = False):
        self._devices: dict[str, Device] = {}
        self._callbacks: List[Callable[[Device], None]] = []
        self._zeroconf: Optional[AsyncZeroconf] = None
        self._browser: Optional[AsyncServiceBrowser] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._debug = debug
        self._device_types = self._load_device_types()
        
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
        
        # Start mDNS discovery
        logger.info("Starting mDNS discovery for _shelly._tcp.local")
        self._zeroconf = AsyncZeroconf()
        self._browser = AsyncServiceBrowser(
            self._zeroconf.zeroconf,
            ["_shelly._tcp.local."],
            handlers=[self._on_service_state_change]
        )
        logger.debug("Started mDNS browser for _shelly._tcp.local")

    async def stop(self):
        """Stop the discovery service"""
        logger.info("Stopping discovery service")
        if self._browser:
            await self._browser.async_cancel()
            logger.debug("Cancelled mDNS browser")
        if self._zeroconf:
            await self._zeroconf.async_close()
            logger.debug("Closed Zeroconf")
        if self._session:
            await self._session.close()
            logger.debug("Closed aiohttp session")

    def add_callback(self, callback: Callable[[Device], None]):
        """Add a callback to be called when a device is discovered"""
        logger.debug(f"Adding callback: {callback.__name__}")
        self._callbacks.append(callback)

    async def _on_service_state_change(self, zeroconf: Zeroconf, service_type: str, name: str, state_change: str):
        """Handle mDNS service state changes"""
        logger.debug(f"mDNS service state change: {state_change} for {name} ({service_type})")
        if state_change == "Added" or state_change == "Updated":
            info = await self._zeroconf.async_get_service_info(service_type, name)
            if info:
                logger.debug(f"Retrieved service info for {name}")
                # Parse device info from mDNS
                device = self._parse_mdns_info(info)
                logger.info(f"Discovered device via mDNS: {device.id} ({device.ip_address})")
                self._devices[device.id] = device
                # Save device info
                self._save_device_info(device)
                # Notify callbacks
                for callback in self._callbacks:
                    logger.debug(f"Notifying callback {callback.__name__} about device {device.id}")
                    callback(device)
        elif state_change == "Removed":
            logger.debug(f"Device removed from mDNS: {name}")
            # Optionally handle device removal
            # self._devices.pop(name, None)

    def _parse_mdns_info(self, info) -> Device:
        """Parse mDNS service info into a Device object"""
        # Extract data from TXT records
        txt_data = {k.decode(): v.decode() for k, v in info.properties.items()}
        logger.debug(f"Parsed mDNS TXT records: {txt_data}")
        
        # Extract common fields
        mac = txt_data.get("mac", "unknown")
        device_id = mac  # Always use MAC as device ID
        
        # Store raw device information
        raw_type = txt_data.get("type", "")
        raw_model = txt_data.get("model", "")
        raw_app = txt_data.get("app", "")
        
        # Determine generation based on response structure
        generation = DeviceGeneration.UNKNOWN
        if "gen" in txt_data:
            generation = DeviceGeneration(f"gen{txt_data['gen']}")
        elif raw_type.startswith("plus") or raw_type.startswith("shellyplus"):
            generation = DeviceGeneration.GEN2
        else:
            generation = DeviceGeneration.GEN1
        
        # Create device with common fields
        device = Device(
            id=device_id,
            name=txt_data.get("name", ""),
            generation=generation,
            ip_address=str(info.addresses[0]) if info.addresses else "unknown",
            mac_address=mac,
            firmware_version=txt_data.get("ver") or txt_data.get("fw", ""),
            status=DeviceStatus.ONLINE,
            discovery_method="mDNS",
            model=raw_model,
            slot=txt_data.get("slot"),
            auth_enabled=txt_data.get("auth_en"),
            auth_domain=txt_data.get("auth_domain"),
            fw_id=txt_data.get("fw_id"),
            raw_type=raw_type,
            raw_model=raw_model,
            raw_app=raw_app
        )
        
        logger.debug(f"Created Device object: {device}")
        return device

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
                discovery_method="HTTP",
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
        """Get additional settings for Gen1 devices"""
        if not self._session:
            return device

        try:
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
                    device.eco_mode_enabled = data.get("eco_mode_enabled", False)  # Set default to False
                    
                    logger.debug(f"Updated Gen1 device with settings: {device}")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.debug(f"Failed to get settings for {ip}: {str(e)}")
        except Exception as e:
            logger.debug(f"Unexpected error getting settings for {ip}: {str(e)}")
        
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
            # Create device info dictionary
            device_info = {
                "id": device.id,
                "name": device.name,
                "type": device.raw_type or "unknown",
                "generation": device.generation.value,
                "ip_address": device.ip_address,
                "mac_address": device.mac_address,
                "firmware_version": device.firmware_version,
                "status": device.status.value,
                "discovery_method": device.discovery_method,
                "last_seen": device.last_seen.isoformat(),
                "hostname": device.hostname,
                "timezone": device.timezone,
                "location": device.location,
                "wifi_ssid": device.wifi_ssid,
                "cloud_enabled": device.cloud_enabled,
                "cloud_connected": device.cloud_connected,
                "mqtt_enabled": device.mqtt_enabled,
                "mqtt_server": device.mqtt_server,
                "num_outputs": device.num_outputs,
                "num_meters": device.num_meters,
                "max_power": device.max_power,
                "eco_mode_enabled": device.eco_mode_enabled,
                "model": device.model,
                "slot": device.slot,
                "auth_enabled": device.auth_enabled,
                "auth_domain": device.auth_domain,
                "fw_id": device.fw_id,
                "raw_type": device.raw_type,
                "raw_model": device.raw_model,
                "raw_app": device.raw_app
            }
            
            # Create filename from device ID
            filename = f"{device.id}.yaml"
            filepath = os.path.join("data", "devices", filename)
            
            # Create directories if they don't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save to file
            with open(filepath, 'w') as f:
                yaml.dump(device_info, f, default_flow_style=False)
                
            logger.debug(f"Saved device info to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save device info: {e}")

    @property
    def devices(self) -> List[Device]:
        """Get list of all discovered devices"""
        return list(self._devices.values())

    async def discover_devices(self, network: str = None, force_http: bool = False, ip_addresses: List[str] = None) -> List[Device]:
        """Discover Shelly devices on the network or at specific IP addresses"""
        logger.info("Starting device discovery")
        
        try:
            # Start discovery service
            await self._start_discovery()
            
            # If IP addresses are provided, use them directly
            if ip_addresses:
                logger.info(f"Discovering devices at {len(ip_addresses)} specific IP addresses")
                await self._probe_specific_ips(ip_addresses)
                # Return discovered devices
                return list(self._devices.values())
            
            # If no specific IPs provided, proceed with normal discovery
            if not network:
                network = "192.168.1.0/24"
            
            # Start mDNS discovery
            logger.info(f"Starting mDNS discovery for _shelly._tcp.local")
            mdns_devices = await self._discover_mdns()
            
            # If devices found via mDNS and not forcing HTTP, return them
            if mdns_devices and not force_http:
                logger.info(f"Found {len(mdns_devices)} devices via mDNS")
                return list(self._devices.values())
            elif mdns_devices:
                logger.info(f"Found {len(mdns_devices)} devices via mDNS, but forcing HTTP probing")
            else:
                logger.info("No devices found via mDNS, falling back to HTTP probing")
            
            # Probe network for devices
            logger.info(f"Probing network {network}")
            await self._probe_network(network)
            
            # Return discovered devices
            return list(self._devices.values())
        finally:
            # Clean up resources
            await self.stop()

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
        """Discover devices via mDNS"""
        await asyncio.sleep(5)  # Wait for mDNS discovery to complete
        return list(self._devices.values())

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
        """Probe a single IP address for a Shelly device"""
        if not self._session:
            return None

        max_retries = retries
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries + 1):  # +1 for the initial attempt
            try:
                logger.debug(f"Probing {ip} (attempt {attempt+1}/{max_retries+1})")
                
                # Try to access the /shelly endpoint for device information
                url = f"http://{ip}/shelly"
                logger.debug(f"Requesting {url}")
                
                async with self._session.get(url, timeout=8) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"Received response from {ip}: {data}")
                        
                        # Parse response into a Device object
                        device = self._parse_shelly_response(ip, data)
                        
                        if device:
                            # Get additional settings based on device generation
                            if device.generation == DeviceGeneration.GEN1:
                                device = await self._get_gen1_settings(ip, device)
                            else:  # Gen2+
                                device = await self._get_gen2_config(ip, device)
                            
                            logger.info(f"Discovered device via HTTP: {device.id} ({ip})")
                            return device
                        
                        return None
                    else:
                        logger.debug(f"Non-200 response from {ip}: {response.status}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < max_retries:
                    logger.debug(f"Connection error for {ip}, retrying: {str(e)}")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.debug(f"Connection error for {ip} after {max_retries+1} attempts: {str(e)}")
            except Exception as e:
                logger.debug(f"Unexpected error for {ip}: {str(e)}")
                break
        
        return None