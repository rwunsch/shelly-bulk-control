from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict

from ...models.device import Device
from ...discovery.discovery_service import DiscoveryService
from ...config_manager.config_manager import ConfigManager

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

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    await discovery_service.start()
    await config_manager.start()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up services on shutdown"""
    await discovery_service.stop()
    await config_manager.stop()

@app.get("/devices", response_model=List[Device])
async def get_devices():
    """Get all discovered devices"""
    return discovery_service.devices

@app.get("/devices/{device_id}/settings")
async def get_device_settings(device_id: str):
    """Get settings for a specific device"""
    devices = {device.id: device for device in discovery_service.devices}
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    return await config_manager.get_device_settings(devices[device_id])

@app.post("/devices/{device_id}/settings")
async def update_device_settings(device_id: str, settings: Dict):
    """Update settings for a specific device"""
    devices = {device.id: device for device in discovery_service.devices}
    if device_id not in devices:
        raise HTTPException(status_code=404, detail="Device not found")
    
    success = await config_manager.apply_settings(devices[device_id], settings)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to apply settings")
    
    return {"status": "success"} 