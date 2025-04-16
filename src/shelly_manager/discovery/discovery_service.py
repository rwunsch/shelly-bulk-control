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
        logger.debug(f"Service found: {name} ({service_type})")
        info = zeroconf.get_service_info(service_type, name)
        if info:
            # Process service info
            if 'shelly' in name.lower() or service_type == '_shelly._tcp.local.' or self.discovery_service._is_shelly_device(info):
                logger.debug(f"Found Shelly device: {name}")
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
                    
                    logger.info(f"Discovered Shelly device via mDNS at IP: {ip_address} ({name})")
                    
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
                logger.debug(f"Updated Shelly device: {name}")
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
                    
                    logger.info(f"Updated Shelly device: {name} - via mDNS at IP: {ip_address}")
                    
                    # Queue this IP for detailed HTTP discovery
                    self.discovery_service._queue_ip_for_http_discovery(ip_address, name, service_type)

class DiscoveryService:
    def __init__(self, debug: bool = False, chunk_size: int = 16, mdns_timeout: int = 10):
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
        # Configurable parameters
        self._chunk_size = chunk_size
        self._mdns_timeout = mdns_timeout
        
        logger.info("Initializing DiscoveryService")
        logger.debug(f"Debug mode: {debug}")
        logger.debug(f"Chunk size: {chunk_size}")
        logger.debug(f"mDNS timeout: {mdns_timeout}")

    def _load_device_types(self) -> Dict[str, Any]:
        """Load device types configuration from YAML"""
        config_path = os.path.join("config", "device_types.yaml")
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load device types configuration: {e}")
            return {"gen1_devices": {}, "gen2_devices": {}}

    async def _ensure_session(self):
        """Ensure an HTTP session exists, creating one if needed"""
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession()
            logger.debug("Created new aiohttp session")
        return self._session
        
    async def start(self):
        """Start the discovery service"""
        logger.info("Starting discovery service")
        
        # Initialize aiohttp session for HTTP probing (fallback)
        await self._ensure_session()
        
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

    async def discover_devices(self, network: str = None, force_http: bool = False, ip_addresses: List[str] = None, auto_optimize: bool = True) -> List[Device]:
        """
        Discover Shelly devices on the network.
        
        Args:
            network: Network CIDR to scan (e.g., "192.168.1.0/24")
            force_http: Whether to force HTTP probing even if mDNS is available
            ip_addresses: List of specific IP addresses to probe
            auto_optimize: Whether to automatically optimize chunk size based on network conditions
            
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
                
        # Initialize aiohttp session for HTTP probing
        await self._ensure_session()
        
        # Optimize chunk size if requested
        if auto_optimize:
            optimal_chunk_size = await self._estimate_optimal_chunk_size(network)
            self._chunk_size = optimal_chunk_size
            logger.info(f"Auto-optimized chunk size: {self._chunk_size}")
        
        # Determine if we need to probe specific IPs
        if ip_addresses:
            logger.info(f"Probing specific IP addresses: {ip_addresses}")
            await self._probe_specific_ips(ip_addresses)
        else:
            # Different approach based on discovery method
            if force_http:
                # Skip mDNS completely when force_http is set
                logger.info(f"Force-HTTP mode: Scanning network {network} directly...")
                await self._probe_network(network)
            else:
                # Use combined mDNS + HTTP approach
                logger.info(f"Scanning network {network} for devices using mDNS...")
                
                # Start mDNS discovery for general network scan
                await self.start()
                
                # Perform mDNS discovery
                logger.info("Starting mDNS discovery")
                await self._discover_mdns()
                
                # If mDNS didn't find any devices, fall back to network probe
                if len(self._mdns_discovered_ips) == 0:
                    logger.info(f"No devices found via mDNS, falling back to HTTP scan of network {network}...")
                    await self._probe_network(network)
        
        # Process the discovery queue
        await self._process_discovery_queue()
        
        # Stop the discovery service if it was started
        if not force_http and not ip_addresses:
            await self.stop()
        elif self._session:
            # Just close the HTTP session if we're in force_http mode
            await self._session.close()
            self._session = None
        
        # Return list of discovered devices
        return self._get_sorted_devices()

    async def _process_discovery_queue(self):
        """Process the queue of IP addresses for HTTP discovery"""
        logger.info(f"Processing {len(self._discovery_queue)} IP addresses for HTTP discovery")
        
        # Convert the set to a list for iteration
        queue_list = list(self._discovery_queue)
        self._discovery_queue.clear()  # Clear the queue after copying
        
        # Filter out already discovered IPs
        queue_list = [ip for ip in queue_list if ip not in self._discovered_ips]
        logger.info(f"Filtered queue contains {len(queue_list)} unique IP addresses")
        
        # Mark all as discovered to prevent duplicates in future runs
        self._discovered_ips.update(queue_list)
        
        # Process IPs in parallel using asyncio.gather
        if queue_list:
            logger.info(f"Processing IPs in parallel batches of {self._chunk_size}")
            
            # Process in chunks to avoid creating too many concurrent connections
            for i in range(0, len(queue_list), self._chunk_size):
                chunk = queue_list[i:i + self._chunk_size]
                logger.debug(f"Processing chunk of {len(chunk)} IPs")
                
                # Create probe tasks for all IPs in this chunk
                tasks = [self._probe_device(ip) for ip in chunk]
                
                # Run them concurrently and wait for all to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Error probing device at {chunk[i]}: {result}")
                    elif result:  # We got a device
                        device = result
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
        
        logger.info(f"HTTP discovery complete. Found {len(self._devices)} devices")

    async def _probe_specific_ips(self, ip_addresses: List[str]) -> None:
        """Probe specific IP addresses for Shelly devices"""
        await self._ensure_session()
        
        logger.info(f"Probing {len(ip_addresses)} specific IP addresses")
        
        # Process IPs in parallel based on configured chunk size
        chunk_size = self._chunk_size
        logger.info(f"Using chunk size of {chunk_size} for IP probing")
        
        # Track statistics
        total_discovered = 0
        total_errors = 0
        chunks_processed = 0
        
        # Process IPs in chunks to limit concurrent connections
        for i in range(0, len(ip_addresses), chunk_size):
            chunks_processed += 1
            chunk = ip_addresses[i:i + chunk_size]
            logger.info(f"Processing chunk {chunks_processed}/{(len(ip_addresses) + chunk_size - 1) // chunk_size} ({len(chunk)} IPs)")
            
            # Create tasks for all IPs in this chunk
            tasks = [self._probe_device(ip) for ip in chunk]
            
            # Run them concurrently and wait for all to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error probing device at {chunk[j]}: {result}")
                    total_errors += 1
                elif result:  # We got a device
                    device = result
                    # Add device to discovered devices
                    self._devices[device.id] = device
                    
                    # Save device info
                    self._save_device_info(device)
                    
                    # Add to discovery queue and track as discovered
                    self._discovery_queue.add(device.ip_address)
                    self._discovered_ips.add(device.ip_address)
                    
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
            
            # Log chunk progress
            logger.info(f"Chunk {chunks_processed} complete. Discovered: {total_discovered}, Errors: {total_errors}")
                
        logger.info(f"IP probe complete. Discovered {total_discovered} devices, encountered {total_errors} errors")

    async def _discover_mdns(self):
        """Discover devices via mDNS - collect IPs only"""
        logger.info("Waiting for mDNS discovery to complete...")
        
        # Configurable parameters
        discovery_time = self._mdns_timeout  # maximum seconds to wait
        check_interval = 1  # seconds between checks
        early_termination_threshold = 3  # consecutive intervals with no new devices
        
        # Track discovery progress
        start_time = time.time()
        consecutive_no_discovery = 0
        previous_device_count = len(self._discovery_queue)
        
        # Wait for mDNS discovery, with potential early termination
        for i in range(discovery_time):
            await asyncio.sleep(check_interval)
            current_device_count = len(self._discovery_queue)
            
            if current_device_count > previous_device_count:
                # Found new devices in this interval
                new_devices = current_device_count - previous_device_count
                logger.info(f"Found {new_devices} new IPs after {i+1} seconds (total: {current_device_count})")
                previous_device_count = current_device_count
                consecutive_no_discovery = 0  # Reset counter since we found devices
            else:
                # No new devices in this interval
                consecutive_no_discovery += 1
                logger.debug(f"No new devices found in interval {i+1}. ({consecutive_no_discovery}/{early_termination_threshold})")
                
                # Check for early termination if we've already found some devices
                if (current_device_count > 0 and 
                    consecutive_no_discovery >= early_termination_threshold):
                    logger.info(f"mDNS discovery terminating early after {i+1} seconds due to no new devices")
                    break
        
        elapsed_time = time.time() - start_time
        
        # If no devices found, provide more debugging info
        if len(self._discovery_queue) == 0:
            logger.warning(f"No device IPs found via mDNS after {elapsed_time:.1f} seconds")
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
            logger.info(f"Successfully collected {len(self._discovery_queue)} device IPs via mDNS in {elapsed_time:.1f} seconds")

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
            
            # Determine optimal chunk size based on network conditions
            chunk_size = await self._estimate_optimal_chunk_size(network)
            logger.info(f"Using chunk size of {chunk_size} for network probing")
            
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
        await self._ensure_session()

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
                    device = await self._get_gen1_details(ip, device)
                else:  # Gen2+ devices
                    logger.debug(f"Detected Gen2/Gen3/Gen4 device at {ip}, getting device info")
                    device = await self._get_gen2plus_details(ip, device)

                # Log the discovered device
                logger.debug(f"Discovered device via {device.discovery_method}: {device.id} ({ip})")
                logger.debug(f"  Name: {device.name}")
                logger.debug(f"  Type: {device.raw_type}")
                logger.debug(f"  Model: {device.model}")
                logger.debug(f"  Generation: {device.generation.value}")
                logger.debug(f"  Firmware: {device.firmware_version}")
                logger.debug(f"  Updates: {device.has_update}")
                
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
                        device = await self._create_device_from_shelly_response(ip, data)
                        return device
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

    async def _create_device_from_shelly_response(self, ip: str, data: Dict[str, Any]) -> Optional[Device]:
        """Parse /shelly endpoint response into a Device object"""
        logger.debug(f"Parsing response from {ip}: {data}")
        
        try:
            # Extract common fields
            mac = data.get("mac", "unknown")
            # Format MAC address consistently (uppercase, no colons)
            formatted_mac = self._format_mac(mac, uppercase=True, include_colons=False)
            device_id = formatted_mac  # Always use formatted MAC as device ID
            
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
                mac_address=self._format_mac(mac, uppercase=False, include_colons=False),  # Store without colons
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

    async def _get_gen1_details(self, ip: str, device: Device) -> Device:
        """Get comprehensive details for a Gen1 device"""
        if not self._session:
            return device

        try:
            # Get settings
            url = f"http://{ip}/settings"
            logger.debug(f"Getting settings from {url}")
            async with self._session.get(url, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Received settings from {ip}: {data}")
                    
                    # Update device with settings information
                    device.name = data.get("name", "")
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
                    
                    # Device specific information from settings
                    device_info = data.get("device", {})
                    device.num_outputs = device_info.get("num_outputs")
                    device.num_meters = device_info.get("num_meters")
                    device.max_power = data.get("max_power")
                    
            # Check firmware update status
            url = f"http://{ip}/status"
            logger.debug(f"Getting status from {url}")
            
            async with self._session.get(url, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Received status from {ip}: {data}")
                    
                    # Check update status
                    if "update" in data:
                        update_info = data.get("update", {})
                        device.has_update = update_info.get("has_update", False)
                        
                        if device.has_update:
                            logger.info(f"Firmware update available for {device.name} ({ip}): "
                                      f"Current: {update_info.get('old_version', 'unknown')}, "
                                      f"New: {update_info.get('new_version', 'unknown')}")
                        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.debug(f"Failed to get Gen1 details for {ip}: {str(e)}")
        except Exception as e:
            logger.debug(f"Unexpected error getting Gen1 details for {ip}: {str(e)}")
        
        return device

    async def _get_gen2plus_details(self, ip: str, device: Device) -> Device:
        """Get comprehensive details for Gen2+ devices"""
        if not self._session:
            return device

        try:
            # First try GetDeviceInfo (more comprehensive)
            url = f"http://{ip}/rpc/Shelly.GetDeviceInfo"
            logger.debug(f"Getting device info from {url}")

            async with self._session.post(url, json={}, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Received device info from {ip}: {data}")

                    # Update device with information from GetDeviceInfo
                    if "name" in data:
                        device.name = data["name"]
                    if "id" in data:
                        device.id = data["id"]
                    if "mac" in data:
                        # Use standardized MAC format without colons
                        device.mac_address = self._format_mac(data["mac"], uppercase=False, include_colons=False)
                    if "model" in data:
                        device.model = data["model"]
                    if "fw_version" in data:
                        device.firmware_version = data["fw_version"]
            
            # Get config information
            url = f"http://{ip}/rpc/Shelly.GetConfig"
            logger.debug(f"Getting config from {url}")
            
            async with self._session.post(url, json={}, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Received config from {ip}: {data}")
                    
                    # System information
                    sys = data.get("sys", {})
                    sys_device = sys.get("device", {})
                    
                    # If name wasn't in device info, get it from config
                    if not device.name and "name" in sys_device:
                        device.name = sys_device.get("name")
                    
                    device.hostname = sys_device.get("name")  # Use name as hostname for Gen2+
                    
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
            
            # Check status and update information
            url = f"http://{ip}/rpc/Shelly.GetStatus"
            logger.debug(f"Getting status from {url}")
            
            async with self._session.post(url, json={}, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Received status from {ip}: {data}")
                    
                    # Check for updates
                    if "sys" in data and "available_updates" in data["sys"]:
                        available_updates = data["sys"]["available_updates"]
                        
                        # Only consider stable updates, ignore beta updates
                        device.has_update = "stable" in available_updates
                        
                        if device.has_update:
                            stable_version = available_updates.get("stable", {}).get("version")
                            logger.info(f"Stable update available for {device.name or device.id} ({ip}): {stable_version}")
                    
                    # Fallback check if sys.available_updates not present
                    elif "cloud" in data and "available_updates" in data["cloud"]:
                        available_updates = data["cloud"]["available_updates"]
                        device.has_update = "stable" in available_updates
                        
                    # Second fallback for older firmware
                    elif "cloud" in data and "new_fw" in data["cloud"]:
                        device.has_update = bool(data["cloud"]["new_fw"])
                        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            logger.debug(f"Failed to get Gen2+ details for {ip}: {str(e)}")
        except Exception as e:
            logger.debug(f"Unexpected error getting Gen2+ details for {ip}: {str(e)}")
        
        return device

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
            await self._ensure_session()
                
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

    def _format_mac(self, mac_address: str, uppercase: bool = True, include_colons: bool = False) -> str:
        """
        Standardize MAC address formatting.
        
        Args:
            mac_address: The MAC address to format
            uppercase: Whether to return uppercase (True) or lowercase (False)
            include_colons: Whether to include colons in the formatted MAC
            
        Returns:
            Formatted MAC address string
        """
        if not mac_address:
            return "unknown"
            
        # Remove any separators (colons, hyphens, dots)
        clean_mac = mac_address.replace(":", "").replace("-", "").replace(".", "")
        
        # Ensure correct format
        if len(clean_mac) != 12:
            logger.warning(f"Invalid MAC address format: {mac_address}")
            return mac_address
            
        # Format with or without colons
        if include_colons:
            formatted_mac = ":".join([clean_mac[i:i+2] for i in range(0, 12, 2)])
        else:
            formatted_mac = clean_mac
            
        # Apply case formatting
        return formatted_mac.upper() if uppercase else formatted_mac.lower()

    async def _estimate_optimal_chunk_size(self, network: str = None) -> int:
        """
        Estimates optimal chunk size for parallel processing based on network conditions and system resources.
        
        Args:
            network: Optional network CIDR to use for testing
            
        Returns:
            Recommended chunk size for parallel processing
        """
        # Default chunk size as fallback
        default_chunk_size = self._chunk_size
        
        try:
            # Get available CPU cores
            import multiprocessing
            available_cores = multiprocessing.cpu_count()
            
            # Adjust for hyper-threading - we want physical cores
            physical_cores = max(1, available_cores // 2)
            
            # Start with a base multiplier
            base_multiplier = 2
            
            # Test network latency to determine if we should increase/decrease
            test_ip = None
            
            # If network specified, use first IP in that network
            if network:
                network_obj = ipaddress.ip_network(network)
                hosts = list(network_obj.hosts())
                if hosts:
                    test_ip = str(hosts[0])
            
            # Fallback to gateway IP
            if not test_ip:
                gateway = None
                try:
                    # Try to get default gateway
                    import socket
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.connect(("8.8.8.8", 80))
                    local_ip = s.getsockname()[0]
                    s.close()
                    
                    # Extract first three octets and append .1 as common gateway
                    gateway = ".".join(local_ip.split(".")[:3]) + ".1"
                except Exception:
                    pass
                
                test_ip = gateway or "192.168.1.1"  # Fallback to common gateway
            
            # Test latency
            import asyncio
            import time
            latency_ms = 100  # Default assumption
            
            # Create a simple HTTP GET request to measure latency
            await self._ensure_session()
            try:
                start_time = time.time()
                async with self._session.get(f"http://{test_ip}", timeout=2) as response:
                    # Just getting the response status is enough
                    status = response.status
                    # Calculate latency
                    latency_ms = (time.time() - start_time) * 1000
            except Exception:
                # If timeout or error, assume high latency
                latency_ms = 500
            
            # Adjust multiplier based on latency
            if latency_ms < 10:  # Very fast network
                base_multiplier = 4
            elif latency_ms < 50:  # Fast network
                base_multiplier = 3
            elif latency_ms > 200:  # Slow network
                base_multiplier = 1
            
            # Calculate chunk size based on cores and network conditions
            chunk_size = physical_cores * base_multiplier
            
            # Cap at reasonable limits
            chunk_size = max(4, min(chunk_size, 32))
            
            logger.info(f"Estimated optimal chunk size: {chunk_size} (latency: {latency_ms:.1f}ms, physical cores: {physical_cores})")
            return chunk_size
            
        except Exception as e:
            logger.warning(f"Error estimating optimal chunk size: {e}, using default ({default_chunk_size})")
            return default_chunk_size