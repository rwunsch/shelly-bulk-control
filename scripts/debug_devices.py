#!/usr/bin/env python3
"""Debug script to print device details for a group."""

import asyncio
import sys
import os
import logging

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shelly_manager.parameters.parameter_service import ParameterService
from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.utils.logging import LogConfig

# Configure logging
log_config = LogConfig(debug=True)
log_config.setup()
logger = logging.getLogger(__name__)

GROUP_NAME = "eco_enabled_small"

async def main():
    """Main entry point."""
    logger.info(f"Debugging devices in group: {GROUP_NAME}")
    
    # Create services
    group_manager = GroupManager("data/groups")
    parameter_service = ParameterService(group_manager)
    
    # Load devices for the group
    devices = await parameter_service.load_devices_for_group(GROUP_NAME)
    logger.info(f"Found {len(devices)} devices in group {GROUP_NAME}")
    
    # Print device details
    for device in devices:
        logger.info(f"Device ID: {device.id}")
        logger.info(f"  Model: {device.model}")
        logger.info(f"  Generation: {device.generation}")
        logger.info(f"  IP Address: {device.ip_address}")
        
        # Get supported parameters for this device
        params = parameter_service.get_device_parameters(device)
        logger.info(f"  Supported parameters: {list(params.keys())}")
        
        # Check specific parameters
        eco_mode_supported = "eco_mode" in params
        logger.info(f"  eco_mode supported: {eco_mode_supported}")
        
        # Print parameter details for eco_mode if supported
        if eco_mode_supported:
            param_def = params["eco_mode"]
            logger.info(f"  eco_mode parameter definition:")
            logger.info(f"    Gen2 method: {param_def.gen2_method}")
            logger.info(f"    Gen2 component: {param_def.gen2_component}")
            logger.info(f"    Gen2 property: {param_def.gen2_property}")
            
            # Print parameter model match
            logger.info(f"  Parameter model match for device {device.id}, model {device.model}")
        
        logger.info("")  # Empty line between devices
    
    # Stop parameter service
    await parameter_service.stop()

if __name__ == "__main__":
    asyncio.run(main()) 