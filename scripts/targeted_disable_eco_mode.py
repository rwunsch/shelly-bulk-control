#!/usr/bin/env python3
"""
Script to disable ECO mode on devices in the eco_enabled_small group using targeted approach.
This approach only probes devices in the group rather than scanning the entire network.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.parameters.parameter_service import ParameterService
from shelly_manager.utils.logging import LogConfig

# Configure logging
log_config = LogConfig(
    app_name="targeted_disable_eco_mode",
    debug=True,
    log_to_file=True,
    log_to_console=True
)
log_config.setup()
logger = logging.getLogger("targeted_disable_eco_mode")

# Group to modify
GROUP_NAME = "eco_enabled_small"
PARAMETER_NAME = "eco_mode"
PARAMETER_VALUE = False


async def disable_eco_mode():
    """
    Disable ECO mode on devices in the specified group using targeted approach.
    This only probes the devices in the group rather than scanning the entire network.
    """
    logger.info(f"Starting script to disable ECO mode on devices in '{GROUP_NAME}' group")
    
    # Initialize services
    group_manager = GroupManager()
    parameter_service = ParameterService(group_manager)
    
    # Start services
    logger.info("Starting parameter service")
    await parameter_service.start()
    
    try:
        # Verify group exists
        group = group_manager.get_group(GROUP_NAME)
        if not group:
            logger.error(f"Group '{GROUP_NAME}' not found")
            return
            
        # Make sure devices directory exists
        device_dir = os.path.join("data", "devices")
        if not os.path.exists(device_dir):
            os.makedirs(device_dir, exist_ok=True)
            logger.info(f"Created device storage directory: {device_dir}")
        
        # Apply parameter change
        logger.info(f"Applying parameter '{PARAMETER_NAME}={PARAMETER_VALUE}' to group '{GROUP_NAME}'")
        
        # Debug: Print device details
        devices = await parameter_service.load_devices_for_group(GROUP_NAME)
        for device in devices:
            logger.info(f"Device details: ID={device.id}, Model={device.model}, Gen={device.generation}, IP={device.ip_address}")
            params = parameter_service.get_device_parameters(device)
            logger.info(f"  Parameters supported: {list(params.keys())}")
        
        result = await parameter_service.apply_parameter_to_group(GROUP_NAME, PARAMETER_NAME, PARAMETER_VALUE)
        
        # Print results
        if "error" in result:
            logger.error(f"Error applying parameter: {result['error']}")
            return
            
        if "warning" in result:
            logger.warning(f"Warning applying parameter: {result['warning']}")
            return
            
        # Log detailed results
        logger.info(f"Parameter applied to {result['device_count']} devices")
        
        success_count = sum(1 for r in result["results"].values() if r.get("success", False))
        if result["device_count"] > 0:
            success_rate = success_count / result["device_count"] * 100
            logger.info(f"Success rate: {success_count}/{result['device_count']} ({success_rate:.0f}%)")
        
        # Log failures
        for device_id, device_result in result["results"].items():
            if not device_result.get("success", False):
                error = device_result.get("error", "Unknown error")
                logger.error(f"Failed to apply parameter to device {device_id}: {error}")
        
        # Log successful operation
        if success_count == result["device_count"]:
            logger.info(f"Successfully disabled ECO mode on all devices in '{GROUP_NAME}' group")
        else:
            logger.warning(f"Disabled ECO mode on {success_count}/{result['device_count']} devices in '{GROUP_NAME}' group")
        
    finally:
        # Stop services
        logger.info("Stopping services")
        await parameter_service.stop()
    
    logger.info("Script completed")


if __name__ == "__main__":
    try:
        asyncio.run(disable_eco_mode())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.exception(f"Error during script execution: {e}") 