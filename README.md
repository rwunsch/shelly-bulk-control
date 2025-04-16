# Shelly Manager

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
- **REST API Service**: Run as a continuous service with full REST API capabilities
- **Client Libraries**: Python client library for API integration

## Installation

### Prerequisites

- Python 3.10 or higher
- pip package manager

### Linux Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/rwunsch/shelly-bulk-control.git
   cd shelly-bulk-control
   ```

2. Install the package:
   ```bash
   # Install in development mode
   pip install -e .
   
   # Or install regularly
   pip install .
   ```

3. The `shelly-manager` command should now be available in your terminal:
   ```bash
   shelly-manager --help
   ```

### Windows Installation

1. Clone the repository (using Git Bash, PowerShell, or your preferred tool):
   ```powershell
   git clone https://github.com/rwunsch/shelly-bulk-control.git
   cd shelly-bulk-control
   ```

2. Install the package:
   ```powershell
   pip install -e .
   ```

3. During installation, you may see a warning that the script is not in your PATH. You have several options:

   #### Option 1: Run with full path
   Look for the warning message that shows where the script was installed, and use the full path:
   ```powershell
   C:\Path\To\Python\Scripts\shelly-manager.exe --help
   ```

   #### Option 2: Add to PATH temporarily
   ```powershell
   $env:PATH += ";C:\Path\To\Python\Scripts"
   shelly-manager --help
   ```

   #### Option 3: Add to PATH permanently
   1. Open System Properties (Win+X, then System)
   2. Click "Advanced system settings"
   3. Click "Environment Variables"
   4. Under "User variables", select "Path" and click "Edit"
   5. Click "New" and add the Scripts directory path
   6. Click OK on all dialogs

   #### Option 4: Create a PowerShell alias
   ```powershell
   # Add this to your PowerShell profile for persistence
   Set-Alias -Name shelly-manager -Value "C:\Path\To\Python\Scripts\shelly-manager.exe"
   
   # Test the alias
   shelly-manager --help
   ```

   To make the alias permanent, add the Set-Alias command to your PowerShell profile:
   ```powershell
   # Find your profile location
   echo $PROFILE
   
   # Create the profile if it doesn't exist
   New-Item -Path $PROFILE -ItemType File -Force
   
   # Edit the profile and add the Set-Alias line
   notepad $PROFILE
   ```

### Using WSL (Windows Subsystem for Linux)

If you're working with WSL, you can install the package in your Linux environment for better network scanning performance:

```bash
# Inside WSL terminal
cd ~/path/to/shelly-bulk-control
pip install -e .
shelly-manager --help
```

Alternatively, you can run the WSL version from PowerShell:

```powershell
# Create a function in PowerShell
function shelly-manager {
    wsl -e python -m shelly_manager.interfaces.cli.main $args
}

# Test it
shelly-manager --help
```

## Usage

### Basic Commands

```bash
# Discover devices on your network
shelly-manager discover

# List all discovered devices
shelly-manager devices list

# Get detailed information about a specific device
shelly-manager devices info shellyplug-s-12345
```

### Device Capabilities

```bash
# List all device capability definitions
shelly-manager capabilities list

# Show detailed capabilities for a specific device type
shelly-manager capabilities show Plus1PM

# Check which devices support a specific parameter
shelly-manager capabilities check-parameter eco_mode

# Refresh all capability definitions (rebuild from scratch)
shelly-manager capabilities refresh --force
```

### Parameter Management

```bash
# List available parameters for a device
shelly-manager parameters list --device shellyplug-s-12345

# Get a parameter value
shelly-manager parameters get shellyplug-s-12345 eco_mode

# Set a parameter value
shelly-manager parameters set shellyplug-s-12345 eco_mode true

# Apply a parameter to all devices in a group
shelly-manager parameters apply living_room eco_mode true

# Set parameter and reboot devices if needed
shelly-manager parameters apply living_room eco_mode true --reboot
```

## Running as a Service

Shelly Manager can run as a continuous service with a REST API, which is useful for integration with other systems or building custom user interfaces.

### Starting the API Service

```bash
# Start the API service with default settings
./scripts/run_api_server.py

# Start with a custom configuration file
./scripts/run_api_server.py --config=/path/to/config.ini

# Start with custom host and port
./scripts/run_api_server.py --host=192.168.1.100 --port=9000

# Start in development mode with hot-reload
./scripts/start_api_dev.sh
```

### Using Docker

```bash
# Build and start the service using Docker Compose
cd docker
docker-compose up -d

# Check logs
docker logs shelly-manager-api

# Stop the service
docker-compose down
```

### Using the API Client

A test client is included for interacting with the API:

```bash
# Get system status
./scripts/test_api_client.py status

# Trigger a device scan
./scripts/test_api_client.py scan

# Get all discovered devices
./scripts/test_api_client.py devices

# Create a device group
./scripts/test_api_client.py create-group "LivingRoom" --device-ids "device1,device2"

# Perform an operation on a group
./scripts/test_api_client.py operate --group "LivingRoom" --operation "toggle"

# Set parameters on a device with auto-reboot if needed
./scripts/test_api_client.py set-params --device "device1" --params '{"eco_mode":true}' --reboot
```

For more details about the API service, see the [API documentation](./documentation/API_Service.md).

## Device Type Support

- **Gen1**: SHPLG-S, SHSW-1, SH2.5, SHPLG-U, SHSW-PM, SHRGBW2, SHSW-25
- **Gen2**: PlusPlugS, Plus1PM, Plus2PM, Plus4PM, PlusHT, PlusI4, PlusUNI
- **Gen3**: Mini1PMG3

## Special Groups

### All Devices Group

The system provides a special dynamic group called `all-devices` which automatically includes all discovered devices on your network. This group is always available and doesn't need to be manually created.

You can use it with any group operation command:

```bash
# Check status of all devices on the network
python -m shelly_manager.interfaces.cli.main groups operate status all-devices

# Turn off all devices
python -m shelly_manager.interfaces.cli.main groups operate off all-devices

# Check for firmware updates on all devices
python -m shelly_manager.interfaces.cli.main groups operate check-updates all-devices

# Update firmware on all devices with available updates
python -m shelly_manager.interfaces.cli.main groups operate update-firmware all-devices
```

**Important Note**: When using the `all-devices` group, the system will display a warning and ask for confirmation before performing any operation, as these actions will affect ALL devices on your network.

## Documentation

For more detailed documentation, see the [documentation](./documentation) folder.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
