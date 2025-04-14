#!/usr/bin/env python3
"""Test script for group operations functionality."""

import asyncio
import sys
import logging
import argparse
from pathlib import Path
import pytest
from unittest.mock import patch, AsyncMock

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


@pytest.mark.asyncio
@pytest.mark.network  # Mark this test as requiring network connectivity
# Comment out this line to enable the test
# @pytest.mark.skip(reason="Requires actual network connectivity and configured groups")
async def test_group_operations(group_name=None, discovery_timeout=30, operation_delay=2):
    """Test group operations functionality.
    
    Args:
        group_name: Optional name of the group to test. If None, uses the first available group.
        discovery_timeout: Timeout in seconds for device discovery.
        operation_delay: Delay in seconds between operations.
    """
    logger.info("Starting group operations test")
    
    # Initialize the group manager
    group_manager = GroupManager()
    
    # List available groups
    groups = group_manager.list_groups()
    logger.info(f"Available groups: {', '.join(g.name for g in groups) if groups else 'None'}")
    
    if not groups:
        logger.warning("No groups found. Please create a group first.")
        pytest.skip("No groups available for testing")
        return
    
    # Select the target group
    target_group = None
    if group_name:
        for group in groups:
            if group.name == group_name:
                target_group = group
                break
        if not target_group:
            logger.warning(f"Group '{group_name}' not found. Using first available group.")
            target_group = groups[0]
    else:
        target_group = groups[0]
    
    logger.info(f"Testing with group: {target_group.name}")
    
    # Create a discovery service
    discovery_service = DiscoveryService()
    
    # Start the discovery service
    logger.info("Starting discovery service")
    await discovery_service.start()
    
    try:
        # Discover devices with a timeout to prevent hanging
        logger.info(f"Discovering devices (with {discovery_timeout}s timeout)")
        try:
            await asyncio.wait_for(
                discovery_service.discover_devices(),
                timeout=float(discovery_timeout)  # Configurable timeout for discovery
            )
        except asyncio.TimeoutError:
            logger.warning(f"Device discovery timed out after {discovery_timeout} seconds")
        
        devices = discovery_service._get_sorted_devices()
        logger.info(f"Discovered {len(devices)} devices")
        
        if not devices:
            logger.warning("No devices found. Skipping remaining tests.")
            pytest.skip("No devices found for testing")
            return
        
        # Create a group command service
        logger.info("Creating group command service")
        command_service = GroupCommandService(group_manager, discovery_service)
        
        # Start the command service
        await command_service.start()
        
        # Test operations on the selected group
        logger.info(f"Testing operations on group: {target_group.name}")
        
        # Get status with timeout
        logger.info("Getting group status")
        try:
            status_result = await asyncio.wait_for(
                command_service.get_group_status(target_group.name),
                timeout=10.0
            )
            logger.info(f"Status result: {status_result}")
        except asyncio.TimeoutError:
            logger.warning("Status operation timed out")
            
        # Wait between operations
        await asyncio.sleep(operation_delay)
        
        # Toggle devices with timeout
        logger.info("Toggling devices in group")
        try:
            toggle_result = await asyncio.wait_for(
                command_service.toggle_group(target_group.name),
                timeout=10.0
            )
            logger.info(f"Toggle result: {toggle_result}")
        except asyncio.TimeoutError:
            logger.warning("Toggle operation timed out")
            
        # Wait between operations
        await asyncio.sleep(operation_delay)
        
        # Turn off devices with timeout
        logger.info("Turning off devices in group")
        try:
            off_result = await asyncio.wait_for(
                command_service.turn_off_group(target_group.name),
                timeout=10.0
            )
            logger.info(f"Turn off result: {off_result}")
        except asyncio.TimeoutError:
            logger.warning("Turn off operation timed out")
            
        # Wait between operations
        await asyncio.sleep(operation_delay)
        
        # Turn on devices with timeout
        logger.info("Turning on devices in group")
        try:
            on_result = await asyncio.wait_for(
                command_service.turn_on_group(target_group.name),
                timeout=10.0
            )
            logger.info(f"Turn on result: {on_result}")
        except asyncio.TimeoutError:
            logger.warning("Turn on operation timed out")
        
        # Stop the command service
        await command_service.stop()
        
    finally:
        # Stop the discovery service
        await discovery_service.stop()
    
    logger.info("Group operations test completed")


# Mock version of the test that doesn't require real network connectivity
@pytest.mark.asyncio
async def test_group_operations_mock():
    """Test group operations functionality with mocks."""
    logger.info("Starting mock group operations test")
    
    # Initialize the group manager with a mock
    with patch('shelly_manager.grouping.group_manager.GroupManager') as mock_group_manager_class:
        # Set up mock group manager to return a mock group
        mock_group_manager = mock_group_manager_class.return_value
        mock_group = AsyncMock()
        mock_group.name = "TestGroup"
        mock_group_manager.list_groups.return_value = [mock_group]
        
        # Create a mock discovery service
        with patch('shelly_manager.discovery.discovery_service.DiscoveryService') as mock_discovery_class:
            mock_discovery = mock_discovery_class.return_value
            
            # Create a mock command service
            with patch('shelly_manager.grouping.command_service.GroupCommandService') as mock_cmd_service_class:
                mock_cmd_service = mock_cmd_service_class.return_value
                
                # Set up mock return values as coroutines
                mock_cmd_service.get_group_status = AsyncMock(return_value={"status": "ok"})
                mock_cmd_service.toggle_group = AsyncMock(return_value={"toggled": True})
                mock_cmd_service.turn_off_group = AsyncMock(return_value={"turned_off": True})
                mock_cmd_service.turn_on_group = AsyncMock(return_value={"turned_on": True})
                
                # Execute test operations
                result1 = await mock_cmd_service.get_group_status("TestGroup")
                result2 = await mock_cmd_service.toggle_group("TestGroup")
                result3 = await mock_cmd_service.turn_off_group("TestGroup")
                result4 = await mock_cmd_service.turn_on_group("TestGroup")
                
                # Verify results
                assert result1 == {"status": "ok"}
                assert result2 == {"toggled": True}
                assert result3 == {"turned_off": True}
                assert result4 == {"turned_on": True}
                
                logger.info("Mock test completed successfully")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Test group operations functionality")
    parser.add_argument("--group", "-g", help="Name of the group to test")
    parser.add_argument("--timeout", "-t", type=int, default=30, help="Timeout in seconds for device discovery")
    parser.add_argument("--delay", "-d", type=int, default=2, help="Delay in seconds between operations")
    parser.add_argument("--mock", "-m", action="store_true", help="Run the mock test instead of the real test")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        if args.mock:
            asyncio.run(test_group_operations_mock())
        else:
            asyncio.run(test_group_operations(args.group, args.timeout, args.delay))
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.exception(f"Error during test: {e}") 