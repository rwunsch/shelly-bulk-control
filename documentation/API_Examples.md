# API Examples

This document provides examples for commonly used API operations.

## Device Management

### Enable MQTT for a Device

For Gen1 devices (such as Shelly 1PM), the MQTT configuration uses different parameter names than what appears in the device status. 

**Example: Enable MQTT on a Gen1 device (Shelly 1PM)**

```bash
# Use the mqtt nested object structure for Gen1 devices
curl -X 'POST' \
  'http://localhost:8000/devices/84CCA8ACEF33/settings' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "mqtt": {
    "enable": true
  }
}'
```

Through the Swagger UI:

1. Navigate to http://localhost:8000/docs
2. Find the POST `/devices/{device_id}/settings` endpoint
3. Click "Try it out"
4. Enter the device ID (e.g., `84CCA8ACEF33`)
5. Enter the following JSON in the request body:
   ```json
   {
     "mqtt": {
       "enable": true
     }
   }
   ```

**Important Note:** 
Gen1 devices report their MQTT status as `mqtt_enabled` in the device information, but to change this setting, you must use the nested structure with `mqtt.enable` in the API call. This is due to the internal structure of the Gen1 Shelly API which expects settings in this format.

### Configure MQTT Server for a Device

```bash
curl -X 'POST' \
  'http://localhost:8000/devices/84CCA8ACEF33/settings' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "mqtt": {
    "server": "192.168.1.100:1883"
  }
}'
```

### Configure MQTT Credentials

```bash
curl -X 'POST' \
  'http://localhost:8000/devices/84CCA8ACEF33/settings' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "mqtt": {
    "user": "username",
    "pass": "password"
  }
}'
```

## Group Management

### Create a Group

```bash
curl -X 'POST' \
  'http://localhost:8000/groups' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "name": "Living Room Lights",
  "device_ids": ["84CCA8ACEF33", "ABCDEF123456"],
  "description": "All lights in the living room"
}'
```

### Operate on a Group (Toggle All Devices)

```bash
curl -X 'POST' \
  'http://localhost:8000/groups/Living%20Room%20Lights/operation' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "operation": "toggle", 
  "parameters": {}
}'
```

## Device Discovery

### Trigger Network Scan

```bash
curl -X 'POST' \
  'http://localhost:8000/discovery/scan' \
  -H 'accept: application/json'
```

## Checking for Updates

### Check for Updates on All Devices

```bash
curl -X 'POST' \
  'http://localhost:8000/groups/all-devices/operation' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "operation": "check_updates", 
  "parameters": {}
}'
``` 