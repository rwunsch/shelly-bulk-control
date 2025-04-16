# API Service Deployment Guide

This guide provides detailed instructions for deploying the Shelly Manager API service in various environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Deployment](#local-development-deployment)
  - [Linux/macOS](#linuxmacos)
  - [Windows](#windows)
- [Production Deployment Options](#production-deployment-options)
  - [Standalone Server](#standalone-server)
  - [Linux Systemd Service](#linux-systemd-service)
  - [Docker Deployment](#docker-deployment)
  - [Windows Service](#windows-service)
- [Configuration Options](#configuration-options)
- [Logging](#logging)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying the API service, ensure you have the following prerequisites:

- Python 3.10 or higher installed
- Required Python packages (install via `pip install -r requirements.txt`)
- Network connectivity to the Shelly devices
- For Docker deployment: Docker and Docker Compose installed
- For systemd service: Linux with systemd
- For Windows: PowerShell 5.1 or higher

## Local Development Deployment

### Linux/macOS

For development and testing on Linux or macOS, you can run the API service locally:

#### Using the Development Script

The development script provides hot-reloading for easier development:

```bash
# Navigate to the project root
cd shelly-bulk-control

# Run the development server
./scripts/start_api_dev.sh
```

This will start the server at `http://0.0.0.0:8000` with auto-reload enabled.

#### Manual Run

You can also run the server manually:

```bash
# Navigate to the project root
cd shelly-bulk-control

# Run with Python module
python -m src.shelly_manager.interfaces.api.server

# Alternatively, use the run script
./scripts/run_api_server.py --host=127.0.0.1 --port=8000 --log-level=debug
```

### Windows

For development and testing on Windows, you can use the PowerShell scripts:

#### Using the Development Script

```powershell
# Navigate to the project root
cd shelly-bulk-control

# Run the development server
.\scripts\start_api_dev.ps1
```

This will start the server at `http://0.0.0.0:8000` with auto-reload enabled.

#### Manual Run

```powershell
# Navigate to the project root
cd shelly-bulk-control

# Run with default settings
.\scripts\run_api_server.ps1

# Run with custom settings
.\scripts\run_api_server.ps1 -Host "127.0.0.1" -Port 9000 -LogLevel "debug"

# Run with a config file
.\scripts\run_api_server.ps1 -Config "config\my_config.ini"
```

## Production Deployment Options

### Standalone Server

For a simple standalone server, you can run the API service directly:

#### Linux/macOS

```bash
# Navigate to the project root
cd shelly-bulk-control

# Run the server
./scripts/run_api_server.py --config=/path/to/config.ini
```

#### Windows

```powershell
# Navigate to the project root
cd shelly-bulk-control

# Run the server
.\scripts\run_api_server.ps1 -Config "C:\path\to\config.ini"
```

You might want to use a process manager to ensure the service stays running:

#### Linux: Supervisord

Example supervisord configuration (`/etc/supervisor/conf.d/shelly-manager.conf`):
```ini
[program:shelly-manager]
command=/path/to/shelly-bulk-control/scripts/run_api_server.py --config=/etc/shelly-manager/config.ini
directory=/path/to/shelly-bulk-control
user=shelly
autostart=true
autorestart=true
stderr_logfile=/var/log/shelly-manager/error.log
stdout_logfile=/var/log/shelly-manager/output.log
```

#### Windows: NSSM (Non-Sucking Service Manager)

NSSM is a service manager for Windows that can run any application as a service:

1. Download and install NSSM from https://nssm.cc/
2. Open Command Prompt as Administrator
3. Install the service:

```cmd
nssm install ShellyManagerAPI
```

4. In the NSSM GUI:
   - Set the **Path** to `powershell.exe`
   - Set the **Startup Directory** to the project directory
   - Set **Arguments** to `-ExecutionPolicy Bypass -File scripts\run_api_server.ps1 -Config "C:\path\to\config.ini"`
   - Configure other options as needed (service name, description, startup type, etc.)
   - Click **Install Service**

5. Start the service:

```cmd
nssm start ShellyManagerAPI
```

### Linux Systemd Service

For a more integrated approach on Linux systems, use the provided systemd service file:

1. **Copy the service file:**

```bash
sudo cp docker/shelly-manager-api.service /etc/systemd/system/
```

2. **Create a dedicated user (optional but recommended):**

```bash
sudo useradd -r -s /bin/false shelly
```

3. **Create required directories:**

```bash
# Create configuration directory
sudo mkdir -p /etc/shelly-manager

# Create application directory
sudo mkdir -p /opt/shelly-manager

# Create log directory
sudo mkdir -p /var/log/shelly-manager
```

4. **Copy files to their locations:**

```bash
# Copy the application
sudo cp -r /path/to/shelly-bulk-control/* /opt/shelly-manager/

# Copy the configuration
sudo cp config/api_config.ini /etc/shelly-manager/config.ini

# Set appropriate permissions
sudo chown -R shelly:shelly /opt/shelly-manager /etc/shelly-manager /var/log/shelly-manager
sudo chmod +x /opt/shelly-manager/scripts/run_api_server.py
```

5. **Edit the configuration as needed:**

```bash
sudo nano /etc/shelly-manager/config.ini
```

6. **Enable and start the service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable shelly-manager-api
sudo systemctl start shelly-manager-api
```

7. **Check service status:**

```bash
sudo systemctl status shelly-manager-api
```

8. **View logs:**

```bash
sudo journalctl -u shelly-manager-api
```

### Docker Deployment

The most portable way to deploy the service is using Docker:

1. **Clone the repository:**

```bash
git clone https://github.com/rwunsch/shelly-bulk-control.git
cd shelly-bulk-control
```

2. **Edit the configuration:**

```bash
# Copy the example config 
cp config/api_config.ini config/my_config.ini

# Edit the config
nano config/my_config.ini
```

3. **Build and start the container:**

```bash
# Using Docker Compose
cd docker
docker-compose up -d

# Or build and run manually
docker build -t shelly-manager-api -f docker/Dockerfile .
docker run -d \
  --name shelly-manager-api \
  -p 8000:8000 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  shelly-manager-api
```

4. **Check container logs:**

```bash
docker logs shelly-manager-api
```

5. **Stop the container:**

```bash
# Using Docker Compose
cd docker
docker-compose down

# Or manually
docker stop shelly-manager-api
docker rm shelly-manager-api
```

### Windows Service

For Windows environments, you can install the API service as a Windows service using either:

1. **Windows Service Wrapper (WinSW)**:
   - Download WinSW from https://github.com/winsw/winsw/releases
   - Place the WinSW executable in your project directory
   - Create a configuration file `ShellyManagerAPI.xml`:

```xml
<service>
  <id>ShellyManagerAPI</id>
  <name>Shelly Manager API</name>
  <description>Enterprise-Grade Shelly Device Management API Service</description>
  <executable>powershell.exe</executable>
  <arguments>-ExecutionPolicy Bypass -File "%BASE%\scripts\run_api_server.ps1" -Config "%BASE%\config\api_config.ini"</arguments>
  <workingdirectory>%BASE%</workingdirectory>
  <logpath>%BASE%\logs</logpath>
  <log mode="roll-by-size">
    <sizeThreshold>10240</sizeThreshold>
    <keepFiles>8</keepFiles>
  </log>
  <onfailure action="restart" delay="10 sec"/>
  <resetfailure>1 hour</resetfailure>
</service>
```

2. Install and start the service:

```cmd
ShellyManagerAPI.exe install
ShellyManagerAPI.exe start
```

## Configuration Options

The API service can be configured through command-line arguments or a configuration file. Here are the available configuration options:

### Command-line Arguments

#### Linux/macOS

```
--host       Host to bind the server to (default: 0.0.0.0)
--port       Port to bind the server to (default: 8000)
--config     Path to configuration file
--log-level  Logging level (debug, info, warning, error, critical)
```

#### Windows PowerShell

```powershell
-Host        Host to bind the server to (default: 0.0.0.0)
-Port        Port to bind the server to (default: 8000)
-Config      Path to configuration file
-LogLevel    Logging level (debug, info, warning, error, critical)
```

### Configuration File

Example configuration file:

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

## Logging

The API service logs to both stdout and a log file. The log level can be configured through the command-line arguments or the configuration file.

### Log File Locations

- **Standalone server:** Logs to `logs/shelly_manager.log` in the project directory
- **Systemd service:** Logs to syslog (view with `journalctl -u shelly-manager-api`)
- **Docker container:** Logs to stdout/stderr (view with `docker logs shelly-manager-api`)
- **Windows service:** Logs to the location specified in the service configuration

### Log Rotation

For long-running deployments, it's recommended to set up log rotation:

#### Linux: logrotate

Example logrotate configuration (`/etc/logrotate.d/shelly-manager`):
```
/var/log/shelly-manager/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 shelly shelly
    sharedscripts
    postrotate
        systemctl restart shelly-manager-api
    endscript
}
```

#### Windows: Built-in Service Log Rotation

Windows services using WinSW have built-in log rotation capabilities as specified in the service configuration file.

## Security Considerations

The API service currently does not include authentication or encryption. When deploying in a production environment, consider the following security measures:

### Network Isolation

It's recommended to run the service on a dedicated network segment or VLAN that is isolated from untrusted networks. If possible, limit access to the API service to trusted devices only.

### Reverse Proxy with HTTPS

For secure access, set up a reverse proxy with HTTPS enabled:

#### Nginx Example

```nginx
server {
    listen 443 ssl;
    server_name shelly-manager.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Windows IIS Example

1. Install IIS and URL Rewrite module
2. Create a new website in IIS pointing to a directory with a web.config file:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <rewrite>
            <rules>
                <rule name="ReverseProxyToShellyAPI" stopProcessing="true">
                    <match url="(.*)" />
                    <action type="Rewrite" url="http://localhost:8000/{R:1}" />
                </rule>
            </rules>
        </rewrite>
    </system.webServer>
</configuration>
```

3. Configure SSL certificate in IIS for the website

### Future Authentication

Authentication will be added in a future update. Until then, you can implement application-level authentication through a reverse proxy or API gateway.

## Troubleshooting

### The API service doesn't start

- Check if the required dependencies are installed: `pip install -r requirements.txt`
- Verify the configuration file exists and has correct permissions
- Check the logs for error messages
- On Windows, make sure PowerShell execution policy allows running scripts: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

### Can't connect to the API

- Verify the service is running: 
  - Linux: `systemctl status shelly-manager-api` 
  - Docker: `docker ps` 
  - Windows: `sc query ShellyManagerAPI`
- Check if the host and port settings are correct
- Verify network connectivity between your client and the server
- Check if any firewall is blocking the connection (Windows Firewall, iptables, etc.)

### Devices are not being discovered

- Verify that the API service has network access to the Shelly devices
- Check if the subnet configuration is correct
- Try to manually trigger a scan:
  - Linux/macOS: `curl -X POST http://localhost:8000/discovery/scan`
  - Windows: `Invoke-RestMethod -Method POST -Uri "http://localhost:8000/discovery/scan"`
- Increase the log level to debug for more information

### Performance issues

- Reduce the scan interval in the configuration
- Limit the subnets to scan to only those containing Shelly devices
- For large deployments, consider running the API service on a more powerful machine

### Windows-specific issues

- If you get permission errors, try running PowerShell as Administrator
- Make sure the Python executable is in your PATH
- If you're using a virtual environment, make sure it's properly activated before running scripts
- For "execution policy" errors, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

For more help, check the [API documentation](API_Service.md) or open an issue on the GitHub repository. 