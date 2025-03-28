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
python -m shelly_manager.interfaces.cli.main discover [OPTIONS]
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
python -m shelly_manager.interfaces.cli.main discover --ips "192.168.1.100,192.168.1.101,192.168.1.102"
```

This is particularly useful for:
- Testing specific devices
- Working with known devices without scanning the entire network
- Environments where you know device IPs in advance

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
| Discovery Method | How the device was discovered (mDNS or HTTP) |

## Examples

### Basic Network Discovery

```bash
# Discover all devices on the default network
python -m shelly_manager.interfaces.cli.main discover --network 192.168.1.0/24
```

### Targeted Discovery

```bash
# Discover specific devices only
python -m shelly_manager.interfaces.cli.main discover --ips "192.168.1.10,192.168.1.20"
```

### Debug Mode

```bash
# Run discovery with detailed debug output
python -m shelly_manager.interfaces.cli.main discover --network 192.168.1.0/24 --debug
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

### Performance Tips
- For large networks, use targeted discovery with `--ips` when possible
- Consider using smaller subnet ranges for faster scanning
- Increase the timeout if you have devices with slower response times 