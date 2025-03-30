# Shelly Bulk Control

A powerful tool for discovering, managing, and controlling multiple Shelly devices on your network.

## Features

- **Device Discovery**: Automatically find all Shelly devices on your network using both mDNS and HTTP probing
- **Device Identification**: Support for Gen1, Gen2, and Gen3 Shelly devices
- **Targeted Discovery**: Specify exact IP addresses to probe for faster testing
- **Detailed Device Information**: View device types, models, firmware versions, and more
- **Structured Configuration**: YAML-based device configurations
- **Multi-Protocol Device Discovery**: Automatically find Shelly devices on your network using mDNS, HTTP scanning, and local network searches
- **Device Grouping**: Create logical groups of devices for bulk operations
- **Group Operations**: Control multiple devices with a single command
- **Device Capabilities**: Automatically detect device capabilities and supported features
- **Parameter Mapping**: Unified parameter interface across different device generations
- **Automated Configuration**: Apply consistent settings across device groups

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/shelly-bulk-control.git
   cd shelly-bulk-control
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Basic Commands

```bash
# Discover devices on your network
shelly-bulk-control discover

# List all discovered devices
shelly-bulk-control devices list

# Get detailed information about a specific device
shelly-bulk-control devices info shellyplug-s-12345
```

### Device Capabilities

```bash
# List all device capability definitions
shelly-bulk-control capabilities list

# Show detailed capabilities for a specific device type
shelly-bulk-control capabilities show Plus1PM

# Check which devices support a specific parameter
shelly-bulk-control capabilities check-parameter eco_mode

# Refresh all capability definitions (rebuild from scratch)
shelly-bulk-control capabilities refresh --force
```

### Parameter Management

```bash
# List available parameters for a device
shelly-bulk-control parameters list --device shellyplug-s-12345

# Get a parameter value
shelly-bulk-control parameters get shellyplug-s-12345 eco_mode

# Set a parameter value
shelly-bulk-control parameters set shellyplug-s-12345 eco_mode true

# Apply a parameter to all devices in a group
shelly-bulk-control parameters apply living_room eco_mode true
```

## Device Type Support

- **Gen1**: SHPLG-S, SHSW-1, SH2.5, SHPLG-U, SHSW-PM, SHRGBW2, SHSW-25
- **Gen2**: PlusPlugS, Plus1PM, Plus2PM, Plus4PM, PlusHT, PlusI4, PlusUNI
- **Gen3**: Mini1PMG3

## Documentation

For more detailed documentation, see the [documentation](./documentation) folder.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
