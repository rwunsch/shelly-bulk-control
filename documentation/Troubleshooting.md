# Troubleshooting

This document provides guidance for troubleshooting common issues with the Shelly Manager.

## API Service Issues

### Connection Issues

- **Problem**: Cannot connect to the API service.
- **Solution**: 
  - Ensure the API service is running.
  - Check the service logs for errors.
  - Verify the host and port settings in your configuration.
  - Check if firewall settings are blocking the port.

### Authentication Issues

- **Problem**: Authentication errors when connecting to the API.
- **Solution**:
  - Verify your authentication credentials.
  - Check if authentication is properly configured in the API settings.
  - Restart the API service after making configuration changes.

## Device Discovery Issues

### Devices Not Found

- **Problem**: Devices not appearing in discovery.
- **Solution**:
  - Ensure devices are on the same network as the Shelly Manager.
  - Verify subnet settings are correct in your configuration.
  - Check if devices are powered on and connected to the network.
  - Try manually adding devices by IP address.

### Incomplete Device Information

- **Problem**: Discovered devices have incomplete information.
- **Solution**:
  - Refresh device data with a new scan.
  - Check device connectivity.
  - Verify the device firmware is up to date.
  - Try rediscovering device capabilities.

## Device Control Issues

### Operations Not Working

- **Problem**: Device operations (toggle, on/off) not working.
- **Solution**:
  - Check device connectivity.
  - Verify you have the correct device ID or name.
  - Check if the device supports the operation.
  - Verify parameter formats for the specific device model.

### Parameter Setting Failures

- **Problem**: Cannot set device parameters.
- **Solution**:
  - Verify the parameter is supported by the device model.
  - Check parameter formatting and value types.
  - Review device capability documentation for parameter constraints.
  - Try updating device capability definitions.

## Group Operation Issues

### Group Operations Failing

- **Problem**: Operations on device groups not working.
- **Solution**:
  - Check if all devices in the group are online.
  - Verify group configuration.
  - Check if any devices in the group have changed IPs.
  - Try refreshing the group device list.

## CLI Tool Issues

### Command Execution Failures

- **Problem**: CLI commands fail to execute.
- **Solution**:
  - Check command syntax and arguments.
  - Verify Python environment is properly set up.
  - Check for permission issues with data directories.
  - Run with `--debug` flag for additional logging.

## Device Capability Issues

### Missing Capabilities

- **Problem**: Device capabilities not detected correctly.
- **Solution**:
  - Force capability rediscovery:
    ```
    shelly-bulk-control capabilities discover --id <device-id> --force
    ```
  - Verify device firmware is up to date.
  - Check if device model is fully supported.

### Unsupported Parameters

- **Problem**: Parameters marked as unsupported for a device.
- **Solution**:
  - Verify the parameter exists for that device model.
  - Check parameter naming for the device generation.
  - Try refreshing device capability definitions.

## API Performance Issues

### Slow Response Times

- **Problem**: API requests take too long to complete.
- **Solution**:
  - Check network connectivity.
  - Reduce the number of devices in bulk operations.
  - Consider increasing timeout values.
  - Optimize database and cache settings.

## Data Storage Issues

### Data Persistence Problems

- **Problem**: Device or group data not persisting after restart.
- **Solution**:
  - Check data directory permissions.
  - Verify configuration file paths.
  - Check for disk space issues.
  - Ensure data files are not corrupted.

## Logging and Diagnostics

### Enabling Debug Logging

For more detailed troubleshooting, enable debug logging:

```bash
# Run API with debug logging
./scripts/run_api_server.py --log-level=debug

# Run CLI commands with debug flag
shelly-bulk-control --debug <command>
```

### Checking Logs

Check the application logs for error messages:

- API service logs: `logs/shelly_manager.log`
- System service logs: `journalctl -u shelly-manager-api`
- Docker logs: `docker logs shelly-manager-api`

## Getting Help

If you continue to experience issues:

1. Check the [GitHub repository](https://github.com/yourusername/shelly-bulk-control) for open issues.
2. Submit a new issue with detailed information about your problem.
3. Include log files and configuration (with sensitive data removed). 