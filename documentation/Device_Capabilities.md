# Device Capabilities Management

This document describes how to manage device capabilities in the Shelly Bulk Control tool.

## Overview

The Device Capabilities system provides a way to:

1. Discover and catalog the capabilities of different Shelly device types
2. Query which parameters and APIs are supported by each device model
3. Load capability definitions from configuration files
4. Automatically detect devices and their supported features

This system serves as the foundation for parameter management and device control, ensuring commands sent to devices are compatible with their specific capabilities.

## Capability Definitions

Each device type (e.g., Shelly Plus 1PM, Shelly Plug S) has a capability definition that includes:

- Basic information (device type ID, name, generation)
- Supported API endpoints
- Supported parameters and how to access them
- Response structures for API calls

Capability definitions are stored as YAML files in the `config/device_capabilities` directory.

## Supported Device Types

The system includes pre-defined capability definitions for various Shelly devices, including:

- Shelly 1, 1PM (Gen1)
- Shelly Plug S (Gen1)
- Shelly RGBW2 (Gen1)
- Shelly Plus 1, 1PM, 2PM (Gen2)
- Shelly Pro 3 (Gen2)
- Shelly Mini 1, 1PM (Gen3)
- And more...

## Command Line Interface

### Listing Available Capabilities

To list all available capability definitions:

```bash
# List all capability definitions
shelly-bulk-control capabilities list

# Filter by device type
shelly-bulk-control capabilities list --type plug
```

### Viewing Capability Details

To view details of a specific capability definition:

```bash
# View all details for a device type
shelly-bulk-control capabilities show SHPLG-S

# View only parameters
shelly-bulk-control capabilities show SHPLG-S --parameters

# View only APIs
shelly-bulk-control capabilities show SHPLG-S --apis
```

### Discovering Device Capabilities

The system can automatically discover and generate capability definitions by probing devices:

```bash
# Discover capabilities for a specific device by IP
shelly-bulk-control capabilities discover --ip 192.168.1.100

# Discover capabilities for a specific device by ID
shelly-bulk-control capabilities discover --id shellyplug-s-12345

# Force rediscovery even if capability already exists
shelly-bulk-control capabilities discover --ip 192.168.1.100 --force
```

### Network Scanning for Device Capabilities

You can scan your network and discover capabilities for all found devices:

```bash
# Scan default network (192.168.1.0/24) and discover capabilities
shelly-bulk-control capabilities discover --scan

# Specify a different network to scan
shelly-bulk-control capabilities discover --scan --network 10.0.0.0/24
```

Or using the module directly:

```bash
python -m src.shelly_manager.interfaces.cli.main capabilities discover --scan
```

This command will:
1. Scan the network for Shelly devices
2. Identify each device's type and model
3. Query the device's API to discover its capabilities
4. Generate and save capability definitions for each device

### Checking Parameter Support

To check which device types support a specific parameter:

```bash
# Check which devices support eco_mode
shelly-bulk-control capabilities check-parameter eco_mode

# Check for a specific device type
shelly-bulk-control capabilities check-parameter max_power --type plus

# Check for a specific device
shelly-bulk-control capabilities check-parameter mqtt_enable --id shellyplug-s-12345
```

## Programmatic Usage

You can use the Device Capabilities system programmatically in your Python code:

```python
from shelly_manager.models.device_capabilities import DeviceCapabilities, CapabilityDiscovery
from shelly_manager.models.device import Device, DeviceGeneration

# Load capability definitions
capabilities = DeviceCapabilities()

# Get capability for a device
device = Device(id="shellyplug-s-12345", ip_address="192.168.1.100")
capability = capabilities.get_capability_for_device(device)

# Check if device supports an API
if capability and capability.has_api("Shelly.GetStatus"):
    print("Device supports Shelly.GetStatus API")
    
# Check if device supports a parameter
if capability and capability.has_parameter("eco_mode"):
    # Get details about the parameter
    param_details = capability.get_parameter_details("eco_mode")
    print(f"Parameter type: {param_details.get('type')}")
    print(f"API to modify: {param_details.get('api')}")
```

## Capability Discovery Process

The capability discovery process works differently for Gen1 vs Gen2/Gen3 devices:

### Gen1 Devices
- Probes common REST API endpoints like `/settings`, `/status`, etc.
- Identifies supported parameters from response data
- Maps parameters to their respective endpoints

### Gen2/Gen3 Devices
- Uses the RPC API to call methods like `Shelly.GetConfig`, `Sys.GetStatus`, etc.
- Identifies supported parameters and their data types
- Maps parameters to their corresponding RPC methods

## Architecture

The Device Capabilities system consists of three main components:

1. **DeviceCapability**: Represents a single device type's capabilities
2. **DeviceCapabilities**: Manages loading and querying capability definitions
3. **CapabilityDiscovery**: Discovers capabilities from live devices

This architecture provides a flexible framework for handling the differences between device generations and models.

## Adding Custom Capability Definitions

You can add custom capability definitions by creating YAML files in the `config/device_capabilities` directory. The file structure should follow this format:

```yaml
id: "CustomDevice"
name: "My Custom Shelly Device"
generation: "gen2"
type_mappings:
  - "mycustom-device"
apis:
  "Shelly.GetStatus":
    description: "Get device status"
    response_structure:
      # Response structure details
parameters:
  "custom_param":
    type: "boolean"
    description: "My custom parameter"
    api: "Shelly.SetConfig"
    parameter_path: "custom.param"
```

## Integration with Parameter Management

The Device Capabilities system integrates with the Parameter Management system to provide a unified way to interact with device parameters:

1. The Parameter Service queries device capabilities to determine if a parameter is supported
2. It uses capability information to construct the correct API calls for different device types
3. This eliminates the need for device-specific code when managing parameters

See the [Parameter Management](Parameter_Management.md) documentation for more details. 