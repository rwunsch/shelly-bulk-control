# Shelly Bulk Control

A powerful tool for discovering, managing, and controlling multiple Shelly devices on your network.

## Features

- **Device Discovery**: Automatically find all Shelly devices on your network using both mDNS and HTTP probing
- **Device Identification**: Support for Gen1, Gen2, and Gen3 Shelly devices
- **Targeted Discovery**: Specify exact IP addresses to probe for faster testing
- **Detailed Device Information**: View device types, models, firmware versions, and more
- **Structured Configuration**: YAML-based device configurations

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

### Discover Devices

Scan your entire network for Shelly devices:
```bash
python -m shelly_manager.interfaces.cli.main discover --network 192.168.1.0/24
```

Discover specific devices by IP for faster testing:
```bash
python -m shelly_manager.interfaces.cli.main discover --ips "192.168.1.100,192.168.1.101"
```

Enable debug logging for more detailed information:
```bash
python -m shelly_manager.interfaces.cli.main discover --network 192.168.1.0/24 --debug
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
