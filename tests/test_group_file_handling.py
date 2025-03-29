#!/usr/bin/env python
"""Tests for file handling in the GroupManager."""

import os
import yaml
import shutil
import tempfile
import unittest
from pathlib import Path

# Add the project directory to the Python path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.shelly_manager.grouping.models import DeviceGroup
from src.shelly_manager.grouping.group_manager import GroupManager


class TestGroupFileHandling(unittest.TestCase):
    """Test cases for file handling in the GroupManager."""

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for the group files
        self.temp_dir = tempfile.mkdtemp()
        self.group_manager = GroupManager(groups_dir=self.temp_dir)

    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_file_naming_with_special_characters(self):
        """Test that group names with special characters are correctly sanitized for filenames."""
        special_characters = [
            ("test/group", "test_group"),
            ("test:group", "test_group"),
            ("test?group", "test_group"),
            ("test*group", "test_group"),
            ("test group", "test_group"),
            ("test.group", "test.group"),  # Periods should be allowed
            ("test_group", "test_group"),  # Underscores should be allowed
            ("test-group", "test-group"),  # Hyphens should be allowed
            ("TeSt_GrOuP", "TeSt_GrOuP"),  # Case should be preserved
        ]

        for group_name, expected_filename in special_characters:
            # Create a group with special characters
            self.group_manager.create_group(
                name=group_name,
                description=f"Group {group_name}"
            )

            # Check that the file was created with the sanitized name
            filename = f"{expected_filename}.yaml"
            file_path = os.path.join(self.temp_dir, filename)
            self.assertTrue(os.path.exists(file_path), f"File {file_path} should exist for group {group_name}")

            # Delete the group for the next test
            self.group_manager.delete_group(group_name)

    def test_file_content_structure(self):
        """Test that the file content has the expected structure."""
        # Create a group with all fields
        group = self.group_manager.create_group(
            name="test_file_structure",
            description="Test group",
            device_ids=["AABBCCDDEEFF"],
            tags=["test", "structure"],
            config={"key1": "value1", "key2": 123}
        )

        # Get the file path
        file_path = os.path.join(self.temp_dir, "test_file_structure.yaml")

        # Read the file
        with open(file_path, 'r') as f:
            content = yaml.safe_load(f)

        # Check the structure
        self.assertEqual(content["name"], "test_file_structure")
        self.assertEqual(content["description"], "Test group")
        self.assertEqual(content["device_ids"], ["AABBCCDDEEFF"])
        self.assertEqual(content["tags"], ["test", "structure"])
        self.assertEqual(content["config"], {"key1": "value1", "key2": 123})

    def test_reload_from_files(self):
        """Test that groups can be correctly reloaded from files."""
        # Create some groups
        self.group_manager.create_group(
            name="group1",
            description="Group 1",
            device_ids=["device1", "device2"],
            tags=["tag1", "tag2"],
            config={"key1": "value1"}
        )
        self.group_manager.create_group(
            name="group2",
            description="Group 2",
            device_ids=["device3"],
            tags=["tag3"],
            config={"key2": "value2"}
        )

        # Create a new instance of GroupManager to reload from files
        new_manager = GroupManager(groups_dir=self.temp_dir)

        # Check that the groups were correctly loaded
        self.assertEqual(len(new_manager.groups), 2)
        self.assertIn("group1", new_manager.groups)
        self.assertIn("group2", new_manager.groups)

        # Check group1 details
        group1 = new_manager.get_group("group1")
        self.assertEqual(group1.name, "group1")
        self.assertEqual(group1.description, "Group 1")
        self.assertEqual(group1.device_ids, ["device1", "device2"])
        self.assertEqual(group1.tags, ["tag1", "tag2"])
        self.assertEqual(group1.config, {"key1": "value1"})

        # Check group2 details
        group2 = new_manager.get_group("group2")
        self.assertEqual(group2.name, "group2")
        self.assertEqual(group2.description, "Group 2")
        self.assertEqual(group2.device_ids, ["device3"])
        self.assertEqual(group2.tags, ["tag3"])
        self.assertEqual(group2.config, {"key2": "value2"})

    def test_malformed_yaml_handling(self):
        """Test that malformed YAML files are handled gracefully."""
        # Create a valid group
        self.group_manager.create_group(
            name="valid_group",
            description="Valid group"
        )

        # Create a malformed file
        malformed_file = os.path.join(self.temp_dir, "malformed_group.yaml")
        with open(malformed_file, 'w') as f:
            f.write("name: malformed_group\ndescription: Malformed group\ntags: [")  # Missing closing bracket

        # Create another valid file
        self.group_manager.create_group(
            name="valid_group2",
            description="Valid group 2"
        )

        # Create a new instance of GroupManager to reload from files
        new_manager = GroupManager(groups_dir=self.temp_dir)

        # Check that valid groups were loaded
        self.assertIn("valid_group", new_manager.groups)
        self.assertIn("valid_group2", new_manager.groups)
        self.assertNotIn("malformed_group", new_manager.groups)

    def test_empty_directory_handling(self):
        """Test that an empty directory is handled correctly."""
        # Delete any existing files
        for file in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, file))

        # Create a new instance of GroupManager with the empty directory
        empty_manager = GroupManager(groups_dir=self.temp_dir)

        # Check that the groups dictionary is empty
        self.assertEqual(len(empty_manager.groups), 0)

    def test_unicode_handling(self):
        """Test that group names with Unicode characters are handled correctly."""
        # Create groups with Unicode characters
        unicode_names = [
            "ünicode_group",
            "unicode_gröup",
            "unicode_group_ä",
            "中文_group",
            "русский_group",
            "😀_group"
        ]

        for name in unicode_names:
            # Create a group with Unicode characters
            self.group_manager.create_group(
                name=name,
                description=f"Group with Unicode characters: {name}"
            )

            # Check that the group exists in the manager
            self.assertIn(name, self.group_manager.groups)

        # Create a new instance of GroupManager to reload from files
        new_manager = GroupManager(groups_dir=self.temp_dir)

        # Check that all groups were correctly loaded
        for name in unicode_names:
            self.assertIn(name, new_manager.groups)
            group = new_manager.get_group(name)
            self.assertEqual(group.name, name)
            self.assertEqual(group.description, f"Group with Unicode characters: {name}")

    def test_file_permissions(self):
        """Test file permissions for group files."""
        # Create a group
        self.group_manager.create_group(
            name="permissions_test",
            description="Testing file permissions"
        )

        # Get the file path
        file_path = os.path.join(self.temp_dir, "permissions_test.yaml")

        # Check that the file exists
        self.assertTrue(os.path.exists(file_path))

        # Check that the file is readable and writable
        self.assertTrue(os.access(file_path, os.R_OK))
        self.assertTrue(os.access(file_path, os.W_OK))

        # Test updating a group
        self.group_manager.update_group(
            DeviceGroup(
                name="permissions_test",
                description="Updated description",
                device_ids=["device1"],
                tags=["tag1"],
                config={"key": "value"}
            )
        )

        # Check that the file still exists and is readable and writable
        self.assertTrue(os.path.exists(file_path))
        self.assertTrue(os.access(file_path, os.R_OK))
        self.assertTrue(os.access(file_path, os.W_OK))


if __name__ == "__main__":
    unittest.main() 