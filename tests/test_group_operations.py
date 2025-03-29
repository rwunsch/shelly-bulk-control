#!/usr/bin/env python3
"""Test script for group operations functionality."""

import asyncio
import sys
import logging
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.grouping.command_service import GroupCommandService
from shelly_manager.discovery.discovery_service import DiscoveryService
from shelly_manager.utils.logging import LogConfig

# Configure logging
log_config = LogConfig(
    app_name="test_group_operations",
    debug=True,
    log_to_file=True,
    log_to_console=True
)
log_config.setup()
logger = logging.getLogger("test_group_operations")


async def test_group_operations():
    """Test group operations functionality."""
    logger.info("Starting group operations test")
    
    # Initialize the group manager
    group_manager = GroupManager()
    
    # List available groups
    groups = group_manager.list_groups()
    logger.info(f"Available groups: {', '.join(g.name for g in groups) if groups else 'None'}")
    
    if not groups:
        logger.warning("No groups found. Please create a group first.")
        return
    
    # Create a discovery service
    discovery_service = DiscoveryService()
    
    # Start the discovery service
    logger.info("Starting discovery service")
    await discovery_service.start()
    
    try:
        # Discover devices
        logger.info("Discovering devices")
        await discovery_service.discover_devices()
        
        devices = discovery_service.get_devices()
        logger.info(f"Discovered {len(devices)} devices")
        
        # Create a group command service
        logger.info("Creating group command service")
        command_service = GroupCommandService(group_manager, discovery_service)
        
        # Start the command service
        await command_service.start()
        
        # Test operations on the first group
        group = groups[0]
        logger.info(f"Testing operations on group: {group.name}")
        
        # Get status
        logger.info("Getting group status")
        status_result = await command_service.get_group_status(group.name)
        logger.info(f"Status result: {status_result}")
        
        # Toggle devices
        logger.info("Toggling devices in group")
        toggle_result = await command_service.toggle_group(group.name)
        logger.info(f"Toggle result: {toggle_result}")
        
        # Turn off devices
        logger.info("Turning off devices in group")
        off_result = await command_service.turn_off_group(group.name)
        logger.info(f"Turn off result: {off_result}")
        
        # Turn on devices
        logger.info("Turning on devices in group")
        on_result = await command_service.turn_on_group(group.name)
        logger.info(f"Turn on result: {on_result}")
        
        # Stop the command service
        await command_service.stop()
        
    finally:
        # Stop the discovery service
        await discovery_service.stop()
    
    logger.info("Group operations test completed")


if __name__ == "__main__":
    try:
        asyncio.run(test_group_operations())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.exception(f"Error during test: {e}") 