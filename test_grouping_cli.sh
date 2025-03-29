#!/bin/bash
# Test script for Shelly Manager group CLI commands
# This script demonstrates all group management commands and tests the file-per-group functionality

set -e  # Exit on error

# Use a unique test directory for each run to avoid conflicts
TIMESTAMP=$(date +%s)
TEST_DIR="$(pwd)/data/test_groups_$TIMESTAMP"
export SHELLY_GROUPS_DIR="$TEST_DIR"

# Use unique group names to avoid conflicts with existing groups
GROUP1="test_living_room_$TIMESTAMP"
GROUP2="test_bedroom_$TIMESTAMP"

# Create the test directory
mkdir -p "$TEST_DIR"

# Cleanup function
cleanup() {
  echo "Cleaning up test directory: $TEST_DIR"
  rm -rf "$TEST_DIR"
}

# Register cleanup function to run on exit
trap cleanup EXIT

echo "====== Testing Group CLI Commands ======"
echo "Using groups directory: $TEST_DIR"
echo "SHELLY_GROUPS_DIR environment variable: $SHELLY_GROUPS_DIR"
echo "Using unique group names: $GROUP1 and $GROUP2"

# Test group listing (should be empty)
echo -e "\n----- Testing group listing (empty) -----"
python -m src.shelly_manager.interfaces.cli.main groups list --debug

# Test creating a group
echo -e "\n----- Testing group creation -----"
python -m src.shelly_manager.interfaces.cli.main groups create "$GROUP1" --description "Living room devices" --tags "indoor,main_floor" --debug
echo "Group created successfully"

# Verify file was created
GROUP1_FILE="$TEST_DIR/${GROUP1}.yaml"
if [ -f "$GROUP1_FILE" ]; then
  echo "✓ Group file was created correctly at $GROUP1_FILE"
  echo "File contents:"
  cat "$GROUP1_FILE"
else
  echo "✗ Group file was not created at $GROUP1_FILE"
  echo "Contents of directory:"
  ls -la "$TEST_DIR"
  exit 1
fi

# Test creating a second group
echo -e "\n----- Testing creation of another group -----"
python -m src.shelly_manager.interfaces.cli.main groups create "$GROUP2" --description "Bedroom devices" --tags "indoor,upstairs" --debug
echo "Second group created successfully"

# Verify file was created
GROUP2_FILE="$TEST_DIR/${GROUP2}.yaml"
if [ -f "$GROUP2_FILE" ]; then
  echo "✓ Second group file was created correctly at $GROUP2_FILE"
else
  echo "✗ Second group file was not created at $GROUP2_FILE"
  echo "Contents of directory:"
  ls -la "$TEST_DIR"
  exit 1
fi

# Test listing groups (should show both groups)
echo -e "\n----- Testing group listing (with groups) -----"
python -m src.shelly_manager.interfaces.cli.main groups list --debug

# Test showing group details
echo -e "\n----- Testing show group details -----"
python -m src.shelly_manager.interfaces.cli.main groups show "$GROUP1" --debug

# Test adding devices to a group
echo -e "\n----- Testing adding devices to a group -----"
python -m src.shelly_manager.interfaces.cli.main groups add-device "$GROUP1" AABBCCDDEEFF --debug
python -m src.shelly_manager.interfaces.cli.main groups add-device "$GROUP1" 112233445566 --debug
echo "Devices added successfully"

# Verify devices were added to file
echo "File contents after adding devices:"
cat "$GROUP1_FILE"

# Show the group with devices
echo -e "\n----- Testing show group with devices -----"
python -m src.shelly_manager.interfaces.cli.main groups show "$GROUP1" --debug

# Test updating a group
echo -e "\n----- Testing updating a group -----"
python -m src.shelly_manager.interfaces.cli.main groups update "$GROUP1" --description "Updated living room description" --tags "indoor,main_floor,updated" --debug
echo "Group updated successfully"

# Verify file was updated
echo "File contents after update:"
cat "$GROUP1_FILE"

# Show the updated group
echo -e "\n----- Testing show updated group -----"
python -m src.shelly_manager.interfaces.cli.main groups show "$GROUP1" --debug

# Test removing a device from a group
echo -e "\n----- Testing removing a device from a group -----"
python -m src.shelly_manager.interfaces.cli.main groups remove-device "$GROUP1" 112233445566 --debug
echo "Device removed successfully"

# Verify device was removed in file
echo "File contents after removing device:"
cat "$GROUP1_FILE"

# Show the group after device removal
echo -e "\n----- Testing show group after device removal -----"
python -m src.shelly_manager.interfaces.cli.main groups show "$GROUP1" --debug

# Test deleting a group
echo -e "\n----- Testing deleting a group -----"
python -m src.shelly_manager.interfaces.cli.main groups delete "$GROUP2" --debug
echo "Group deleted successfully"

# Verify file was deleted
if [ ! -f "$GROUP2_FILE" ]; then
  echo "✓ Group file was deleted correctly from $GROUP2_FILE"
else
  echo "✗ Group file was not deleted from $GROUP2_FILE"
  exit 1
fi

# Test listing groups after deletion
echo -e "\n----- Testing group listing after deletion -----"
python -m src.shelly_manager.interfaces.cli.main groups list --debug

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