#!/usr/bin/env python
"""Integration tests for the Shelly Manager system."""

import unittest
import os
import shutil
import tempfile
from pathlib import Path

# Add the project directory to the Python path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.shelly_manager.grouping.models import DeviceGroup
from src.shelly_manager.grouping.group_manager import GroupManager


class TestGroupManagerIntegration(unittest.TestCase):
    """Integration tests for the GroupManager with other components."""

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for the group files
        self.temp_dir = tempfile.mkdtemp()
        self.group_manager = GroupManager(groups_dir=self.temp_dir)

        # Create some test device IDs
        self.device_ids = [
            "AABBCCDDEEFF",  # Living room light
            "112233445566",  # Kitchen light
            "AABBCCDDEE77",  # Bedroom outlet
            "112233445588"   # Outdoor light
        ]

        # Create test groups
        self.group_manager.create_group(
            name="indoor",
            description="Indoor devices",
            device_ids=[self.device_ids[0], self.device_ids[1], self.device_ids[2]],
            tags=["indoor"],
            config={"eco_mode": True}
        )
        
        self.group_manager.create_group(
            name="lighting",
            description="Lighting devices",
            device_ids=[self.device_ids[0], self.device_ids[1], self.device_ids[3]],
            tags=["lighting"],
            config={"schedule": "evening"}
        )

    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_file_persistence(self):
        """Test that groups are correctly persisted to files."""
        # Create a new instance of GroupManager pointing to the same directory
        # This simulates restarting the application
        new_manager = GroupManager(groups_dir=self.temp_dir)
        
        # Check that groups were loaded correctly
        groups = new_manager.list_groups()
        self.assertEqual(len(groups), 2)
        
        # Check group names
        group_names = [group.name for group in groups]
        self.assertIn("indoor", group_names)
        self.assertIn("lighting", group_names)
        
        # Check group contents for a specific group
        indoor_group = new_manager.get_group("indoor")
        self.assertEqual(indoor_group.description, "Indoor devices")
        self.assertEqual(len(indoor_group.device_ids), 3)
        self.assertEqual(indoor_group.tags, ["indoor"])
        self.assertEqual(indoor_group.config, {"eco_mode": True})
    
    def test_cross_group_operations(self):
        """Test operations across multiple groups."""
        # Add a device to both groups
        fifth_device = "ABCDEF123456"
        self.group_manager.add_device_to_group("indoor", fifth_device)
        self.group_manager.add_device_to_group("lighting", fifth_device)
        
        # Get groups for this device
        groups_with_device = self.group_manager.get_groups_for_device(fifth_device)
        self.assertEqual(len(groups_with_device), 2)
        
        # Remove device from one group
        self.group_manager.remove_device_from_group("indoor", fifth_device)
        
        # Check it's still in the other group
        groups_with_device = self.group_manager.get_groups_for_device(fifth_device)
        self.assertEqual(len(groups_with_device), 1)
        self.assertEqual(groups_with_device[0].name, "lighting")
    
    def test_group_rename_scenario(self):
        """Test a scenario where a group is renamed (delete and recreate)."""
        # Get the device IDs from the indoor group
        indoor_group = self.group_manager.get_group("indoor")
        device_ids = indoor_group.device_ids
        tags = indoor_group.tags
        config = indoor_group.config
        
        # Delete the indoor group
        self.group_manager.delete_group("indoor")
        
        # Create a new group with a different name but same devices
        self.group_manager.create_group(
            name="inside",
            description="Inside devices (renamed from indoor)",
            device_ids=device_ids,
            tags=tags,
            config=config
        )
        
        # Check group was renamed properly
        inside_group = self.group_manager.get_group("inside")
        self.assertIsNotNone(inside_group)
        self.assertEqual(inside_group.device_ids, device_ids)
        
        # Check the old file is gone and new file exists
        old_file = os.path.join(self.temp_dir, "indoor.yaml")
        new_file = os.path.join(self.temp_dir, "inside.yaml")
        self.assertFalse(os.path.exists(old_file))
        self.assertTrue(os.path.exists(new_file))
    
    def test_special_characters_in_group_name(self):
        """Test how groups with special characters in names are handled."""
        # Create a group with special characters
        special_name = "test/group:with?special*chars"
        self.group_manager.create_group(
            name=special_name,
            description="Group with special characters"
        )
        
        # Check file exists with sanitized name
        sanitized_file = os.path.join(self.temp_dir, "test_group_with_special_chars.yaml")
        self.assertTrue(os.path.exists(sanitized_file))
        
        # Reload manager and check group exists
        new_manager = GroupManager(groups_dir=self.temp_dir)
        group = new_manager.get_group(special_name)
        self.assertIsNotNone(group)
        self.assertEqual(group.name, special_name)
    
    def test_missing_groups_dir(self):
        """Test behavior when groups directory doesn't exist."""
        # Create a path that doesn't exist
        nonexistent_dir = os.path.join(self.temp_dir, "nonexistent")
        
        # Create manager with nonexistent directory
        manager = GroupManager(groups_dir=nonexistent_dir)
        
        # Directory should be created automatically
        self.assertTrue(os.path.exists(nonexistent_dir))
        
        # Should be able to create and retrieve groups
        manager.create_group("test", "Test group")
        group = manager.get_group("test")
        self.assertIsNotNone(group)
        
        # Group file should exist
        group_file = os.path.join(nonexistent_dir, "test.yaml")
        self.assertTrue(os.path.exists(group_file))


if __name__ == "__main__":
    unittest.main() 