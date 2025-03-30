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
