from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional, Any, Set, Union
from pydantic import BaseModel, Field
from fastapi.responses import RedirectResponse
import os
import yaml
import re
import asyncio
from datetime import datetime
import time

from ...models.device import Device
from ...models.device_schema import DeviceSchema
from ...discovery.discovery_service import DiscoveryService
from ...config_manager.config_manager import ConfigManager
from ...grouping.group_manager import GroupManager
from ...grouping.command_service import GroupCommandService
from ...parameter.parameter_service import ParameterService
from ...utils.logging import get_logger

# Get logger for this module
logger = get_logger(__name__)

# Pydantic models for request/response
class GroupModel(BaseModel):
    name: str
    device_ids: List[str] = Field(default_factory=list)
    description: Optional[str] = None

class ParameterUpdateModel(BaseModel):
    parameters: Dict[str, Any]
    reboot_if_needed: bool = False

class OperationRequest(BaseModel):
    operation: str
    parameters: Optional[Dict[str, Any]] = None

class OperationResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

class SystemStatusSchema(BaseModel):
    status: str
    device_count: int
    group_count: int
    last_discovery: Optional[str] = None
    last_mdns_received: Optional[str] = None
    discovery_interval_seconds: int
    version: str

class DiscoveryScanResponse(BaseModel):
    status: str
    device_count: Optional[int] = None
    message: Optional[str] = None

class DiscoveryConfigureResponse(BaseModel):
    status: str
    discovery_interval: int

class DeviceParametersResponse(BaseModel):
    parameters: Dict[str, Dict[str, Any]]

class SetParametersResponse(BaseModel):
    status: str
    details: Optional[Dict[str, Any]] = None
    results: Optional[Dict[str, Any]] = None

class GroupParametersResponse(BaseModel):
    status: str
    results: Dict[str, Dict[str, Any]]

class DeviceSettingsResponse(BaseModel):
    settings: Dict[str, Any]

class DeleteGroupResponse(BaseModel):
    status: str

# Initialize FastAPI app
app = FastAPI(
    title="Shelly Device Manager",
    description="Enterprise-Grade Shelly Device Management API",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services
discovery_service = DiscoveryService()
config_manager = ConfigManager()
group_manager = GroupManager()
parameter_service = ParameterService()
command_service = GroupCommandService(group_manager)

# Configuration for periodic discovery
DEFAULT_DISCOVERY_INTERVAL = 300  # 5 minutes in seconds
discovery_interval = DEFAULT_DISCOVERY_INTERVAL
background_discovery_task = None

# Function to run periodic discovery
async def periodic_discovery():
    """Run device discovery at regular intervals"""
    global discovery_interval
    
    while True:
        try:
            logger.info(f"Starting periodic device discovery (interval: {discovery_interval} seconds)")
            await discovery_service.discover_devices()
            logger.info(f"Completed periodic discovery, found {len(discovery_service.devices)} devices")
        except Exception as e:
            logger.error(f"Error during periodic device discovery: {str(e)}")
        
        # Wait for the configured interval
        await asyncio.sleep(discovery_interval)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global background_discovery_task
    
    logger.info("API server starting: Initializing services")
    
    await discovery_service.start()
    await config_manager.start()
    await group_manager.load_groups()
    await parameter_service.initialize()
    await command_service.start()
    
    # Start device discovery automatically on startup
    try:
        logger.info("API server: Starting automatic device discovery on startup")
        await discovery_service.discover_devices()
        logger.info(f"API server: Discovered {len(discovery_service.devices)} devices")
    except Exception as e:
        logger.error(f"API server error during automatic device discovery: {str(e)}")
    
    # Start background task for periodic discovery
    background_discovery_task = asyncio.create_task(periodic_discovery())
    logger.info(f"API server: Started background discovery task with interval of {discovery_interval} seconds")
    logger.info("API server startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up services on shutdown"""
    global background_discovery_task
    
    logger.info("API server shutting down: Cleaning up services")
    
    # Cancel the background task if it's running
    if background_discovery_task:
        background_discovery_task.cancel()
        try:
            await background_discovery_task
        except asyncio.CancelledError:
            logger.info("API server: Background discovery task cancelled")
    
    await discovery_service.stop()
    await config_manager.stop()
    await command_service.stop()
    
    logger.info("API server shutdown complete")

# Add root endpoint
@app.get("/")
async def root():
    """Redirect to API documentation"""
    return RedirectResponse(url="/docs")

# Device endpoints
@app.get("/devices", response_model=List[DeviceSchema])
async def get_devices(scan: bool = Query(False, description="Trigger a new scan before returning devices")):
    """Get all discovered devices
    
    Optionally trigger a new network scan first
    """
    if scan:
        try:
            await discovery_service.discover_devices()
        except Exception as e:
            logger.error(f"Error during device discovery: {str(e)}")
    return [device.to_schema() for device in discovery_service.devices]

@app.get("/devices/{device_id}", response_model=DeviceSchema)
async def get_device(device_id: str):
    """Get a specific device by ID"""
    devices = {device.id: device for device in discovery_service.devices}
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")
    return devices[device_id].to_schema()

@app.get("/devices/{device_id}/settings", response_model=DeviceSettingsResponse)
async def get_device_settings(device_id: str):
    """Get current settings for a specific device"""
    devices = {device.id: device for device in discovery_service.devices}
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device = devices[device_id]
    try:
        settings = await config_manager.get_device_settings(device)
        return {"settings": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/devices/{device_id}/settings", response_model=SetParametersResponse)
async def update_device_settings(device_id: str, settings: Dict[str, Any]):
    """Update settings for a specific device"""
    devices = {device.id: device for device in discovery_service.devices}
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device = devices[device_id]
    try:
        success = await config_manager.apply_settings(device, settings)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to apply settings")
        return {"status": "success", "details": settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/devices/{device_id}/operation", response_model=OperationResponse)
async def perform_device_operation(device_id: str, operation_request: OperationRequest):
    """Perform an operation on a specific device (e.g., reboot, identify, toggle)"""
    logger.info(f"API request: Performing operation '{operation_request.operation}' on device {device_id}")
    
    devices = {device.id: device for device in discovery_service.devices}
    if device_id not in devices:
        logger.warning(f"API request failed: Device {device_id} not found")
        raise HTTPException(status_code=404, detail="Device not found")

    device = devices[device_id]
    operation = operation_request.operation
    parameters = operation_request.parameters or {}
    
    try:
        # Use command service instead of config manager
        result = await command_service.send_command(device, operation, parameters)
        
        # Check if the command was successful
        if isinstance(result, dict) and not result.get("success", True):
            logger.warning(f"API request partially failed: Operation '{operation}' failed on {device_id}: {result.get('error', 'Unknown error')}")
            return OperationResponse(
                success=False,
                message=f"Operation '{operation}' failed: {result.get('error', 'Unknown error')}",
                details=result
            )
            
        logger.info(f"API request successful: Operation '{operation}' performed on {device_id}")
        return OperationResponse(
            success=True,
            message=f"Operation '{operation}' performed successfully on {device.name}",
            details=result
        )
    except Exception as e:
        logger.error(f"API request failed: Operation '{operation}' on {device_id} raised exception: {str(e)}")
        return OperationResponse(
            success=False,
            message=f"Operation '{operation}' failed: {str(e)}",
            details=None
        )

# Group endpoints
@app.get("/groups", response_model=List[GroupModel])
async def get_groups():
    """Get all device groups"""
    groups = group_manager.get_all_groups()
    result = []
    
    for group in groups:
        # Log complete group data structure
        logger.debug(f"Group data structure: {repr(group)}")
        
        try:
            # Check if this is a dictionary or DeviceGroup object
            if isinstance(group, dict):
                # Handle dictionary response
                name = group.get("name", "")
                device_ids = group.get("device_ids", [])
                description = group.get("description", None)
                
                # Print types for debugging
                logger.debug(f"Dict type: name={type(name)}, device_ids={type(device_ids)}, description={type(description)}")
                logger.debug(f"Dict values: name={name}, device_ids={device_ids}, description={description}")
                
                # Ensure correct types
                if not isinstance(device_ids, list):
                    logger.warning(f"device_ids is not a list for group {name}, converting: {device_ids}")
                    # It appears device_ids might be swapped with description
                    if isinstance(description, list):
                        logger.warning(f"Description is a list for group {name}, swapping with device_ids")
                        temp = device_ids
                        device_ids = description
                        description = temp
                    else:
                        device_ids = []
                
                if not isinstance(description, str) and description is not None:
                    logger.warning(f"description is not a string for group {name}, converting: {description}")
                    description = str(description) if description else None
            else:
                # Handle DeviceGroup object - access attributes safely
                name = getattr(group, "name", "")
                device_ids = getattr(group, "device_ids", [])
                description = getattr(group, "description", None)
                
                # Print types for debugging
                logger.debug(f"Object type: name={type(name)}, device_ids={type(device_ids)}, description={type(description)}")
                logger.debug(f"Object values: name={name}, device_ids={device_ids}, description={description}")
                
                # Ensure correct types
                if not isinstance(device_ids, list):
                    logger.warning(f"device_ids is not a list for group {name}, converting: {device_ids}")
                    # It appears device_ids might be swapped with description
                    if isinstance(description, list):
                        logger.warning(f"Description is a list for group {name}, swapping with device_ids")
                        temp = device_ids
                        device_ids = description
                        description = temp
                    else:
                        device_ids = []
                
                if not isinstance(description, str) and description is not None:
                    logger.warning(f"description is not a string for group {name}, converting: {description}")
                    description = str(description) if description else None
            
            # Create the model with verified types
            group_model = GroupModel(
                name=name,
                device_ids=device_ids,
                description=description
            )
            result.append(group_model)
            logger.debug(f"Successfully created GroupModel for {name}")
        except Exception as e:
            logger.error(f"Error processing group {getattr(group, 'name', repr(group))}: {str(e)}")
    
    return result

@app.post("/groups", response_model=GroupModel)
async def create_group(group: GroupModel):
    """Create a new device group"""
    logger.info(f"API request: Creating group '{group.name}' with {len(group.device_ids)} devices")
    
    # Verify that all device IDs exist
    device_ids = {device.id for device in discovery_service.devices}
    for device_id in group.device_ids:
        if device_id not in device_ids:
            logger.warning(f"API request failed: Device {device_id} not found when creating group '{group.name}'")
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    # Check if group already exists
    if group_manager.get_group(group.name):
        logger.warning(f"API request failed: Group '{group.name}' already exists")
        raise HTTPException(status_code=409, detail=f"Group '{group.name}' already exists")
    
    # Create group - use correct parameter order: name, device_ids, description
    created_group = group_manager.create_group(
        name=group.name,
        device_ids=group.device_ids,
        description=group.description
    )
    logger.info(f"API request successful: Created group '{group.name}' with {len(created_group.device_ids)} devices")
    return created_group

@app.get("/groups/{group_name}", response_model=GroupModel)
async def get_group(group_name: str):
    """Get a specific group by name"""
    group = group_manager.get_group(group_name)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group '{group_name}' not found")
    
    # Log complete group data structure for debugging
    logger.debug(f"Group data for {group_name}: {repr(group)}")
    
    try:
        # Check if this is a dictionary or DeviceGroup object
        if isinstance(group, dict):
            # Handle dictionary response
            name = group.get("name", group_name)
            device_ids = group.get("device_ids", [])
            description = group.get("description", None)
            
            # Print types for debugging
            logger.debug(f"Dict type: name={type(name)}, device_ids={type(device_ids)}, description={type(description)}")
            logger.debug(f"Dict values: name={name}, device_ids={device_ids}, description={description}")
            
            # Ensure correct types
            if not isinstance(device_ids, list):
                logger.warning(f"device_ids is not a list for group {name}, converting: {device_ids}")
                # It appears device_ids might be swapped with description
                if isinstance(description, list):
                    logger.warning(f"Description is a list for group {name}, swapping with device_ids")
                    temp = device_ids
                    device_ids = description
                    description = temp
                else:
                    device_ids = []
            
            if not isinstance(description, str) and description is not None:
                logger.warning(f"description is not a string for group {name}, converting: {description}")
                description = str(description) if description else None
        else:
            # Handle DeviceGroup object - access attributes safely
            name = getattr(group, "name", group_name)
            device_ids = getattr(group, "device_ids", [])
            description = getattr(group, "description", None)
            
            # Print types for debugging
            logger.debug(f"Object type: name={type(name)}, device_ids={type(device_ids)}, description={type(description)}")
            logger.debug(f"Object values: name={name}, device_ids={device_ids}, description={description}")
            
            # Ensure correct types
            if not isinstance(device_ids, list):
                logger.warning(f"device_ids is not a list for group {name}, converting: {device_ids}")
                # It appears device_ids might be swapped with description
                if isinstance(description, list):
                    logger.warning(f"Description is a list for group {name}, swapping with device_ids")
                    temp = device_ids
                    device_ids = description
                    description = temp
                else:
                    device_ids = []
            
            if not isinstance(description, str) and description is not None:
                logger.warning(f"description is not a string for group {name}, converting: {description}")
                description = str(description) if description else None
        
        # Create the model with verified types
        return GroupModel(
            name=name,
            device_ids=device_ids,
            description=description
        )
    except Exception as e:
        logger.error(f"Error processing group {group_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing group: {str(e)}")

@app.put("/groups/{group_name}", response_model=GroupModel)
async def update_group(group_name: str, group_update: GroupModel):
    """Update an existing group"""
    # Verify group exists
    existing_group = group_manager.get_group(group_name)
    if not existing_group:
        raise HTTPException(status_code=404, detail=f"Group '{group_name}' not found")
    
    # Verify that all device IDs exist
    device_ids = {device.id for device in discovery_service.devices}
    for device_id in group_update.device_ids:
        if device_id not in device_ids:
            raise HTTPException(status_code=404, detail=f"Device {device_id} not found")
    
    # Update group
    updated_group = await group_manager.update_group(
        group_name, 
        group_update.device_ids, 
        group_update.description
    )
    return updated_group

@app.delete("/groups/{group_name}", response_model=DeleteGroupResponse)
async def delete_group(group_name: str):
    """Delete a group"""
    success = await group_manager.delete_group(group_name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Group '{group_name}' not found")
    return {"status": "success"}

@app.post("/groups/{group_name}/operation", response_model=OperationResponse)
async def perform_group_operation(group_name: str, operation_request: OperationRequest):
    """Perform an operation on all devices in a group"""
    logger.info(f"API request: Performing operation '{operation_request.operation}' on group {group_name}")
    
    # Special handling for firmware update operations
    if operation_request.operation == "update_firmware" or operation_request.operation == "apply_updates":
        try:
            # Use the specific firmware update method from command service
            only_with_updates = not operation_request.parameters.get("check_only", False)
            result = await command_service.apply_updates_group(group_name, only_with_updates)
            
            # Check if operation was successful
            if "error" in result:
                logger.warning(f"API request failed: Firmware update on group {group_name} failed: {result['error']}")
                return OperationResponse(
                    success=False,
                    message=f"Firmware update failed: {result['error']}",
                    details=result
                )
                
            # Process results
            device_results = {}
            success = True
            
            for device_id, device_result in result.get("results", {}).items():
                if not device_result.get("success", True):
                    success = False
                device_results[device_id] = device_result
                
            logger.info(f"API request completed: Firmware update on group {group_name}, success: {success}")
            return OperationResponse(
                success=success,
                message=f"Firmware update performed on group '{group_name}'",
                details={"device_results": device_results}
            )
        except Exception as e:
            logger.error(f"API request failed: Firmware update on group {group_name} raised exception: {str(e)}")
            return OperationResponse(
                success=False,
                message=f"Firmware update failed: {str(e)}",
                details=None
            )
    
    # For other operations, use the general operate_group method
    try:
        # Use command service operate_group
        operation = operation_request.operation
        parameters = operation_request.parameters or {}
        
        result = await command_service.operate_group(group_name, operation, parameters)
        
        # Check if operation was successful
        if "error" in result:
            logger.warning(f"API request failed: Operation '{operation}' on group {group_name} failed: {result['error']}")
            return OperationResponse(
                success=False,
                message=f"Operation '{operation}' failed: {result['error']}",
                details=result
            )
        
        # Process results to match expected format
        device_results = {}
        success = True
        
        for device_id, device_result in result.get("results", {}).items():
            if not device_result.get("success", True):
                success = False
            device_results[device_id] = device_result
        
        logger.info(f"API request completed: Operation '{operation}' on group {group_name}, success: {success}")
        return OperationResponse(
            success=success,
            message=f"Operation '{operation}' performed on group '{group_name}'",
            details={"device_results": device_results}
        )
    except Exception as e:
        logger.error(f"API request failed: Operation '{operation}' on group {group_name} raised exception: {str(e)}")
        return OperationResponse(
            success=False,
            message=f"Operation '{operation}' failed: {str(e)}",
            details=None
        )

# Parameter endpoints
@app.get("/parameters/supported", response_model=Dict[str, Any])
async def get_supported_parameters():
    """Get all supported parameters across all device types"""
    return await parameter_service.get_all_parameters()

@app.get("/devices/{device_id}/parameters", response_model=DeviceParametersResponse)
async def get_device_parameters(device_id: str):
    """Get supported parameters for a specific device"""
    devices = {device.id: device for device in discovery_service.devices}
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device = devices[device_id]
    parameters = await parameter_service.get_supported_parameters(device)
    return {"parameters": parameters}

@app.post("/devices/{device_id}/parameters", response_model=SetParametersResponse)
async def set_device_parameters(device_id: str, parameter_update: ParameterUpdateModel):
    """Set parameters for a specific device"""
    devices = {device.id: device for device in discovery_service.devices}
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    device = devices[device_id]
    try:
        result = await parameter_service.set_parameters(
            device, 
            parameter_update.parameters, 
            parameter_update.reboot_if_needed
        )
        return {"status": "success", "details": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/groups/{group_name}/parameters", response_model=GroupParametersResponse)
async def set_group_parameters(group_name: str, parameter_update: ParameterUpdateModel):
    """Set parameters for all devices in a group"""
    group = group_manager.get_group(group_name)
    if not group:
        raise HTTPException(status_code=404, detail=f"Group '{group_name}' not found")
    
    # Get all devices in the group
    devices = [d for d in discovery_service.devices if d.id in group.device_ids]
    if not devices:
        raise HTTPException(status_code=404, detail=f"No devices found in group '{group_name}'")
    
    results = {}
    for device in devices:
        try:
            result = await parameter_service.set_parameters(
                device, 
                parameter_update.parameters, 
                parameter_update.reboot_if_needed
            )
            results[device.id] = {"success": True, "details": result}
        except Exception as e:
            results[device.id] = {"success": False, "error": str(e)}
    
    return {"status": "complete", "results": results}

# Discovery endpoints
@app.post("/discovery/scan", response_model=DiscoveryScanResponse)
async def trigger_scan():
    """Trigger a new network scan for devices"""
    try:
        await discovery_service.discover_devices()
    except Exception as e:
        logger.error(f"Error during device discovery: {str(e)}")
        return {"status": "error", "message": str(e)}
    return {"status": "success", "device_count": len(discovery_service.devices)}

@app.post("/discovery/configure", response_model=DiscoveryConfigureResponse)
async def configure_discovery(interval_seconds: int = Query(DEFAULT_DISCOVERY_INTERVAL, description="Discovery interval in seconds")):
    """Configure the automatic discovery interval"""
    global discovery_interval
    
    if interval_seconds < 60:
        raise HTTPException(status_code=400, detail="Interval must be at least 60 seconds")
    
    discovery_interval = interval_seconds
    logger.info(f"Updated discovery interval to {discovery_interval} seconds")
    
    return {
        "status": "success", 
        "discovery_interval": discovery_interval
    }

@app.get("/system/status", response_model=SystemStatusSchema)
async def get_system_status():
    """Get system status information"""
    # Format the timestamps or set to None if not available
    last_discovery = None
    if discovery_service.last_discovery_time:
        last_discovery = discovery_service.last_discovery_time.isoformat()
        
    last_mdns = None
    if discovery_service.last_mdns_time:
        last_mdns = discovery_service.last_mdns_time.isoformat()
    
    return {
        "status": "running",
        "device_count": len(discovery_service.devices),
        "group_count": len(group_manager.get_all_groups()),
        "last_discovery": last_discovery,
        "last_mdns_received": last_mdns,
        "discovery_interval_seconds": discovery_interval,
        "version": "0.2.0"
    } 