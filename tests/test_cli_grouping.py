#!/usr/bin/env python
"""Pytest-based CLI tests for the grouping functionality."""

import os
import shutil
import tempfile
import subprocess
import pytest
from pathlib import Path

# Add the project directory to the Python path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.shelly_manager.grouping.group_manager import GroupManager


@pytest.fixture
def test_groups_dir():
    """Create a temporary directory for test groups."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


def run_cli_command(command, env=None):
    """Run a CLI command and return its output."""
    if env is None:
        env = os.environ.copy()
    
    # Run the command and capture output
    result = subprocess.run(
        command,
        shell=True,
        check=False,
        capture_output=True,
        text=True,
        env=env
    )
    
    return result


def test_empty_group_listing(test_groups_dir):
    """Test listing groups when none exist."""
    env = os.environ.copy()
    env["SHELLY_GROUPS_DIR"] = test_groups_dir
    
    # Run the command to list groups
    result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups list",
        env=env
    )
    
    # Check the output contains the expected message
    assert "No groups found" in result.stdout
    assert f"Groups directory: {os.path.abspath(test_groups_dir)}" in result.stdout
    assert result.returncode == 0


def test_group_creation_and_listing(test_groups_dir):
    """Test creating a group and then listing it."""
    env = os.environ.copy()
    env["SHELLY_GROUPS_DIR"] = test_groups_dir
    
    # Create a group
    create_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups create test_group --description 'Test group' --tags 'test,pytest'",
        env=env
    )
    
    # Check the group was created successfully
    assert "Created group 'test_group'" in create_result.stdout
    assert create_result.returncode == 0
    
    # Verify the file was created
    group_file = os.path.join(test_groups_dir, "test_group.yaml")
    assert os.path.exists(group_file)
    
    # List groups
    list_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups list",
        env=env
    )
    
    # Check the output contains the group
    assert "test_group" in list_result.stdout
    assert "Test group" in list_result.stdout
    assert "test, pytest" in list_result.stdout
    assert list_result.returncode == 0


def test_group_details(test_groups_dir):
    """Test showing group details."""
    env = os.environ.copy()
    env["SHELLY_GROUPS_DIR"] = test_groups_dir
    
    # Create a group
    run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups create test_group --description 'Test group details' --tags 'test,details'",
        env=env
    )
    
    # Show group details
    show_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups show test_group",
        env=env
    )
    
    # Check the output contains the expected details
    assert "Name" in show_result.stdout
    assert "test_group" in show_result.stdout
    assert "Test group details" in show_result.stdout
    assert "test, details" in show_result.stdout
    assert show_result.returncode == 0


def test_adding_devices(test_groups_dir):
    """Test adding devices to a group."""
    env = os.environ.copy()
    env["SHELLY_GROUPS_DIR"] = test_groups_dir
    
    # Create a group
    run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups create test_group",
        env=env
    )
    
    # Add a device to the group
    add_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups add-device test_group AABBCCDDEEFF",
        env=env
    )
    
    # Check the device was added
    assert "Added device 'AABBCCDDEEFF' to group 'test_group'" in add_result.stdout
    assert add_result.returncode == 0
    
    # Show group details to verify the device was added
    show_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups show test_group",
        env=env
    )
    
    # Check the output contains the device
    assert "AABBCCDDEEFF" in show_result.stdout
    assert "Device Count" in show_result.stdout
    assert "1" in show_result.stdout
    assert show_result.returncode == 0


def test_updating_group(test_groups_dir):
    """Test updating a group."""
    env = os.environ.copy()
    env["SHELLY_GROUPS_DIR"] = test_groups_dir
    
    # Create a group
    run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups create test_group --description 'Original description' --tags 'original'",
        env=env
    )
    
    # Update the group
    update_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups update test_group --description 'Updated description' --tags 'updated'",
        env=env
    )
    
    # Check the group was updated
    assert "Updated group 'test_group'" in update_result.stdout
    assert update_result.returncode == 0
    
    # Show group details to verify the updates
    show_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups show test_group",
        env=env
    )
    
    # Check the output contains the updated details
    assert "Updated description" in show_result.stdout
    assert "updated" in show_result.stdout
    assert "original" not in show_result.stdout
    assert show_result.returncode == 0


def test_removing_devices(test_groups_dir):
    """Test removing devices from a group."""
    env = os.environ.copy()
    env["SHELLY_GROUPS_DIR"] = test_groups_dir
    
    # Create a group
    run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups create test_group",
        env=env
    )
    
    # Add two devices to the group
    run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups add-device test_group AABBCCDDEEFF",
        env=env
    )
    run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups add-device test_group 112233445566",
        env=env
    )
    
    # Remove one device
    remove_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups remove-device test_group AABBCCDDEEFF",
        env=env
    )
    
    # Check the device was removed
    assert "Removed device 'AABBCCDDEEFF' from group 'test_group'" in remove_result.stdout
    assert remove_result.returncode == 0
    
    # Show group details to verify the device was removed
    show_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups show test_group",
        env=env
    )
    
    # Check only the remaining device is present
    assert "AABBCCDDEEFF" not in show_result.stdout
    assert "112233445566" in show_result.stdout
    assert show_result.returncode == 0


def test_deleting_group(test_groups_dir):
    """Test deleting a group."""
    env = os.environ.copy()
    env["SHELLY_GROUPS_DIR"] = test_groups_dir
    
    # Create two groups
    run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups create group1",
        env=env
    )
    run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups create group2",
        env=env
    )
    
    # Verify both files exist
    group1_file = os.path.join(test_groups_dir, "group1.yaml")
    group2_file = os.path.join(test_groups_dir, "group2.yaml")
    assert os.path.exists(group1_file)
    assert os.path.exists(group2_file)
    
    # Delete one group
    delete_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups delete group1",
        env=env
    )
    
    # Check the group was deleted
    assert "Deleted group 'group1'" in delete_result.stdout
    assert delete_result.returncode == 0
    
    # Verify the file was deleted
    assert not os.path.exists(group1_file)
    assert os.path.exists(group2_file)
    
    # List groups to verify only one remains
    list_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups list",
        env=env
    )
    
    # Check only group2 is listed
    assert "group1" not in list_result.stdout
    assert "group2" in list_result.stdout


def test_nonexistent_group(test_groups_dir):
    """Test operations on a non-existent group."""
    env = os.environ.copy()
    env["SHELLY_GROUPS_DIR"] = test_groups_dir
    
    # Try to show a non-existent group
    show_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups show nonexistent_group",
        env=env
    )
    
    # Check the error message
    assert "Group 'nonexistent_group' not found" in show_result.stdout
    
    # Try to delete a non-existent group
    delete_result = run_cli_command(
        "python -m src.shelly_manager.interfaces.cli.main groups delete nonexistent_group",
        env=env
    )
    
    # Check the error message
    assert "Group 'nonexistent_group' not found" in delete_result.stdout


if __name__ == "__main__":
    pytest.main(["-v"]) 