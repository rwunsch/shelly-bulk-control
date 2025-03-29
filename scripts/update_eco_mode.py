#!/usr/bin/env python3
"""
Example script that demonstrates using the device capabilities system
to update the eco_mode parameter on all compatible devices.

This script shows how to:
1. Discover devices on the network
2. Check if each device supports the eco_mode parameter
3. Set the eco_mode parameter on compatible devices
"""
import asyncio
import argparse
import sys
import os
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.shelly_manager.discovery.discovery_service import DiscoveryService
from src.shelly_manager.models.device_capabilities import device_capabilities, CapabilityDiscovery
from src.shelly_manager.models.device_registry import device_registry
from src.shelly_manager.parameter.parameter_service import ParameterService
from src.shelly_manager.grouping.group_manager import GroupManager
from src.shelly_manager.utils.logging import LogConfig, get_logger

# Configure logging
log_config = LogConfig(debug=True)
log_config.setup()
logger = logging.getLogger(__name__)

async def main():
    """Main function that demonstrates using device capabilities."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Update eco_mode on compatible Shelly devices")
    parser.add_argument("--enable", action="store_true", help="Enable eco_mode (default: disable)")
    parser.add_argument("--network", type=str, default="192.168.1.0/24", help="Network to scan")
    parser.add_argument("--force-discovery", action="store_true", help="Force discovery of device capabilities")
    args = parser.parse_args()
    
    # Set eco_mode value
    eco_mode_value = args.enable
    
    # Initialize services
    discovery_service = DiscoveryService(network=args.network)
    group_manager = GroupManager()
    parameter_service = ParameterService(group_manager, discovery_service)
    
    logger.info("Starting device discovery...")
    await discovery_service.start_discovery_service()
    
    try:
        # Discover devices
        devices = await discovery_service.discover_devices()
        
        if not devices:
            logger.error("No devices found.")
            return
        
        logger.info(f"Found {len(devices)} devices")
        
        # Save discovered devices to registry
        for device in devices:
            device_registry.save_device(device)
        
        # Discover capabilities if requested
        if args.force_discovery:
            logger.info("Discovering device capabilities...")
            capability_discovery = CapabilityDiscovery(device_capabilities)
            
            for device in devices:
                logger.info(f"Discovering capabilities for {device.id}...")
                try:
                    capability = await capability_discovery.discover_device_capabilities(device)
                    if capability:
                        logger.info(f"Successfully discovered capabilities for {device.id}")
                except Exception as e:
                    logger.error(f"Error discovering capabilities for {device.id}: {e}")
        
        # Find devices that support eco_mode
        compatible_devices = []
        for device in devices:
            # Get device capability
            capability = device_capabilities.get_capability_for_device(device)
            if capability and capability.has_parameter("eco_mode"):
                compatible_devices.append(device)
        
        if not compatible_devices:
            logger.error("No devices support eco_mode parameter.")
            return
        
        logger.info(f"Found {len(compatible_devices)} devices that support eco_mode")
        
        # Set eco_mode on compatible devices
        success_count = 0
        for device in compatible_devices:
            logger.info(f"Setting eco_mode to {eco_mode_value} on {device.id}...")
            result = await parameter_service.set_parameter(device.id, "eco_mode", eco_mode_value)
            
            if "error" in result:
                logger.error(f"Failed to set eco_mode on {device.id}: {result['error']}")
            else:
                logger.info(f"Successfully set eco_mode to {eco_mode_value} on {device.id}")
                success_count += 1
        
        logger.info(f"Successfully updated eco_mode on {success_count} of {len(compatible_devices)} compatible devices")
        
    finally:
        # Clean up
        await discovery_service.stop_discovery_service()

if __name__ == "__main__":
    asyncio.run(main()) 