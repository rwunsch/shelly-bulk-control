# Next Steps for Shelly Bulk Control

The Shelly Bulk Control project has successfully implemented core features including Device Discovery, Device Grouping, Group Operations, Device Capabilities, and Parameter Mapping. Building on these foundations, here are the recommended next steps:

## 1. Parameter Management Implementation (In Progress)

The parameter management system is now partially implemented with the following features:
- ✅ Parameter mapping between Gen1 and Gen2+ devices
- ✅ Standardized parameter names across all device generations
- ✅ Capability refresh and automatic discovery
- ✅ Parameter support checking across device types
- ✅ Parameter reboot functionality with `--reboot` flag
- ✅ Optimized device discovery for parameter operations
- ✅ Fixed RPC method for Gen2 devices (Sys.SetConfig)

Next steps for parameter management:
- ✅ Implement automatic device restart after parameter changes when needed
- ✅ Develop CLI commands for setting parameters on groups of devices
- Create helper commands for common parameter operations

## 2. API Development

Build a RESTful API to enable integration with other systems:

- Design comprehensive API endpoints for all functionality
- Implement authentication and authorization mechanisms
- Create detailed API documentation and SDK libraries
- Support both device-specific and group-based operations
- Add versioning support for future compatibility

## 3. Web User Interface Development

Develop a modern, responsive web interface using React and Vite:

- Create a dashboard for device and group status visualization
- Build interfaces for device discovery and management
- Implement group creation and configuration screens
- Design intuitive controls for group operations
- Add real-time updates and notifications

## 4. Desktop Application

Create a cross-platform desktop application:

- Integrate the React SPA frontend into an Electron container
- Add system tray integration and native notifications
- Implement offline capabilities and synchronization
- Provide automatic updates and installation wizards
- Create platform-specific optimizations for Windows, macOS, and Linux

## 5. Rules Engine

Implement a simple rules system for device automation:

- Create a rule definition interface with conditions and actions
- Support triggering group operations based on device states
- Example: "If device X reports temperature > 30°C, then turn on all fans in group Y"
- Allow complex condition chaining (AND/OR logic)
- Enable scheduling rules to run at specific times or intervals

## 6. Scheduled Operations

Add support for time-based scheduling of operations:

- Create a scheduler for one-time and recurring operations
- Allow scheduling operations on specific days of the week
- Support cron-like syntax for advanced scheduling
- Implement timezone awareness for global deployments
- Add calendar visualization of scheduled operations

## 7. Notification System

Develop a comprehensive notification system:

- Implement alerts for failed operations and critical events
- Support multiple notification channels (email, SMS, push, webhook)
- Create configurable notification policies per user/group
- Allow custom messages and severity levels
- Implement notification history and acknowledgment tracking

## 8. Advanced Discovery Integration

Enhance device discovery with intelligent features:

- Auto-group devices based on discovery results (by type, location, etc.)
- Periodically verify group membership against discovered devices
- Implement network-aware scanning for multi-subnet environments
- Add support for device location mapping and visualization
- Create automatic device labeling and categorization

## 9. Expanded Operation Types

Extend the operation types supported by the system:

- Add support for more complex operations beyond simple on/off/toggle
- Implement device-specific operations like color control for RGB devices
- Create operation profiles for common scenarios
- Support multi-step operation sequences
- Add conditional branching in operation flows

## 10. Parameter System Enhancements

Further enhance the parameter management system:

- **Add more parameter definitions**: Expand support for other device parameters beyond eco_mode and max_power
  - Support for MQTT configuration parameters
  - Support for network configuration parameters
  - Support for security parameters (auth, cloud connectivity)
  - Support for sensor thresholds and calibration

- **Improve error handling**: Enhance error messages when parameters aren't supported by specific device models
  - Clear messages explaining compatibility issues
  - Suggestions for alternative parameters when available
  - Device-specific guidance for unsupported operations

- **Create example scripts**: Add more examples showcasing the new features, especially for complex parameter management across device groups
  - Bulk configuration of devices by type
  - Migrating configurations between device generations
  - Automated device provisioning workflows

- **Automated testing**: Develop more automated tests for the parameter service to ensure it handles different device generations correctly
  - Comprehensive test coverage for all parameter types
  - Mock testing for API responses
  - Integration tests with real device responses

## Getting Started

The work on Parameter Management is well underway with the successful implementation of parameter mapping between device generations. The immediate next steps are:

1. **Parameter System Enhancements**:
   - Add support for more device parameters beyond eco_mode and max_power
   - Improve error messages for parameter compatibility issues
   - Create more example scripts for common parameter operations
   - Expand automated testing for the parameter service

2. **CLI Command Enhancements**:
   - Add more advanced parameter operations
   - Add support for parameter profiles (multiple parameters at once)

3. **Testing & Validation**:
   - Test parameter operations on both Gen1 and Gen2 devices
   - Verify correct parameter mapping during API calls
   - Test batch operations and device restart functionality

After completing these tasks, focus should shift to the API development and Web UI aspects of the project.