#!/usr/bin/env python3
"""
Script to discover and update device capabilities for Shelly devices.

This script connects to specific Shelly devices by IP address and:
1. Discovers all available APIs
2. Updates or creates the capability definition YAML file
"""
import asyncio
import argparse
import sys
import os
import logging
import aiohttp
import ipaddress
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Add src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.shelly_manager.utils.logging import LogConfig, get_logger
from src.shelly_manager.models.device import Device, DeviceGeneration
from src.shelly_manager.models.device_capabilities import device_capabilities, CapabilityDiscovery

# Configure logging
log_config = LogConfig(debug=True)
log_config.setup()
logger = logging.getLogger(__name__)

async def scan_network(network):
    """Scan a network for Shelly devices."""
    logger.info(f"Scanning network {network} for Shelly devices...")
    
    # Parse the network CIDR notation
    network = ipaddress.IPv4Network(network)
    
    # List to store found device IPs
    found_devices = []
    
    # Semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(16)
    
    async def check_ip(ip):
        """Check if a Shelly device is at this IP."""
        async with semaphore:
            ip_str = str(ip)
            
            try:
                # Fast check with a timeout
                info = await asyncio.wait_for(discover_device_info(ip_str), timeout=10)
                if info:
                    logger.info(f"Found Shelly device at {ip_str}: {info}")
                    found_devices.append(ip_str)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.debug(f"Error checking {ip_str}: {e}")
    
    # Create tasks for all IP addresses in the network
    tasks = [check_ip(ip) for ip in network.hosts()]
    
    # Run all tasks concurrently and wait for them to complete
    await asyncio.gather(*tasks)
    
    logger.info(f"Found {len(found_devices)} Shelly devices on the network")
    return found_devices

async def discover_device_info(ip_address):
    """Get basic device information to create a Device object."""
    logger.info(f"Discovering device information for {ip_address}...")
    
    # First try Gen2 API
    async with aiohttp.ClientSession() as session:
        try:
            # Try Gen2 Shelly.GetDeviceInfo
            url = f"http://{ip_address}/rpc/Shelly.GetDeviceInfo"
            async with session.post(url, json={}, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Found Gen2 device: {data}")
                    return {
                        "id": data.get("id", ""),
                        "mac": data.get("mac", ""),
                        "model": data.get("model", ""),
                        "gen": 2,
                        "app": data.get("app", ""),
                        "name": data.get("name", "")
                    }
        except Exception as e:
            logger.debug(f"Not a Gen2 device: {e}")
            
        try:
            # Try Gen1 /shelly endpoint
            url = f"http://{ip_address}/shelly"
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Found Gen1 device: {data}")
                    return {
                        "id": data.get("mac", "").replace(":", "").lower(),
                        "mac": data.get("mac", ""),
                        "type": data.get("type", ""),
                        "gen": 1,
                        "name": data.get("hostname", "")
                    }
        except Exception as e:
            logger.debug(f"Not a Gen1 device: {e}")
    
    logger.error(f"Could not identify device at {ip_address}")
    return None

async def create_device_object(ip_address, device_info):
    """Create a Device object from device info."""
    if not device_info:
        return None
        
    if device_info["gen"] == 2:
        return Device(
            id=device_info["id"],
            name=device_info["name"] or device_info["id"],
            generation=DeviceGeneration.GEN2,
            raw_app=device_info["app"],
            raw_model=device_info["model"],
            ip_address=ip_address,
            mac_address=device_info["mac"],
        )
    else:
        return Device(
            id=device_info["id"],
            name=device_info["name"] or device_info["id"],
            generation=DeviceGeneration.GEN1,
            raw_type=device_info["type"],
            ip_address=ip_address,
            mac_address=device_info["mac"],
        )

async def discover_and_save_capabilities(ip_address):
    """Discover and save capabilities for a device."""
    device_info = await discover_device_info(ip_address)
    if not device_info:
        logger.error(f"Failed to discover device at {ip_address}")
        return False
        
    device = await create_device_object(ip_address, device_info)
    if not device:
        logger.error(f"Failed to create device object for {ip_address}")
        return False
    
    logger.info(f"Discovering capabilities for {device.id} at {ip_address}...")
    
    # Create capability discovery instance
    capability_discovery = CapabilityDiscovery(device_capabilities)
    
    # Discover capabilities
    capability = await capability_discovery.discover_device_capabilities(device)
    if not capability:
        logger.error(f"Failed to discover capabilities for {device.id}")
        return False
    
    logger.info(f"Successfully discovered capabilities for {device.id}")
    logger.info(f"APIs: {list(capability.apis.keys())}")
    logger.info(f"Parameters: {list(capability.parameters.keys())}")
    
    # Check if saved successfully
    if capability and device_capabilities.save_capability(capability):
        logger.info(f"Saved capability definition to config/device_capabilities/{capability.device_type}.yaml")
        return True
    else:
        logger.error(f"Failed to save capability definition for {device.id}")
        return False

async def interactive_selection(device_ips):
    """Allow user to select which device to discover capabilities for."""
    if not device_ips:
        logger.error("No devices found to select from")
        return None
    
    # Get device info for each IP
    device_info_list = []
    for ip in device_ips:
        info = await discover_device_info(ip)
        if info:
            device_info_list.append((ip, info))
    
    # Display options to user
    print("\nFound Shelly devices:")
    for i, (ip, info) in enumerate(device_info_list):
        device_type = info.get("app") if info.get("gen") == 2 else info.get("type")
        print(f"{i+1}. IP: {ip}, Type: {device_type}, ID: {info.get('id')}")
    
    # Get user selection
    try:
        selection = int(input("\nSelect a device (number): "))
        if 1 <= selection <= len(device_info_list):
            return device_info_list[selection-1][0]
        else:
            logger.error("Invalid selection")
            return None
    except ValueError:
        logger.error("Invalid input")
        return None

async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Discover device capabilities and update YAML files")
    parser.add_argument("--ip", help="IP address of the device to discover")
    parser.add_argument("--network", default="192.168.1.0/24", help="Network to scan (CIDR notation)")
    parser.add_argument("--scan", action="store_true", help="Scan network for devices and select interactively")
    
    args = parser.parse_args()
    
    ip_address = args.ip
    
    # If no IP specified or scan requested, scan the network
    if not ip_address or args.scan:
        device_ips = await scan_network(args.network)
        if not device_ips:
            logger.error(f"No Shelly devices found on network {args.network}")
            sys.exit(1)
            
        # If scan only, let user select a device
        if not ip_address:
            ip_address = await interactive_selection(device_ips)
            if not ip_address:
                logger.error("No device selected")
                sys.exit(1)
    
    # Discover and save capabilities
    success = await discover_and_save_capabilities(ip_address)
    if success:
        logger.info("Discovery completed successfully")
    else:
        logger.error("Discovery failed")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 