# Device Discovery

The Shelly Bulk Control tool provides robust device discovery capabilities to find and identify Shelly devices on your network.

## Discovery Methods

The tool uses two primary methods for discovering Shelly devices:

1. **mDNS Discovery**: Leverages multicast DNS to find devices that advertise themselves using the `_shelly._tcp.local` service type.
2. **HTTP Probing**: Directly probes IP addresses with HTTP requests to the `/shelly` endpoint to identify Shelly devices.

### Discovery Process Flow

```
┌─────────────────┐
│   Start Discovery   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   mDNS Discovery   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Devices Found?  │──Yes──►┌─────────────────┐
└────────┬────────┘         │  Return Devices  │
         │                  └─────────────────┘
         │ No
         ▼
┌─────────────────┐
│   HTTP Probing   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Return Devices  │
└─────────────────┘
```

## Discovery Command Options

The CLI tool provides several options for device discovery:

```bash
python -m src.shelly_manager.interfaces.cli.main discover [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--network` | Network address to scan in CIDR notation (e.g., 192.168.1.0/24) |
| `--ips` | Comma-separated list of specific IP addresses to probe |
| `--force-http` | Force HTTP probing even if mDNS devices are found |
| `--debug` | Enable debug logging for detailed discovery information |

## Device Generation Detection

The discovery process automatically identifies the device generation:

1. **Gen1 Devices**: Older devices that use the `/shelly` endpoint with a `type` field (e.g., SHPLG-S, SHSW-1)
2. **Gen2 Devices**: Newer devices with the `/shelly` endpoint containing the `app` field (e.g., PlusPlugS, Plus1PM)
3. **Gen3 Devices**: Latest generation devices, also with an `app` field (e.g., Mini1PMG3)

## mDNS Discovery

The tool uses the `python-zeroconf` library to search for Shelly devices advertising themselves on the local network using mDNS:

1. Listens for devices advertising with service type `_shelly._tcp.local`
2. Extracts device information from TXT records (name, type, generation, etc.)
3. Automatically attempts to discover all Shelly devices on the network

## HTTP Probing

For networks where mDNS might be blocked or for targeted discovery, the tool performs HTTP probing:

1. Sends HTTP GET requests to the `/shelly` endpoint of specified IP addresses
2. Parses the JSON response to extract device information
3. Supports scanning entire subnets or specific IP addresses

### Optimized Chunk-Based Scanning

When scanning large networks, the tool uses an optimized chunking approach:

1. Divides the IP range into chunks of 16 IPs
2. Processes each chunk in parallel
3. Implements timeout and retry mechanisms for reliability
4. Provides progress reporting during scanning

## Targeted Discovery

For faster testing and focused operations, the tool supports discovering specific devices by IP address:

```bash
# Example: Discover only specific devices
python -m src.shelly_manager.interfaces.cli.main discover --ips "192.168.1.100,192.168.1.101,192.168.1.102"
```

This is particularly useful for:
- Testing specific devices
- Working with known devices without scanning the entire network
- Environments where you know device IPs in advance

## Enhanced Device Information

The discovery process now includes additional important device information:

### Firmware Update Detection

The tool automatically checks if firmware updates are available for each device:

1. For Gen1 devices: Checks the `/status` endpoint for the `update.has_update` field
2. For Gen2+ devices: Checks `/rpc/Shelly.GetStatus` and examines `sys.available_updates.stable`
3. Only stable updates are considered (beta updates are detected but not flagged as updates)

### Eco Mode Detection

The tool identifies if eco mode is enabled on devices:

1. For Gen1 devices: Checks eco mode in device settings
2. For Gen2+ devices: Looks in multiple locations including:
   - `sys.device.eco_mode` in the device configuration
   - Switch-specific eco mode settings
   - Root-level eco mode settings

## Discovery Output

The discovery command returns a table with detailed information about each discovered device:

| Field | Description |
|-------|-------------|
| Name | Device name or ID |
| Type | Device type (SHPLG-S, PlusPlugS, etc.) |
| Model | Hardware model number |
| Generation | Device generation (gen1, gen2, gen3) |
| IP Address | Current IP address |
| MAC Address | Device MAC address |
| Firmware | Firmware version |
| Updates | Whether firmware updates are available (YES/NO) |
| Eco Mode | Whether eco mode is enabled (YES/NO) |
| Discovery Method | How the device was discovered (mDNS or HTTP) |

## Device Information Storage

Discovered devices are saved as YAML files in the `data/devices` directory using the format:
```
<type>_<mac-address>.yaml
```

For example:
- `SHPLG-S_E868E7EA6333.yaml`
- `Plus1PM_7C87CE65AF78.yaml`
- `Mini1PMG3_84FCE63E6C98.yaml`

## API Endpoints for Manual Testing

You can manually test or explore devices using these curl commands:

### Gen1 Devices (HTTP GET Endpoints)

```bash
# Get device information
curl "http://[Device_IP]/shelly" | jq

# Get device settings
curl "http://[Device_IP]/settings" | jq

# Get device status (includes update information)
curl "http://[Device_IP]/status" | jq

# Example with a real IP address:
curl "http://192.168.1.100/shelly" | jq
curl "http://192.168.1.100/settings" | jq
curl "http://192.168.1.100/status" | jq
```

### Gen2 Devices (RPC POST Endpoints)

```bash
# Get basic device information
curl -X POST -d '{}' "http://[Device_IP]/rpc/Shelly.GetInfo" | jq

# Get device status (includes update and eco mode information)
curl -X POST -d '{}' "http://[Device_IP]/rpc/Shelly.GetStatus" | jq

# Get device information
curl -X POST -d '{}' "http://[Device_IP]/rpc/Shelly.GetDeviceInfo" | jq

# Get device configuration (includes eco mode settings)
curl -X POST -d '{}' "http://[Device_IP]/rpc/Shelly.GetConfig" | jq

# Example with a real IP address:
curl -X POST -d '{}' "http://192.168.0.7/rpc/Shelly.GetInfo" | jq
curl -X POST -d '{}' "http://192.168.0.7/rpc/Shelly.GetStatus" | jq
curl -X POST -d '{}' "http://192.168.0.7/rpc/Shelly.GetDeviceInfo" | jq
curl -X POST -d '{}' "http://192.168.0.7/rpc/Shelly.GetConfig" | jq
```

### Key API Response Fields

#### Firmware Update Status

For Gen1 devices (in `/status` response):
```json
{
  "update": {
    "has_update": true,
    "old_version": "1.8.0",
    "new_version": "1.9.0"
  }
}
```

For Gen2 devices (in `/rpc/Shelly.GetStatus` response):
```json
{
  "sys": {
    "available_updates": {
      "stable": {
        "version": "1.4.4"
      },
      "beta": {
        "version": "1.5.1-beta2"
      }
    }
  }
}
```

#### Eco Mode Status

For Gen2 devices (in `/rpc/Shelly.GetConfig` response):
```json
{
  "sys": {
    "device": {
      "eco_mode": true
    }
  }
}
```

Or in switch configuration:
```json
{
  "switch:0": {
    "eco_mode": true
  }
}
```

## Examples

### Basic Network Discovery

```bash
# Discover all devices on the default network
python -m src.shelly_manager.interfaces.cli.main discover --network 192.168.1.0/24
```

### Targeted Discovery

```bash
# Discover specific devices only
python -m src.shelly_manager.interfaces.cli.main discover --ips "192.168.1.10,192.168.1.20"
```

### Debug Mode

```bash
# Run discovery with detailed debug output
python -m src.shelly_manager.interfaces.cli.main discover --network 192.168.1.0/24 --debug
```

## Device Type Support

The tool currently identifies and supports the following device types:

### Gen1 Devices
- SHPLG-S (Shelly Plug S)
- SHSW-1 (Shelly 1)
- SH2.5 (Shelly 2.5)
- SHPLG-U (Shelly Plug US)
- SHSW-PM (Shelly 1PM)
- SHRGBW2 (Shelly RGBW2)
- SHSW-25 (Shelly 2.5)

### Gen2 Devices
- PlusPlugS (Shelly Plus Plug S)
- Plus1PM (Shelly Plus 1PM)
- Plus1PMMini (Shelly Plus 1PM Mini)
- Plus2PM (Shelly Plus 2PM)
- Plus4PM (Shelly Plus 4PM)
- PlusHT (Shelly Plus H&T)
- PlusI4 (Shelly Plus I4)
- PlusUNI (Shelly Plus UNI)

### Gen3 Devices
- Mini1PMG3 (Shelly Mini 1PM Gen3)

## Troubleshooting

### No Devices Found via mDNS
- Check if mDNS/Bonjour is enabled on your network
- Ensure multicast traffic is allowed between VLANs if applicable
- Try using `--force-http` to bypass mDNS discovery

### IP Probing Fails
- Verify device IP addresses are correct
- Check network connectivity to the devices
- Ensure the devices are powered on
- Check if HTTP access is blocked by firewalls

### Incorrect Update or Eco Mode Detection
- Use debug mode (`--debug`) to see detailed API responses
- For firmware updates, check if the device is connected to the Shelly Cloud
- For eco mode, verify the setting directly in the device's web interface
- Use the curl commands provided above to manually check device status

### Performance Tips
- For large networks, use targeted discovery with `--ips` when possible
- Consider using smaller subnet ranges for faster scanning
- Increase the timeout if you have devices with slower response times 