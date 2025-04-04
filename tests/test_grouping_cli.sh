#!/bin/bash
# Test script for Shelly Manager group CLI commands
# This script demonstrates all group management commands and tests the file-per-group functionality

set -e  # Exit on error

# Use a test directory for groups
TEST_DIR="$(pwd)/data/test_groups"
export SHELLY_GROUPS_DIR="$TEST_DIR"

# Create the test directory
mkdir -p "$TEST_DIR"

# Cleanup function
cleanup() {
  echo "Cleaning up test directory"
  rm -rf "$TEST_DIR"
}

# Register cleanup function to run on exit
trap cleanup EXIT

echo "====== Testing Group CLI Commands ======"
echo "Using groups directory: $TEST_DIR"
echo "SHELLY_GROUPS_DIR environment variable: $SHELLY_GROUPS_DIR"

# Test group listing (should be empty)
echo -e "\n----- Testing group listing (empty) -----"
python -m src.shelly_manager.interfaces.cli.main groups list

# Test creating a group
echo -e "\n----- Testing group creation -----"
python -m src.shelly_manager.interfaces.cli.main groups create living_room --description "Living room devices" --tags "indoor,main_floor"
echo "Group created successfully"

# Verify file was created
if [ -f "$TEST_DIR/living_room.yaml" ]; then
  echo "✓ Group file was created correctly at $TEST_DIR/living_room.yaml"
  echo "File contents:"
  cat "$TEST_DIR/living_room.yaml"
else
  echo "✗ Group file was not created at $TEST_DIR/living_room.yaml"
  exit 1
fi

# Test creating a second group
echo -e "\n----- Testing creation of another group -----"
python -m src.shelly_manager.interfaces.cli.main groups create bedroom --description "Bedroom devices" --tags "indoor,upstairs"
echo "Second group created successfully"

# Verify file was created
if [ -f "$TEST_DIR/bedroom.yaml" ]; then
  echo "✓ Second group file was created correctly at $TEST_DIR/bedroom.yaml"
else
  echo "✗ Second group file was not created at $TEST_DIR/bedroom.yaml"
  exit 1
fi

# Test listing groups (should show both groups)
echo -e "\n----- Testing group listing (with groups) -----"
python -m src.shelly_manager.interfaces.cli.main groups list

# Test showing group details
echo -e "\n----- Testing show group details -----"
python -m src.shelly_manager.interfaces.cli.main groups show living_room

# Test adding devices to a group
echo -e "\n----- Testing adding devices to a group -----"
python -m src.shelly_manager.interfaces.cli.main groups add-device living_room AABBCCDDEEFF
python -m src.shelly_manager.interfaces.cli.main groups add-device living_room 112233445566
echo "Devices added successfully"

# Verify devices were added to file
echo "File contents after adding devices:"
cat "$TEST_DIR/living_room.yaml"

# Show the group with devices
echo -e "\n----- Testing show group with devices -----"
python -m src.shelly_manager.interfaces.cli.main groups show living_room

# Test updating a group
echo -e "\n----- Testing updating a group -----"
python -m src.shelly_manager.interfaces.cli.main groups update living_room --description "Updated living room description" --tags "indoor,main_floor,updated"
echo "Group updated successfully"

# Verify file was updated
echo "File contents after update:"
cat "$TEST_DIR/living_room.yaml"

# Show the updated group
echo -e "\n----- Testing show updated group -----"
python -m src.shelly_manager.interfaces.cli.main groups show living_room

# Test removing a device from a group
echo -e "\n----- Testing removing a device from a group -----"
python -m src.shelly_manager.interfaces.cli.main groups remove-device living_room 112233445566
echo "Device removed successfully"

# Verify device was removed in file
echo "File contents after removing device:"
cat "$TEST_DIR/living_room.yaml"

# Show the group after device removal
echo -e "\n----- Testing show group after device removal -----"
python -m src.shelly_manager.interfaces.cli.main groups show living_room

# Test deleting a group
echo -e "\n----- Testing deleting a group -----"
python -m src.shelly_manager.interfaces.cli.main groups delete bedroom
echo "Group deleted successfully"

# Verify file was deleted
if [ ! -f "$TEST_DIR/bedroom.yaml" ]; then
  echo "✓ Group file was deleted correctly from $TEST_DIR/bedroom.yaml"
else
  echo "✗ Group file was not deleted from $TEST_DIR/bedroom.yaml"
  exit 1
fi

# Test listing groups after deletion
echo -e "\n----- Testing group listing after deletion -----"
python -m src.shelly_manager.interfaces.cli.main groups list

# Count files in directory to ensure we have the right number
FILE_COUNT=$(find "$TEST_DIR" -name "*.yaml" | wc -l)
echo -e "\nTotal YAML files in directory: $FILE_COUNT (expected: 1)"
if [ "$FILE_COUNT" -eq 1 ]; then
  echo "✓ Directory has correct number of files"
else
  echo "✗ Directory has incorrect number of files"
  echo "Files in directory:"
  ls -la "$TEST_DIR"
  exit 1
fi

echo -e "\n====== All tests completed successfully ======" 