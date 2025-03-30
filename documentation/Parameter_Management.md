# Parameter Management

This document describes how to manage device parameters using the Shelly Bulk Control tool.

## Overview

The Parameter Management feature allows you to discover, view, and modify various configuration parameters on Shelly devices. This system provides a versatile way to:

1. Identify available parameters for different device types
2. Read current parameter values from devices
3. Modify parameters on individual devices
4. Apply parameter changes to groups of devices

The system automatically handles the differences between Gen1 and Gen2 device APIs, making it easy to manage a mixed-device network.

## Unified Parameter Service

The system uses a unified parameter service implementation that combines:

1. **Device Capabilities-based Management**: Intelligently determines API endpoints and parameter paths based on device capabilities.
2. **Legacy Parameter Definitions**: Maintains backward compatibility with older parameter definition approaches.

The Parameter Service now leverages the [Device Capabilities](Device_Capabilities.md) system as its primary source of information about supported parameters. When a parameter operation is requested, the service first checks if the device has a capability definition and looks up the parameter details there. This provides more accurate and device-specific parameter handling.

The service is designed to be flexible and extensible, with priority given to the device capabilities-based approach for modern devices, falling back to legacy approaches when needed. This ensures reliable operation across diverse device types and firmware versions.

**Note**: Code using the old import path `shelly_manager.parameters.parameter_service` will continue to work but is deprecated. Please update your imports to use `shelly_manager.parameter.parameter_service` instead.

## Supported Parameters

The following parameters are currently supported:

| Parameter | Display Name | Description | Device Types |
|-----------|--------------|-------------|--------------|
| eco_mode | ECO Mode | Energy saving mode | Plugs, Power Meters |
| max_power | Maximum Power | Maximum power limit in watts | Plugs, Power Meters |

Support for additional parameters can be added by extending the parameter definitions.

## Command Line Interface

### Listing Parameters

To list available parameters for devices:

```bash
# List parameters for all devices
shelly-bulk-control parameters list

# List parameters for a specific device
shelly-bulk-control parameters list --device shellyplug-s-12345

# List parameters for all devices in a group
shelly-bulk-control parameters list --group living_room
```

### Getting Parameter Values

To get the current value of a parameter:

```bash
# Get eco_mode parameter from a device
shelly-bulk-control parameters get shellyplug-s-12345 eco_mode
```

### Setting Parameter Values

To set a parameter value on a device:

```bash
# Set eco_mode parameter to false
shelly-bulk-control parameters set shellyplug-s-12345 eco_mode false

# Set max_power parameter to 2000W
shelly-bulk-control parameters set shellyplug-s-12345 max_power 2000

# Set parameter and reboot the device after setting it
shelly-bulk-control parameters set shellyplug-s-12345 eco_mode true --reboot
```

The parameter setting command has several optimizations:
- Uses cached devices from the device registry to avoid network scanning when possible
- Only starts mDNS discovery if the device is not found in the registry
- Uses targeted discovery when needed to minimize network traffic

**Important Note:** For Gen1 devices, boolean values for eco_mode parameter must be specified as "true" or "false", not "on" or "off".

### Applying Parameters to Groups

To apply a parameter value to all devices in a group:

```bash
# Disable eco mode for all devices in a group
shelly-bulk-control parameters apply eco_enabled eco_mode false

# Set max power for all devices in a group
shelly-bulk-control parameters apply power_plugs max_power 1500
```

## Value Types

The system supports the following value types:

- **Boolean**: `true` or `false`
- **Integer**: Whole numbers like `42`, `100`
- **Float**: Decimal numbers like `1.5`, `3.14`
- **String**: Text values like `"high"`, `"low"`

When specifying values on the command line, they are automatically converted to the appropriate type.

## Programmatic Usage

You can also use the Parameter Management feature programmatically in your Python code:

```python
import asyncio
from shelly_manager.grouping.group_manager import GroupManager
from shelly_manager.discovery.discovery_service import DiscoveryService
from shelly_manager.parameter.parameter_service import ParameterService

async def main():
    # Initialize services
    discovery_service = DiscoveryService()
    group_manager = GroupManager()
    parameter_service = ParameterService(group_manager, discovery_service)
    
    # Start services without starting discovery (optimization)
    await parameter_service.start(no_discovery=True)
    
    try:
        # Check device registry first (to avoid network scanning)
        device_registry.load_all_devices()
        device = device_registry.get_device("E868E7EA6333")
        
        if not device:
            # Only use discovery if needed
            await discovery_service.start()
            await discovery_service.discover_specific_devices(["E868E7EA6333"])
            device = discovery_service.get_device("E868E7EA6333")
        
        if not device:
            print("Device not found")
            return
            
        # Set parameter value on a device
        success = await parameter_service.set_parameter_value(device, "eco_mode", False)
        if success:
            print(f"Successfully set eco_mode to false")
            
        # Option to reboot device after parameter change
        if success:
            await _reboot_device(device, parameter_service.session)
        
    finally:
        # Stop services
        await parameter_service.stop()
        if discovery_service.started:
            await discovery_service.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

## Adding New Parameters

The system is designed to be extensible, allowing new parameters to be added for different device types. To add a new parameter:

1. Define the parameter in `src/shelly_manager/models/parameters.py`
2. Specify the API mappings for Gen1 and Gen2 devices
3. Update the model parameter map to associate the parameter with device types

Example parameter definition:

```python
# Define the parameter
"brightness": ParameterDefinition(
    name="brightness",
    display_name="Brightness",
    parameter_type=ParameterType.INTEGER,
    description="Light brightness level (0-100)",
    read_only=False,
    default_value=100,
    min_value=0,
    max_value=100,
    unit="%",
    group="light",
    
    # Gen1 API mapping
    gen1_endpoint="light/0",
    gen1_property="brightness",
    
    # Gen2 API mapping
    gen2_method="Light.Set",
    gen2_component="light",
    gen2_property="brightness"
)

# Add to model map
MODEL_PARAMETER_MAP = {
    "shellybulb": ["brightness"],
    # ...other models
}
```

## Parameter Value Formatting

Different device generations may require different value formats for the same parameter. The system handles this automatically:

- For Gen1 devices, boolean parameters like `eco_mode` are formatted as "true"/"false" values
- For other Gen1 parameters, boolean values may use "on"/"off" format
- Gen2/Gen3 devices typically use JSON boolean values (true/false)

These conversions happen automatically in the `format_value_for_gen1` and `format_value_for_gen2` methods.

## Dynamic Parameter Discovery

The system includes support for dynamically discovering parameters from devices. This can be extended in the future to query devices for their available parameters, allowing for a more flexible and adaptable parameter management system.

## Optimized Device Discovery

To improve performance and reduce network traffic, the parameter service now:

1. Prioritizes the device registry for device lookups
2. Only starts mDNS discovery if needed
3. Provides a targeted discovery method to look for specific devices
4. Skips discovery when devices already have valid IP addresses

This makes parameter setting commands faster and more efficient, especially in environments with many devices.

## Error Handling

The Parameter Management system provides detailed error information when operations fail, including:

- Device not found
- Parameter not supported by the device
- Communication errors
- Invalid parameter values

This makes it easier to diagnose and troubleshoot issues when managing device parameters.

## Scripts

The repository includes example scripts for common parameter management tasks:

- `scripts/disable_eco_mode.py`: Disables ECO mode on all devices in the eco_enabled_small group 