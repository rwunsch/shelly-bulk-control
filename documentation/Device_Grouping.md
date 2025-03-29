# Device Grouping

This document describes the device grouping functionality of the Shelly Manager.

## Overview

Device grouping allows you to organize your Shelly devices into logical groups for easier management. For example, you might create groups for:

- All devices in a specific room or area
- Devices with similar functions (lights, heating, etc.)
- Devices that should be controlled together

Each group is stored in its own YAML file in the `data/groups` directory, making it easy to manage and organize groups.

## Group Files

Each group is stored as a separate YAML file in the `data/groups` directory. The filename is derived from the group name (with invalid characters replaced with underscores).

For example, a group named "living_room" would be stored in `data/groups/living_room.yaml`.

Each group file has the following structure:

```yaml
name: living_room
description: "Devices in the living room"
device_ids:
  - AABBCCDDEEFF  # Living room lamp
  - 001122334455  # Living room outlet
tags:
  - indoor
  - main_floor
config:
  eco_mode: true
```

Each group contains:
- `name`: The name of the group
- `description`: A human-readable description of the group
- `device_ids`: List of device IDs (MAC addresses without colons)
- `tags`: Optional tags for categorizing groups
- `config`: Optional configuration settings for the group

## CLI Commands

The Shelly Manager CLI provides commands for managing device groups:

### List Groups

```bash
python -m src.shelly_manager.interfaces.cli.main groups list
```

Shows all defined groups and basic information about them.

### Show Group Details

```bash
python -m src.shelly_manager.interfaces.cli.main groups show <group_name>
```

Shows detailed information about a specific group.

### Create a Group

```bash
python -m src.shelly_manager.interfaces.cli.main groups create <group_name> --description "Description" --tags "tag1,tag2"
```

Creates a new empty group.

### Update a Group

```bash
python -m src.shelly_manager.interfaces.cli.main groups update <group_name> --description "New description" --tags "new_tag1,new_tag2"
```

Updates an existing group's properties.

### Delete a Group

```bash
python -m src.shelly_manager.interfaces.cli.main groups delete <group_name>
```

Deletes a group.

### Add a Device to a Group

```bash
python -m src.shelly_manager.interfaces.cli.main groups add-device <group_name> <device_id>
```

Adds a device to a group.

### Remove a Device from a Group

```bash
python -m src.shelly_manager.interfaces.cli.main groups remove-device <group_name> <device_id>
```

Removes a device from a group.

## Using Groups for Operations

In future versions, you'll be able to target operations to specific groups:

```bash
python -m src.shelly_manager.interfaces.cli.main toggle-power --group living_room
```

Or using tags:

```bash
python -m src.shelly_manager.interfaces.cli.main toggle-power --tag outdoor
```

## Programmatic API

You can also use the Group Manager in your own code:

```python
from shelly_manager.grouping.group_manager import GroupManager

# Create a group manager
group_manager = GroupManager()

# Get all groups
groups = group_manager.list_groups()

# Get a specific group
living_room = group_manager.get_group("living_room")

# Get all devices in a group
devices = living_room.device_ids

# Create a new group
new_group = group_manager.create_group(
    name="bedroom",
    description="Bedroom devices",
    device_ids=["AABBCCDDEEFF"],
    tags=["indoor", "bedroom"]
)

# Add a device to a group
group_manager.add_device_to_group("bedroom", "112233445566")
``` 