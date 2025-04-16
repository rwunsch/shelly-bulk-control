# Shelly Manager Documentation

This directory contains detailed documentation for the Shelly Manager project.

## Core Concepts

- [**Shelly Device Manager Specification**](./Shelly_Device_Manager_Specification.md) - The original specification document outlining the system architecture and design goals
- [**Shelly Device Generations**](./Shelly_Device_Generations.md) - Information about different generations of Shelly devices and their characteristics
- [**Next Steps**](./Next_Steps.md) - Roadmap and future development plans

## Features

- [**Device Discovery**](./Device_Discovery.md) - How device discovery works across different protocols and network segments
- [**Device Grouping**](./Device_Grouping.md) - Creating and managing logical groups of devices
- [**Group Operations**](./Group_Operations.md) - Performing operations on multiple devices simultaneously
- [**Device Capabilities**](./Device_Capabilities.md) - Device capability detection and representation
- [**Parameter Management**](./Parameter_Management.md) - Managing device parameters across different device generations
- [**API Service**](./API_Service.md) - REST API service for integrating with other systems
- [**API Service Deployment**](./API_Service_Deployment.md) - Detailed guide for deploying the API service in various environments

## Development

- [**Testing**](./Testing.md) - Information about testing the system and writing tests

## Media

- Demo Video: [shelly-bulk-controller.mp4](./shelly-bulk-controller.mp4)
- Demo GIF: [shelly-bulk-control.gif](./shelly-bulk-control.gif)

## API Documentation

The API Service documentation is split into two parts:

1. **[API Service](./API_Service.md)** - API endpoints, request/response formats, and basic usage
2. **[API Service Deployment](./API_Service_Deployment.md)** - Deployment options and configurations

The documentation covers:

- Running the service as a standalone server, Docker container, or system service
- Cross-platform support for Linux/macOS (bash scripts) and Windows (PowerShell scripts)
- Available API endpoints for device and group management
- Device capability querying and management
- Request and response formats
- Client libraries and integration examples
- Production deployment considerations
- Security recommendations

## Help

- [**Troubleshooting**](./Troubleshooting.md) - Common issues and their solutions 