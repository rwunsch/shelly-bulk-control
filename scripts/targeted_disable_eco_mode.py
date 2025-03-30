#!/usr/bin/env python3
"""
Script to test the parameter group CLI commands by disabling ECO mode
on devices in the eco_enabled_small group using the device registry.
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.parameter.parameter_service import ParameterService
from shelly_manager.models.device_registry import device_registry
from shelly_manager.utils.logging import LogConfig

# Configure logging
log_config = LogConfig(
    app_name="test_parameter_group_cli",
    debug=True,
    log_to_file=True,
    log_to_console=True
)
log_config.setup()
logger = logging.getLogger("test_parameter_group_cli")

# Group to modify
GROUP_NAME = "eco_enabled_small"
PARAMETER_NAME = "eco_mode"
PARAMETER_VALUE = False


async def test_parameter_group_commands():
    """
    Test the parameter group CLI commands by:
    1. Getting the current eco_mode status for all devices in the group
    2. Setting eco_mode to False for all devices in the group
    3. Verifying the changes took effect
    """
    logger.info(f"Testing parameter group CLI commands on '{GROUP_NAME}' group")
    
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
        
        logger.info(f"Group '{GROUP_NAME}' contains {len(group.device_ids)} devices")
        
        # Make sure devices directory exists
        device_dir = os.path.join("data", "devices")
        if not os.path.exists(device_dir):
            os.makedirs(device_dir, exist_ok=True)
            logger.info(f"Created device storage directory: {device_dir}")
        
        # Load devices from registry
        logger.info(f"Loading devices for group '{GROUP_NAME}' from registry")
        devices = await parameter_service.load_devices_for_group(GROUP_NAME)
        
        if not devices:
            logger.error(f"No devices found in group '{GROUP_NAME}'")
            return
            
        logger.info(f"Loaded {len(devices)} devices from registry")
        
        # Debug: Print device details
        for device in devices:
            logger.info(f"Device details: ID={device.id}, Model={device.model}, Gen={device.generation}, IP={device.ip_address}")
        
        # STEP 1: Get current eco_mode status for all devices in the group
        logger.info(f"Getting current '{PARAMETER_NAME}' status for all devices in '{GROUP_NAME}'")
        get_result = await parameter_service.get_parameter_for_group(GROUP_NAME, PARAMETER_NAME)
        
        if "error" in get_result:
            logger.error(f"Error getting parameter: {get_result['error']}")
            return
        
        logger.info(f"Current status: {get_result['success_count']}/{get_result['device_count']} devices responded")
        
        # Print current values
        for device_id, result in get_result.get("results", {}).items():
            if "error" in result:
                logger.warning(f"Device {device_id}: Error - {result['error']}")
            else:
                value = result.get("value")
                logger.info(f"Device {device_id}: {PARAMETER_NAME} = {value}")
        
        # STEP 2: Set eco_mode to False for all devices in the group
        logger.info(f"Setting '{PARAMETER_NAME}={PARAMETER_VALUE}' for all devices in '{GROUP_NAME}'")
        set_result = await parameter_service.set_parameter_for_group(GROUP_NAME, PARAMETER_NAME, PARAMETER_VALUE)
        
        if "error" in set_result:
            logger.error(f"Error setting parameter: {set_result['error']}")
            return
        
        logger.info(f"Set status: {set_result['success_count']}/{set_result['device_count']} devices updated")
        
        # STEP 3: Verify the changes took effect
        logger.info(f"Verifying '{PARAMETER_NAME}' was set to '{PARAMETER_VALUE}' for all devices")
        verify_result = await parameter_service.get_parameter_for_group(GROUP_NAME, PARAMETER_NAME)
        
        if "error" in verify_result:
            logger.error(f"Error verifying parameter: {verify_result['error']}")
            return
        
        # Check if all devices have the expected value
        success_count = 0
        for device_id, result in verify_result.get("results", {}).items():
            if "error" in result:
                logger.warning(f"Device {device_id}: Error - {result['error']}")
            else:
                value = result.get("value")
                if value == PARAMETER_VALUE:
                    success_count += 1
                    logger.info(f"Device {device_id}: {PARAMETER_NAME} = {value} ✓")
                else:
                    logger.warning(f"Device {device_id}: {PARAMETER_NAME} = {value} ✗ (Expected {PARAMETER_VALUE})")
        
        # Calculate success rate
        if verify_result["device_count"] > 0:
            success_rate = success_count / verify_result["device_count"] * 100
            logger.info(f"Verification success rate: {success_count}/{verify_result['device_count']} ({success_rate:.0f}%)")
        
        # STEP 4: Test parameter profile application
        logger.info("Testing parameter profile application")
        profile = {
            "eco_mode": False,
            "name": f"Eco-Disabled Device"
        }
        
        profile_result = await parameter_service.apply_parameter_profile(GROUP_NAME, profile)
        
        if "error" in profile_result:
            logger.error(f"Error applying profile: {profile_result['error']}")
            return
        
        logger.info(f"Profile application: {profile_result['success_count']}/{profile_result['total_operations']} operations succeeded")
        
        # Summary
        if success_count == verify_result["device_count"]:
            logger.info(f"✓ Successfully set {PARAMETER_NAME}={PARAMETER_VALUE} on all devices in '{GROUP_NAME}' group")
        else:
            logger.warning(f"⚠ Set {PARAMETER_NAME}={PARAMETER_VALUE} on {success_count}/{verify_result['device_count']} devices in '{GROUP_NAME}' group")
        
    finally:
        # Stop services
        logger.info("Stopping services")
        await parameter_service.stop()
    
    logger.info("Test completed")


if __name__ == "__main__":
    try:
        asyncio.run(test_parameter_group_commands())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.exception(f"Error during script execution: {e}") 