# Group Operations

This document describes how to perform operations on groups of Shelly devices using the Shelly Bulk Control tool.

## Overview

The Group Operations feature allows you to execute commands on multiple devices at once by targeting a group. This is particularly useful for controlling multiple devices of the same type or in the same area, such as turning on all lights in a room or toggling all devices in a specific location.

## Available Operations

The following operations are supported:

- **turn_on**: Turn on all devices in a group
- **turn_off**: Turn off all devices in a group
- **toggle**: Toggle the state of all devices in a group
- **status**: Get the status of all devices in a group
- **reboot**: Reboot all devices in a group
- **set_brightness**: Set the brightness level for all light devices in a group

## Command Line Interface

You can execute operations on groups using the CLI:

```bash
# Basic syntax
shelly-bulk-control groups operate execute <group_name> --action <action> [--parameters <params>]

# Examples:
shelly-bulk-control groups operate execute living_room --action turn_on
shelly-bulk-control groups operate execute kitchen --action turn_off
shelly-bulk-control groups operate execute bedroom --action toggle
shelly-bulk-control groups operate execute office --action status
shelly-bulk-control groups operate execute all_devices --action reboot
shelly-bulk-control groups operate execute lights --action set_brightness --parameters brightness=50
```

### Convenience Commands

For common operations, the following shorthand commands are available:

```bash
# Turn on devices in a group
shelly-bulk-control groups operate on <group_name>

# Turn off devices in a group
shelly-bulk-control groups operate off <group_name>

# Toggle devices in a group
shelly-bulk-control groups operate toggle <group_name>

# Get status of devices in a group
shelly-bulk-control groups operate status <group_name>

# Reboot devices in a group
shelly-bulk-control groups operate reboot <group_name>

# Set brightness for light devices (0-100)
shelly-bulk-control groups operate brightness <group_name> <level>
```

## Advanced Usage

### Custom Parameters

You can pass custom parameters to operations using the `--parameters` option. Parameters should be specified in the format `key1=value1,key2=value2`.

```bash
shelly-bulk-control groups operate execute kitchen --action set_brightness --parameters brightness=75,transition=1000
```

### Debug Mode

To enable verbose logging during operations, use the `--debug` flag:

```bash
shelly-bulk-control groups operate on living_room --debug
```

## Programmatic Usage

You can also use the Group Operations feature programmatically in your Python code:

```python
import asyncio
from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.grouping.command_service import GroupCommandService
from shelly_manager.discovery.discovery_service import DiscoveryService

async def main():
    # Initialize services
    group_manager = GroupManager()
    discovery_service = DiscoveryService()
    command_service = GroupCommandService(group_manager, discovery_service)
    
    # Start services
    await discovery_service.start()
    await discovery_service.discover_devices()
    await command_service.start()
    
    try:
        # Turn on all devices in "living_room" group
        result = await command_service.turn_on_group("living_room")
        print(f"Operation result: {result}")
        
        # Set brightness for all lights in "bedroom" group
        result = await command_service.set_brightness_group("bedroom", 50)
        print(f"Operation result: {result}")
        
        # Execute custom operation
        result = await command_service.operate_group(
            "kitchen", 
            "set_color", 
            {"red": 255, "green": 0, "blue": 0}
        )
        print(f"Operation result: {result}")
    
    finally:
        # Stop services
        await command_service.stop()
        await discovery_service.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Handling Different Device Types

The Group Command Service automatically handles different device generations and types:

- **Generation 1 Devices**: Uses the appropriate HTTP endpoints for controlling Gen1 devices
- **Generation 2 Devices**: Uses the RPC API for controlling Gen2 devices

When sending commands to a mixed group containing different device types, the service will adapt each request to match the appropriate API for each device.

## Error Handling

If an operation fails for some devices in a group, the command will continue executing on the remaining devices. The results will include information about which devices succeeded and which failed, along with error messages.

```bash
# Example output for a failed operation
Operation results for group 'living_room'
Action: turn_on
Devices affected: 3
┌────────────────────┬─────────┬───────────────────────────┐
│ Device ID          │ Success │ Result/Error              │
├────────────────────┼─────────┼───────────────────────────┤
│ shellyplug-s-12345 │ Yes     │ {"ison": true}            │
│ shellyplug-s-67890 │ No      │ Connection refused        │
│ shelly1-abcde      │ Yes     │ {"ison": true}            │
└────────────────────┴─────────┴───────────────────────────┘
Success rate: 67%
``` 