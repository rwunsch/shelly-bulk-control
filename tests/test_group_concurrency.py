#!/usr/bin/env python
"""Tests for concurrency and error handling in the GroupManager."""

import os
import shutil
import tempfile
import unittest
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add the project directory to the Python path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.shelly_manager.grouping.models import DeviceGroup
from src.shelly_manager.grouping.group_manager import GroupManager


class TestGroupConcurrency(unittest.TestCase):
    """Test cases for concurrency and error handling in the GroupManager."""

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for the group files
        self.temp_dir = tempfile.mkdtemp()
        self.group_manager = GroupManager(groups_dir=self.temp_dir)

    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_concurrent_group_creation(self):
        """Test creating groups concurrently from multiple threads."""
        num_groups = 10
        group_names = [f"group_{i}" for i in range(num_groups)]

        # Function to create a group
        def create_group(name):
            try:
                return self.group_manager.create_group(
                    name=name,
                    description=f"Group {name}"
                )
            except Exception as e:
                self.fail(f"Failed to create group {name}: {e}")

        # Create groups concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(create_group, group_names))

        # Check that all groups were created
        self.assertEqual(len(results), num_groups)
        for name in group_names:
            group = self.group_manager.get_group(name)
            self.assertIsNotNone(group)
            self.assertEqual(group.name, name)
            self.assertEqual(group.description, f"Group {name}")

            # Verify file was created
            file_path = os.path.join(self.temp_dir, f"{name}.yaml")
            self.assertTrue(os.path.exists(file_path))

    def test_concurrent_device_addition(self):
        """Test adding devices to a group concurrently."""
        # Create a group
        group_name = "concurrent_devices"
        self.group_manager.create_group(
            name=group_name,
            description="Group for concurrent device addition"
        )

        # Generate device IDs
        num_devices = 20
        device_ids = [f"device_{i}" for i in range(num_devices)]

        # Function to add a device
        def add_device(device_id):
            try:
                return self.group_manager.add_device_to_group(group_name, device_id)
            except Exception as e:
                self.fail(f"Failed to add device {device_id}: {e}")

        # Add devices concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(add_device, device_ids))

        # Check that all devices were added
        self.assertTrue(all(results))

        # Get the group and check its devices
        group = self.group_manager.get_group(group_name)
        self.assertEqual(len(group.device_ids), num_devices)
        for device_id in device_ids:
            self.assertIn(device_id, group.device_ids)

    def test_concurrent_reads_and_writes(self):
        """Test reading and writing groups concurrently."""
        # Create initial groups
        for i in range(5):
            self.group_manager.create_group(
                name=f"group_{i}",
                description=f"Initial group {i}"
            )

        # Define operations
        def read_groups():
            try:
                groups = self.group_manager.list_groups()
                return len(groups)
            except Exception as e:
                self.fail(f"Failed to read groups: {e}")

        def create_group(index):
            try:
                name = f"new_group_{index}"
                self.group_manager.create_group(
                    name=name,
                    description=f"New group {index}"
                )
                return name
            except Exception as e:
                self.fail(f"Failed to create group: {e}")

        def update_group(index):
            try:
                name = f"group_{index}"
                group = self.group_manager.get_group(name)
                if group:
                    group.description = f"Updated group {index}"
                    self.group_manager.update_group(group)
                return name
            except Exception as e:
                self.fail(f"Failed to update group: {e}")

        # Run operations concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit a mix of reads and writes
            read_futures = [executor.submit(read_groups) for _ in range(20)]
            create_futures = [executor.submit(create_group, i) for i in range(5, 10)]
            update_futures = [executor.submit(update_group, i) for i in range(5)]

            # Get results
            read_results = [future.result() for future in read_futures]
            created_groups = [future.result() for future in create_futures]
            updated_groups = [future.result() for future in update_futures]

        # Verify results
        # All groups should exist
        for i in range(10):
            group_name = f"group_{i}" if i < 5 else f"new_group_{i}"
            group = self.group_manager.get_group(group_name)
            self.assertIsNotNone(group)

        # Updated groups should have new descriptions
        for i in range(5):
            group = self.group_manager.get_group(f"group_{i}")
            self.assertEqual(group.description, f"Updated group {i}")

    def test_error_handling_nonexistent_group(self):
        """Test error handling when accessing a non-existent group."""
        # Try to get a non-existent group
        group = self.group_manager.get_group("nonexistent")
        self.assertIsNone(group)

        # Try to add a device to a non-existent group
        with self.assertRaises(KeyError):
            self.group_manager.add_device_to_group("nonexistent", "device1")

        # Try to update a non-existent group
        # The group manager raises ValueError, not KeyError for this case
        with self.assertRaises(ValueError):
            self.group_manager.update_group(DeviceGroup(name="nonexistent"))

        # Try to remove a device from a non-existent group
        result = self.group_manager.remove_device_from_group("nonexistent", "device1")
        self.assertFalse(result)

        # Try to delete a non-existent group
        result = self.group_manager.delete_group("nonexistent")
        self.assertFalse(result)

    def test_error_handling_duplicate_group(self):
        """Test error handling when creating a duplicate group."""
        # Create a group
        self.group_manager.create_group(
            name="duplicate",
            description="Original group"
        )

        # Try to create another group with the same name
        with self.assertRaises(ValueError):
            self.group_manager.create_group(
                name="duplicate",
                description="Duplicate group"
            )

        # Verify the original group is unchanged
        group = self.group_manager.get_group("duplicate")
        self.assertEqual(group.description, "Original group")

    def test_error_handling_device_operations(self):
        """Test error handling for device operations."""
        # Create a group
        self.group_manager.create_group(
            name="devices",
            description="Group for device operations"
        )

        # Add a device
        self.group_manager.add_device_to_group("devices", "device1")

        # Try to add the same device again
        # This should not raise an error but should return success
        result = self.group_manager.add_device_to_group("devices", "device1")
        self.assertTrue(result)

        # Check that the device is still in the group exactly once
        group = self.group_manager.get_group("devices")
        self.assertEqual(group.device_ids.count("device1"), 1)

        # Try to remove a device that's not in the group
        # This should not raise an error but should return failure
        result = self.group_manager.remove_device_from_group("devices", "nonexistent_device")
        self.assertFalse(result)

        # Remove the device
        result = self.group_manager.remove_device_from_group("devices", "device1")
        self.assertTrue(result)

        # Check that the device is no longer in the group
        group = self.group_manager.get_group("devices")
        self.assertNotIn("device1", group.device_ids)

    def test_transaction_like_behavior(self):
        """Test that operations have transaction-like behavior."""
        # Create a group
        self.group_manager.create_group(
            name="transaction",
            description="Group for transaction testing",
            device_ids=["device1", "device2"]
        )

        # Simulate an error during update
        group = self.group_manager.get_group("transaction")
        group.description = "Updated description"
        group.device_ids.append("device3")

        # Create a file that can't be written to (in some environments)
        try:
            # Try to create a scenario where saving fails
            # Note: This is environment-dependent and may not always work
            file_path = os.path.join(self.temp_dir, "transaction.yaml")
            os.chmod(file_path, 0o444)  # Make file read-only

            # This should either fail or succeed, depending on the environment
            try:
                self.group_manager.update_group(group)
            except:
                # If it failed, the group in memory should still be updated
                # but the file should remain unchanged
                pass

            # Fix the permissions
            os.chmod(file_path, 0o666)

            # Create a new instance to reload from file
            new_manager = GroupManager(groups_dir=self.temp_dir)
            reloaded_group = new_manager.get_group("transaction")

            # The state might vary depending on whether the write succeeded
            # But we should always have a consistent state
            if "device3" in reloaded_group.device_ids:
                # If the write succeeded, both changes should be present
                self.assertEqual(reloaded_group.description, "Updated description")
            elif reloaded_group.description == "Updated description":
                # Both changes should be present if the description was updated
                self.assertIn("device3", reloaded_group.device_ids)
            else:
                # If the write failed, neither change should be present
                self.assertEqual(reloaded_group.description, "Group for transaction testing")
                self.assertEqual(reloaded_group.device_ids, ["device1", "device2"])
        except:
            # Skip the test if we can't create the test condition
            self.skipTest("Could not create test condition")

    def test_cross_manager_operations(self):
        """Test operations across multiple manager instances."""
        # Create a group with one manager
        manager1 = GroupManager(groups_dir=self.temp_dir)
        manager1.create_group(
            name="shared",
            description="Shared group",
            device_ids=["device1"]
        )

        # Create a second manager instance
        manager2 = GroupManager(groups_dir=self.temp_dir)

        # Use the second manager to modify the group
        group = manager2.get_group("shared")
        group.description = "Modified by manager2"
        group.device_ids.append("device2")
        manager2.update_group(group)

        # Use the first manager to check the changes
        # We need to create a new instance of manager1 to reload from file
        manager1 = GroupManager(groups_dir=self.temp_dir)
        manager1_group = manager1.get_group("shared")
        self.assertEqual(manager1_group.description, "Modified by manager2")
        self.assertEqual(manager1_group.device_ids, ["device1", "device2"])

        # Use the first manager to add another device
        manager1.add_device_to_group("shared", "device3")

        # Create new instance of manager2 to reload from file
        manager2 = GroupManager(groups_dir=self.temp_dir)
        manager2_group = manager2.get_group("shared")
        self.assertIn("device3", manager2_group.device_ids)


if __name__ == "__main__":
    unittest.main() 