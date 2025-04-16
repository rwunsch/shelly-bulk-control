# API Service

The Shelly Manager API Service provides a RESTful interface for managing Shelly devices and device groups. It allows for device discovery, configuration, parameter management, and group operations through HTTP requests, making it ideal for integration with other systems or building custom user interfaces.

## Running the API Service

The API service can be run in several ways:

### Using the Run Script

```bash
# Start with default settings (host 0.0.0.0, port 8000)
./scripts/run_api_server.py

# Start with a custom configuration file
./scripts/run_api_server.py --config=/path/to/config.ini

# Start with custom host and port
./scripts/run_api_server.py --host=192.168.1.100 --port=9000

# Start with debug logging
./scripts/run_api_server.py --log-level=debug
```

### Development Mode

For development and testing, a hot-reload script is provided that automatically refreshes the service when code changes are detected:

```bash
./scripts/start_api_dev.sh
```

### As a System Service

The API can be installed as a systemd service on Linux systems:

```bash
# Copy the service file
sudo cp docker/shelly-manager-api.service /etc/systemd/system/

# Edit the service file if needed
sudo nano /etc/systemd/system/shelly-manager-api.service

# Create configuration directory
sudo mkdir -p /etc/shelly-manager

# Copy a configuration file
sudo cp config/api_config.ini /etc/shelly-manager/config.ini

# Edit the configuration
sudo nano /etc/shelly-manager/config.ini

# Enable and start the service
sudo systemctl enable shelly-manager-api
sudo systemctl start shelly-manager-api

# Check the service status
sudo systemctl status shelly-manager-api

# View logs
sudo journalctl -u shelly-manager-api
```

### Using Docker

A Docker setup is provided for containerized deployment:

```bash
# Build and start with Docker Compose
cd docker
docker-compose up -d

# Check logs
docker logs shelly-manager-api

# Stop the service
docker-compose down
```

## Configuration

The API service can be configured through command-line arguments or a configuration file.

### Configuration File Structure

```ini
[server]
# Host address to bind the server to (0.0.0.0 for all interfaces)
host = 0.0.0.0
# Port to bind the server to
port = 8000
# Logging level (debug, info, warning, error, critical)
log_level = info

[discovery]
# Scan interval in seconds (how often to automatically scan the network)
scan_interval = 300
# Whether to scan the network on startup
auto_scan_on_startup = true
# Subnet to scan (comma-separated list)
subnets = 192.168.1.0/24

[security]
# Whether to enable authentication (not yet implemented)
enable_auth = false
# CORS origins (comma-separated list, * for all)
cors_origins = *

[data]
# Directory to store data files
data_dir = data/
# Filename for device data
devices_file = devices.yaml
# Filename for group data
groups_file = groups.yaml
```

## API Endpoints

### System Endpoints

#### Get System Status

```
GET /system/status
```

Returns the current status of the API service, including device and group counts.

**Response Example:**
```json
{
  "status": "running",
  "device_count": 5,
  "group_count": 2,
  "discovery_active": false,
  "version": "0.2.0"
}
```

### Discovery Endpoints

#### Trigger Network Scan

```
POST /discovery/scan
```

Initiates a network scan to discover Shelly devices.

**Response Example:**
```json
{
  "status": "success",
  "device_count": 5
}
```

### Device Endpoints

#### Get All Devices

```
GET /devices
```

Optional query parameters:
- `scan` (boolean): Whether to trigger a network scan before returning devices

**Response Example:**
```json
[
  {
    "id": "shellyplug-s-12345",
    "name": "Living Room Lamp",
    "model": "SHPLG-S",
    "ip": "192.168.1.100",
    "mac": "AA:BB:CC:DD:EE:FF",
    "gen": 1,
    "firmware": "1.11.0"
  }
]
```

#### Get Device by ID

```
GET /devices/{device_id}
```

**Response Example:**
```json
{
  "id": "shellyplug-s-12345",
  "name": "Living Room Lamp",
  "model": "SHPLG-S",
  "ip": "192.168.1.100",
  "mac": "AA:BB:CC:DD:EE:FF",
  "gen": 1,
  "firmware": "1.11.0"
}
```

#### Get Device Settings

```
GET /devices/{device_id}/settings
```

**Response Example:**
```json
{
  "name": "Living Room Lamp",
  "wifi_ssid": "MyWiFi",
  "eco_mode": true,
  "max_power": 2500
}
```

#### Update Device Settings

```
POST /devices/{device_id}/settings
```

**Request Body Example:**
```json
{
  "name": "Kitchen Lamp",
  "eco_mode": false
}
```

**Response Example:**
```json
{
  "status": "success"
}
```

#### Perform Device Operation

```
POST /devices/{device_id}/operation
```

**Request Body Example:**
```json
{
  "operation": "toggle",
  "parameters": {
    "channel": 0
  }
}
```

**Response Example:**
```json
{
  "success": true,
  "message": "Operation 'toggle' performed successfully on Kitchen Lamp",
  "details": {
    "state": true
  }
}
```

### Parameter Endpoints

#### Get Supported Parameters

```
GET /parameters/supported
```

**Response Example:**
```json
[
  "eco_mode",
  "max_power",
  "led_status_disable",
  "relay_state"
]
```

#### Get Device Parameters

```
GET /devices/{device_id}/parameters
```

**Response Example:**
```json
{
  "supported_parameters": [
    "eco_mode",
    "max_power",
    "led_status_disable"
  ],
  "current_values": {
    "eco_mode": true,
    "max_power": 2500,
    "led_status_disable": false
  }
}
```

#### Set Device Parameters

```
POST /devices/{device_id}/parameters
```

**Request Body Example:**
```json
{
  "parameters": {
    "eco_mode": true,
    "max_power": 2000
  },
  "reboot_if_needed": true
}
```

**Response Example:**
```json
{
  "status": "success",
  "applied_parameters": {
    "eco_mode": true,
    "max_power": 2000
  },
  "reboot_required": false
}
```

### Capability Endpoints

#### List Available Capabilities

```
GET /capabilities
```

Returns a list of all available device capability definitions.

Optional query parameters:
- `type` (string): Filter capabilities by device type (e.g., "plug", "dimmer")

**Response Example:**
```json
[
  {
    "device_type": "SHPLG-S",
    "name": "Shelly Plug S",
    "gen": 1,
    "parameter_count": 15,
    "api_count": 8
  },
  {
    "device_type": "SHSW-1",
    "name": "Shelly 1",
    "gen": 1,
    "parameter_count": 12,
    "api_count": 6
  }
]
```

#### Get Capability Details

```
GET /capabilities/{device_type}
```

Returns detailed information about a specific device capability definition.

Optional query parameters:
- `parameters_only` (boolean): Return only the parameters section
- `apis_only` (boolean): Return only the APIs section

**Response Example:**
```json
{
  "device_type": "SHPLG-S",
  "name": "Shelly Plug S",
  "gen": 1,
  "apis": {
    "settings": {
      "description": "Gen1 API endpoint: settings",
      "response_structure": { /*...details...*/ }
    },
    "status": {
      "description": "Gen1 API endpoint: status",
      "response_structure": { /*...details...*/ }
    }
  },
  "parameters": {
    "name": {
      "type": "string",
      "description": "Device name",
      "api": "settings",
      "parameter_path": "name"
    },
    "eco_mode": {
      "type": "boolean",
      "description": "Eco mode enabled",
      "api": "settings",
      "parameter_path": "eco_mode_enabled"
    },
    "max_power": {
      "type": "integer",
      "description": "Maximum power in watts",
      "api": "settings",
      "parameter_path": "max_power"
    }
  }
}
```

#### Check Parameter Support

```
GET /capabilities/check-parameter/{parameter_name}
```

Checks which device types support a specific parameter.

Optional query parameters:
- `type` (string): Filter by device type (e.g., "plug", "dimmer")

**Response Example:**
```json
{
  "parameter": "eco_mode",
  "supported_devices": [
    {
      "device_type": "SHPLG-S",
      "name": "Shelly Plug S",
      "gen": 1,
      "parameter_details": {
        "type": "boolean",
        "description": "Eco mode enabled",
        "api": "settings",
        "parameter_path": "eco_mode_enabled"
      }
    },
    {
      "device_type": "SHPLG2-1",
      "name": "Shelly Plug 2",
      "gen": 2,
      "parameter_details": {
        "type": "boolean",
        "description": "Eco mode",
        "api": "Shelly.SetConfig",
        "parameter_path": "sys.device.eco_mode"
      }
    }
  ]
}
```

#### Get Device Capabilities

```
GET /devices/{device_id}/capabilities
```

Returns capability information for a specific device.

**Response Example:**
```json
{
  "device_id": "shellyplug-s-12345",
  "device_type": "SHPLG-S",
  "gen": 1,
  "supported_parameters": [
    "name", "eco_mode", "max_power", "led_status_disable"
  ],
  "supported_operations": [
    "on", "off", "toggle", "reboot"
  ],
  "capability_definition": {
    "parameters": {
      /*...parameter details...*/
    },
    "apis": {
      /*...API details...*/
    }
  }
}
```

#### Discover Device Capabilities

```
POST /devices/{device_id}/capabilities/discover
```

Forces rediscovery of capabilities for a specific device.

**Request Body Example:**
```json
{
  "force": true
}
```

**Response Example:**
```json
{
  "status": "success",
  "device_id": "shellyplug-s-12345",
  "device_type": "SHPLG-S",
  "parameter_count": 15,
  "api_count": 8
}
```

#### Scan Network for Capabilities

```
POST /capabilities/scan
```

Scans the network and discovers capabilities for all found devices.

Optional query parameters:
- `network` (string): Network CIDR to scan (e.g., "192.168.1.0/24")

**Response Example:**
```json
{
  "status": "success",
  "devices_scanned": 5,
  "capabilities_discovered": 3,
  "details": {
    "new": ["SHPLG-S", "SHRGBW2-1"],
    "updated": ["SHSW-1"],
    "failed": []
  }
}
```

#### Standardize Parameter Names

```
POST /capabilities/standardize
```

Standardizes parameter names across different device generations.

**Request Body Example:**
```json
{
  "dry_run": true
}
```

**Response Example:**
```json
{
  "status": "success",
  "changes": {
    "SHPLG-S": {
      "eco_mode_enabled": "eco_mode",
      "max_pwr": "max_power"
    },
    "SHSW-1": {
      "led_power_disable": "led_status_disable"
    }
  }
}
```

#### Refresh Capability Definitions

```
POST /capabilities/refresh
```

Refreshes all capability definition files.

**Request Body Example:**
```json
{
  "force": true,
  "no_discover": false
}
```

**Response Example:**
```json
{
  "status": "success",
  "deleted_files": 5,
  "discovered_capabilities": 5
}
```

### Group Endpoints

#### Get All Groups

```
GET /groups
```

**Response Example:**
```json
[
  {
    "name": "living_room",
    "device_ids": ["shellyplug-s-12345", "shelly25-67890"],
    "description": "Living Room Devices"
  }
]
```

#### Create Group

```
POST /groups
```

**Request Body Example:**
```json
{
  "name": "kitchen",
  "device_ids": ["shellyplug-s-54321", "shelly1-12345"],
  "description": "Kitchen Devices"
}
```

**Response Example:**
```json
{
  "name": "kitchen",
  "device_ids": ["shellyplug-s-54321", "shelly1-12345"],
  "description": "Kitchen Devices"
}
```

#### Get Group by Name

```
GET /groups/{group_name}
```

**Response Example:**
```json
{
  "name": "kitchen",
  "device_ids": ["shellyplug-s-54321", "shelly1-12345"],
  "description": "Kitchen Devices"
}
```

#### Update Group

```
PUT /groups/{group_name}
```

**Request Body Example:**
```json
{
  "device_ids": ["shellyplug-s-54321", "shelly1-12345", "shelly25-11111"],
  "description": "Updated Kitchen Devices"
}
```

**Response Example:**
```json
{
  "name": "kitchen",
  "device_ids": ["shellyplug-s-54321", "shelly1-12345", "shelly25-11111"],
  "description": "Updated Kitchen Devices"
}
```

#### Delete Group

```
DELETE /groups/{group_name}
```

**Response Example:**
```json
{
  "status": "success"
}
```

#### Perform Group Operation

```
POST /groups/{group_name}/operation
```

**Request Body Example:**
```json
{
  "operation": "on",
  "parameters": {
    "channel": 0
  }
}
```

**Response Example:**
```json
{
  "success": true,
  "message": "Operation 'on' performed on group 'kitchen'",
  "details": {
    "device_results": {
      "shellyplug-s-54321": {
        "success": true,
        "details": {
          "state": true
        }
      },
      "shelly1-12345": {
        "success": true,
        "details": {
          "state": true
        }
      }
    }
  }
}
```

#### Set Group Parameters

```
POST /groups/{group_name}/parameters
```

**Request Body Example:**
```json
{
  "parameters": {
    "eco_mode": true,
    "led_status_disable": true
  },
  "reboot_if_needed": false
}
```

**Response Example:**
```json
{
  "status": "complete",
  "results": {
    "shellyplug-s-54321": {
      "success": true,
      "details": {
        "applied_parameters": {
          "eco_mode": true,
          "led_status_disable": true
        },
        "reboot_required": false
      }
    },
    "shelly1-12345": {
      "success": true,
      "details": {
        "applied_parameters": {
          "led_status_disable": true
        },
        "reboot_required": false
      }
    }
  }
}
```

## Using the API Client

The Shelly Manager includes a Python client for interacting with the API service:

```bash
# Get system status
./scripts/test_api_client.py status

# Trigger a device scan
./scripts/test_api_client.py scan

# Get all discovered devices
./scripts/test_api_client.py devices

# Get details for a specific device
./scripts/test_api_client.py device "shellyplug-s-12345"

# Get all groups
./scripts/test_api_client.py groups

# Create a device group
./scripts/test_api_client.py create-group "LivingRoom" --device-ids "shellyplug-s-12345,shelly25-67890" --description "Living Room Devices"

# Perform an operation on a device
./scripts/test_api_client.py operate --device "shellyplug-s-12345" --operation "toggle"

# Perform an operation on a group
./scripts/test_api_client.py operate --group "LivingRoom" --operation "on"

# Set parameters on a device
./scripts/test_api_client.py set-params --device "shellyplug-s-12345" --params '{"eco_mode":true,"max_power":2000}'

# Set parameters on a group with auto-reboot
./scripts/test_api_client.py set-params --group "LivingRoom" --params '{"eco_mode":true}' --reboot
```

## Using the API for Integration

The API service can be used to integrate Shelly device management with other systems:

### Python Integration

```python
import requests

# Base API URL
base_url = "http://localhost:8000"

# Get all devices
response = requests.get(f"{base_url}/devices")
devices = response.json()

# Perform an operation on a device
device_id = devices[0]["id"]
response = requests.post(
    f"{base_url}/devices/{device_id}/operation", 
    json={"operation": "toggle"}
)
result = response.json()

# Create a group
response = requests.post(
    f"{base_url}/groups", 
    json={
        "name": "my_group",
        "device_ids": [d["id"] for d in devices[:2]],
        "description": "My Test Group"
    }
)
group = response.json()

# Set parameters on the group
response = requests.post(
    f"{base_url}/groups/my_group/parameters",
    json={
        "parameters": {"eco_mode": True},
        "reboot_if_needed": True
    }
)
```

### JavaScript/Node.js Integration

```javascript
const axios = require('axios');

// Base API URL
const baseUrl = 'http://localhost:8000';

// Get all devices
axios.get(`${baseUrl}/devices`)
  .then(response => {
    const devices = response.data;
    const deviceId = devices[0].id;
    
    // Perform an operation on a device
    return axios.post(`${baseUrl}/devices/${deviceId}/operation`, {
      operation: 'toggle'
    });
  })
  .then(response => {
    console.log('Operation result:', response.data);
    
    // Create a group
    return axios.post(`${baseUrl}/groups`, {
      name: 'my_group',
      device_ids: ['shellyplug-s-12345', 'shelly25-67890'],
      description: 'My Test Group'
    });
  })
  .then(response => {
    console.log('Group created:', response.data);
    
    // Set parameters on the group
    return axios.post(`${baseUrl}/groups/my_group/parameters`, {
      parameters: {eco_mode: true},
      reboot_if_needed: true
    });
  })
  .then(response => {
    console.log('Parameters set:', response.data);
  })
  .catch(error => {
    console.error('Error:', error.response ? error.response.data : error.message);
  });
```

## Future Improvements

The API service is designed to be extensible. Planned improvements include:

- **Authentication**: Adding JWT-based authentication for securing API access
- **User Management**: Support for multiple users with different permissions
- **WebSocket Support**: Real-time updates via WebSocket connections for device status changes
- **Swagger Documentation**: Interactive API documentation with Swagger UI
- **Rate Limiting**: Protection against API abuse
- **Metrics and Monitoring**: Endpoints for service health and performance monitoring
- **CLI Command Parity**: All CLI commands available as REST API endpoints

For more information about the planned enhancements, see the [Next Steps](./Next_Steps.md) document. 