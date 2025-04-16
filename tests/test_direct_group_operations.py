#!/usr/bin/env python3
"""Test script for direct group operations without network scanning."""

import asyncio
import sys
import logging
import argparse
import pytest
from pathlib import Path
from typing import List, Dict, Any

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.grouping.command_service import GroupCommandService
from shelly_manager.models.device import Device, DeviceGeneration
from shelly_manager.models.device_registry import device_registry
from shelly_manager.utils.logging import LogConfig

# Configure logging
log_config = LogConfig(
    app_name="test_direct_group_operations",
    debug=True,
    log_to_file=True,
    log_to_console=True
)
log_config.setup()
logger = logging.getLogger("test_direct_group_operations")


@pytest.fixture
def test_group_name():
    """Fixture to provide a test group name."""
    return "test_group"


@pytest.mark.asyncio
async def test_direct_group_operations(test_group_name):
    """
    Test group operations functionality by directly accessing devices.
    
    Args:
        test_group_name: Name of the group to test from fixture
    """
    # Use default values for optional parameters
    ip_address = None
    operation_delay = 2
    
    logger.info("Starting direct group operations test")
    
    # Initialize the group manager
    group_manager = GroupManager()
    
    # List available groups
    groups = group_manager.list_groups()
    logger.info(f"Available groups: {', '.join(g.name for g in groups) if groups else 'None'}")
    
    if not groups:
        logger.warning("No groups found. Please create a group first.")
        pytest.skip("No groups found for testing")
        return
    
    # Select the target group
    target_group = None
    for group in groups:
        if group.name == test_group_name:
            target_group = group
            break
    
    if not target_group:
        logger.warning(f"Group '{test_group_name}' not found.")
        pytest.skip(f"Test group '{test_group_name}' not found")
        return
    
    logger.info(f"Testing with group: {target_group.name}")
    logger.info(f"Device IDs in group: {target_group.device_ids}")
    
    # Get devices from registry or create a device with the provided IP
    devices = []
    
    if ip_address:
        # Create a device with the provided IP, use the first device ID from the group
        if not target_group.device_ids:
            logger.warning(f"Group '{target_group.name}' has no device IDs")
            pytest.skip(f"Group '{target_group.name}' has no device IDs")
            return
            
        device_id = target_group.device_ids[0]
        logger.info(f"Creating device with ID {device_id} and IP {ip_address}")
        device = Device(
            id=device_id,
            name=f"Test Device ({device_id})",
            model="TestModel",
            generation=DeviceGeneration.GEN2,  # Assumes Gen2, modify as needed
            ip_address=ip_address,
            mac_address=device_id
        )
        devices.append(device)
    else:
        # Try to load devices from registry
        logger.info(f"Attempting to load {len(target_group.device_ids)} devices from registry")
        devices = device_registry.get_devices(target_group.device_ids)
        
        # If we have missing devices, log them
        if len(devices) < len(target_group.device_ids):
            found_ids = {device.id for device in devices}
            missing_ids = [device_id for device_id in target_group.device_ids if device_id not in found_ids]
            logger.warning(f"Missing devices in registry: {missing_ids}")
    
    if not devices:
        logger.warning("No devices found for testing")
        pytest.skip("No devices found for testing")
        return
    
    logger.info(f"Found {len(devices)} devices to test with")
    
    # Create a command service
    logger.info("Creating command service")
    command_service = GroupCommandService(group_manager)
    
    # Start the command service
    await command_service.start()
    
    try:
        # Get status
        logger.info("Getting group status")
        try:
            status_result = await asyncio.wait_for(
                command_service.get_group_status(target_group.name),
                timeout=10.0
            )
            logger.info(f"Status result: {status_result}")
        except asyncio.TimeoutError:
            logger.warning("Status operation timed out")
        except Exception as e:
            logger.error(f"Error getting status: {e}")
        
        # Wait between operations
        await asyncio.sleep(operation_delay)
        
        # Toggle devices
        logger.info("Toggling devices in group")
        try:
            toggle_result = await asyncio.wait_for(
                command_service.toggle_group(target_group.name),
                timeout=10.0
            )
            logger.info(f"Toggle result: {toggle_result}")
        except asyncio.TimeoutError:
            logger.warning("Toggle operation timed out")
        except Exception as e:
            logger.error(f"Error toggling devices: {e}")
        
        # Wait between operations
        await asyncio.sleep(operation_delay)
        
        # Turn off devices
        logger.info("Turning off devices in group")
        try:
            off_result = await asyncio.wait_for(
                command_service.turn_off_group(target_group.name),
                timeout=10.0
            )
            logger.info(f"Turn off result: {off_result}")
        except asyncio.TimeoutError:
            logger.warning("Turn off operation timed out")
        except Exception as e:
            logger.error(f"Error turning off devices: {e}")
        
        # Wait between operations
        await asyncio.sleep(operation_delay)
        
        # Turn on devices
        logger.info("Turning on devices in group")
        try:
            on_result = await asyncio.wait_for(
                command_service.turn_on_group(target_group.name),
                timeout=10.0
            )
            logger.info(f"Turn on result: {on_result}")
        except asyncio.TimeoutError:
            logger.warning("Turn on operation timed out")
        except Exception as e:
            logger.error(f"Error turning on devices: {e}")
        
    finally:
        # Stop the command service
        await command_service.stop()
    
    logger.info("Group operations test completed")


# The following functions are for command-line usage, not for pytest
def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Test direct group operations functionality")
    parser.add_argument("--group", "-g", required=True, help="Name of the group to test")
    parser.add_argument("--ip", "-i", help="IP address of a device to use directly (optional)")
    parser.add_argument("--delay", "-d", type=int, default=2, help="Delay in seconds between operations")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(test_direct_group_operations(args.group))
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.exception(f"Error during test: {e}") 