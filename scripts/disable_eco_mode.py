#!/usr/bin/env python3
"""Script to disable ECO mode on devices in the eco_enabled_small group."""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.discovery.discovery_service import DiscoveryService
from shelly_manager.parameter.parameter_service import ParameterService
from shelly_manager.utils.logging import LogConfig

# Configure logging
log_config = LogConfig(
    app_name="disable_eco_mode",
    debug=True,
    log_to_file=True,
    log_to_console=True
)
log_config.setup()
logger = logging.getLogger("disable_eco_mode")

# Group to modify
GROUP_NAME = "eco_enabled"
PARAMETER_NAME = "eco_mode"
PARAMETER_VALUE = False


async def disable_eco_mode():
    """Disable ECO mode on devices in the eco_enabled_small group."""
    logger.info(f"Starting script to disable ECO mode on devices in '{GROUP_NAME}' group")
    
    # Initialize services
    discovery_service = DiscoveryService()
    group_manager = GroupManager()
    parameter_service = ParameterService(group_manager, discovery_service)
    
    # Start services
    logger.info("Starting services")
    await discovery_service.start()
    await parameter_service.start()
    
    try:
        # Verify group exists
        group = group_manager.get_group(GROUP_NAME)
        if not group:
            logger.error(f"Group '{GROUP_NAME}' not found")
            return
            
        # Discover devices
        logger.info("Discovering devices")
        await discovery_service.discover_devices()
        
        # Apply parameter change
        logger.info(f"Applying parameter '{PARAMETER_NAME}={PARAMETER_VALUE}' to group '{GROUP_NAME}'")
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
        logger.info(f"Success rate: {success_count}/{result['device_count']} ({success_count/result['device_count']*100:.0f}%)")
        
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
        await discovery_service.stop()
    
    logger.info("Script completed")


if __name__ == "__main__":
    try:
        asyncio.run(disable_eco_mode())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.exception(f"Error during script execution: {e}") 