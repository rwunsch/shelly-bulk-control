from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class DeviceGeneration(str, Enum):
    """Device generation"""
    UNKNOWN = "unknown"
    GEN1 = "gen1"
    GEN2 = "gen2"
    GEN3 = "gen3"
    GEN4 = "gen4"

class DeviceStatus(str, Enum):
    """Device status"""
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"

class DeviceSchema(BaseModel):
    """Pydantic model for Device API responses"""
    id: str
    name: Optional[str] = None
    device_name: str
    device_type: str
    generation: str
    ip_address: str
    mac_address: str
    firmware_version: Optional[str] = None
    status: str
    discovery_method: str
    last_seen: str  # ISO format datetime string
    hostname: Optional[str] = None
    timezone: Optional[str] = None
    location: Optional[Dict[str, float]] = None
    wifi_ssid: Optional[str] = None
    cloud_enabled: Optional[bool] = None
    cloud_connected: Optional[bool] = None
    mqtt_enabled: Optional[bool] = None
    mqtt_server: Optional[str] = None
    num_outputs: Optional[int] = None
    num_meters: Optional[int] = None
    max_power: Optional[float] = None
    eco_mode_enabled: Optional[bool] = None
    model: Optional[str] = None
    slot: Optional[int] = None
    auth_enabled: Optional[bool] = None
    auth_domain: Optional[str] = None
    fw_id: Optional[str] = None
    raw_type: Optional[str] = None
    raw_model: Optional[str] = None
    raw_app: Optional[str] = None
    features: List[str] = Field(default_factory=list)
    has_update: bool = False
    restart_required: bool = False 