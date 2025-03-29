#!/usr/bin/env python
"""Test cases for the grouping functionality."""

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


class TestGroupManager(unittest.TestCase):
    """Test the GroupManager class."""

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for the group files
        self.temp_dir = tempfile.mkdtemp()
        self.group_manager = GroupManager(groups_dir=self.temp_dir)

        # Create some test device IDs
        self.device_ids = [
            "AABBCCDDEEFF",  # Device 1
            "112233445566",  # Device 2
            "AABBCCDDEE77",  # Device 3
            "112233445588"   # Device 4
        ]

    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_create_group(self):
        """Test creating a group."""
        # Create a group
        group = self.group_manager.create_group(
            name="test_group",
            description="Test group",
            device_ids=[self.device_ids[0]],
            tags=["test", "group"],
            config={"test_key": "test_value"}
        )

        # Check that the group was created correctly
        self.assertEqual(group.name, "test_group")
        self.assertEqual(group.description, "Test group")
        self.assertEqual(group.device_ids, [self.device_ids[0]])
        self.assertEqual(group.tags, ["test", "group"])
        self.assertEqual(group.config, {"test_key": "test_value"})

        # Check that the group file was created
        group_file = os.path.join(self.temp_dir, "test_group.yaml")
        self.assertTrue(os.path.exists(group_file))

        # Check that the group is in the group manager
        self.assertIn("test_group", self.group_manager.groups)

    def test_create_group_with_special_chars(self):
        """Test creating a group with special characters in the name."""
        # Create a group with special characters in the name
        group = self.group_manager.create_group(
            name="test/group:with?special*chars",
            description="Test group with special characters"
        )

        # Check that the group was created correctly
        self.assertEqual(group.name, "test/group:with?special*chars")

        # Check that the group file was created with sanitized name
        group_file = os.path.join(self.temp_dir, "test_group_with_special_chars.yaml")
        self.assertTrue(os.path.exists(group_file))

    def test_update_group(self):
        """Test updating a group."""
        # Create a group
        group = self.group_manager.create_group(
            name="test_group",
            description="Test group"
        )

        # Update the group
        group.description = "Updated description"
        group.tags = ["updated", "tags"]
        group.config = {"updated_key": "updated_value"}

        # Save the updated group
        self.group_manager.update_group(group)

        # Reload the group manager to ensure changes were saved
        new_group_manager = GroupManager(groups_dir=self.temp_dir)
        updated_group = new_group_manager.get_group("test_group")

        # Check that the group was updated correctly
        self.assertEqual(updated_group.description, "Updated description")
        self.assertEqual(updated_group.tags, ["updated", "tags"])
        self.assertEqual(updated_group.config, {"updated_key": "updated_value"})

    def test_delete_group(self):
        """Test deleting a group."""
        # Create a group
        self.group_manager.create_group(
            name="test_group",
            description="Test group"
        )

        # Check that the group was created
        group_file = os.path.join(self.temp_dir, "test_group.yaml")
        self.assertTrue(os.path.exists(group_file))

        # Delete the group
        result = self.group_manager.delete_group("test_group")
        self.assertTrue(result)

        # Check that the group file was deleted
        self.assertFalse(os.path.exists(group_file))

        # Check that the group is no longer in the group manager
        self.assertNotIn("test_group", self.group_manager.groups)

    def test_add_device_to_group(self):
        """Test adding a device to a group."""
        # Create a group
        self.group_manager.create_group(
            name="test_group",
            description="Test group"
        )

        # Add a device to the group
        result = self.group_manager.add_device_to_group("test_group", self.device_ids[0])
        self.assertTrue(result)

        # Check that the device was added to the group
        group = self.group_manager.get_group("test_group")
        self.assertIn(self.device_ids[0], group.device_ids)

        # Reload the group manager to ensure changes were saved
        new_group_manager = GroupManager(groups_dir=self.temp_dir)
        group = new_group_manager.get_group("test_group")
        self.assertIn(self.device_ids[0], group.device_ids)

    def test_remove_device_from_group(self):
        """Test removing a device from a group."""
        # Create a group with a device
        self.group_manager.create_group(
            name="test_group",
            description="Test group",
            device_ids=[self.device_ids[0]]
        )

        # Remove the device from the group
        result = self.group_manager.remove_device_from_group("test_group", self.device_ids[0])
        self.assertTrue(result)

        # Check that the device was removed from the group
        group = self.group_manager.get_group("test_group")
        self.assertNotIn(self.device_ids[0], group.device_ids)

        # Reload the group manager to ensure changes were saved
        new_group_manager = GroupManager(groups_dir=self.temp_dir)
        group = new_group_manager.get_group("test_group")
        self.assertNotIn(self.device_ids[0], group.device_ids)

    def test_get_groups_for_device(self):
        """Test getting all groups that contain a specific device."""
        # Create two groups with different devices
        self.group_manager.create_group(
            name="group1",
            description="Group 1",
            device_ids=[self.device_ids[0], self.device_ids[1]]
        )
        self.group_manager.create_group(
            name="group2",
            description="Group 2",
            device_ids=[self.device_ids[1], self.device_ids[2]]
        )

        # Get groups for device 1
        groups = self.group_manager.get_groups_for_device(self.device_ids[0])
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].name, "group1")

        # Get groups for device 2
        groups = self.group_manager.get_groups_for_device(self.device_ids[1])
        self.assertEqual(len(groups), 2)
        group_names = [group.name for group in groups]
        self.assertIn("group1", group_names)
        self.assertIn("group2", group_names)

    def test_list_groups(self):
        """Test listing all groups."""
        # Create some groups
        self.group_manager.create_group(
            name="group1",
            description="Group 1"
        )
        self.group_manager.create_group(
            name="group2",
            description="Group 2"
        )

        # List all groups
        groups = self.group_manager.list_groups()
        self.assertEqual(len(groups), 2)
        group_names = [group.name for group in groups]
        self.assertIn("group1", group_names)
        self.assertIn("group2", group_names)

    def test_get_devices_in_group(self):
        """Test getting all devices in a group."""
        # Create a group with devices
        self.group_manager.create_group(
            name="test_group",
            description="Test group",
            device_ids=[self.device_ids[0], self.device_ids[1]]
        )

        # Get devices in the group
        devices = self.group_manager.get_devices_in_group("test_group")
        self.assertEqual(len(devices), 2)
        self.assertIn(self.device_ids[0], devices)
        self.assertIn(self.device_ids[1], devices)

    def test_get_all_devices(self):
        """Test getting all devices across all groups."""
        # Create groups with different devices
        self.group_manager.create_group(
            name="group1",
            description="Group 1",
            device_ids=[self.device_ids[0], self.device_ids[1]]
        )
        self.group_manager.create_group(
            name="group2",
            description="Group 2",
            device_ids=[self.device_ids[1], self.device_ids[2]]
        )

        # Get all devices
        devices = self.group_manager.get_all_devices()
        self.assertEqual(len(devices), 3)
        self.assertIn(self.device_ids[0], devices)
        self.assertIn(self.device_ids[1], devices)
        self.assertIn(self.device_ids[2], devices)

    def test_group_not_found(self):
        """Test behavior when a group is not found."""
        # Try to get a non-existent group
        group = self.group_manager.get_group("non_existent_group")
        self.assertIsNone(group)

        # Try to add a device to a non-existent group
        with self.assertRaises(KeyError):
            self.group_manager.add_device_to_group("non_existent_group", self.device_ids[0])

        # Try to remove a device from a non-existent group
        result = self.group_manager.remove_device_from_group("non_existent_group", self.device_ids[0])
        self.assertFalse(result)

        # Try to get devices in a non-existent group
        with self.assertRaises(KeyError):
            self.group_manager.get_devices_in_group("non_existent_group")

        # Try to delete a non-existent group
        result = self.group_manager.delete_group("non_existent_group")
        self.assertFalse(result)

    def test_duplicate_group_name(self):
        """Test behavior when creating a group with a duplicate name."""
        # Create a group
        self.group_manager.create_group(
            name="test_group",
            description="Test group"
        )

        # Try to create another group with the same name
        with self.assertRaises(ValueError):
            self.group_manager.create_group(
                name="test_group",
                description="Another test group"
            )


if __name__ == "__main__":
    unittest.main() 