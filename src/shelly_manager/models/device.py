from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from .device_config import device_config_manager, DeviceTypeConfig
import json

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

class Device:
    """Represents a Shelly device"""
    def __init__(
        self,
        id: str,
        name: Optional[str] = None,
        generation: DeviceGeneration = DeviceGeneration.UNKNOWN,
        ip_address: str = "unknown",
        mac_address: str = "unknown",
        firmware_version: Optional[str] = None,
        status: DeviceStatus = DeviceStatus.UNKNOWN,
        discovery_method: str = "unknown",
        hostname: Optional[str] = None,
        timezone: Optional[str] = None,
        location: Optional[Dict[str, float]] = None,
        wifi_ssid: Optional[str] = None,
        cloud_enabled: Optional[bool] = None,
        cloud_connected: Optional[bool] = None,
        mqtt_enabled: Optional[bool] = None,
        mqtt_server: Optional[str] = None,
        eco_mode_enabled: Optional[bool] = None,
        model: Optional[str] = None,
        slot: Optional[int] = None,
        auth_enabled: Optional[bool] = None,
        auth_domain: Optional[str] = None,
        fw_id: Optional[str] = None,  # Added for Gen2+ devices
        raw_type: Optional[str] = None,  # Store the raw device type from the device
        raw_model: Optional[str] = None,  # Store the raw model from the device
        raw_app: Optional[str] = None,  # Store the raw app type from the device
        last_seen: Optional[datetime] = None,  # Added last_seen parameter
        has_update: bool = False,  # New field for firmware update status
        restart_required: bool = False  # Track if device needs restart after config changes
    ):
        self.id = id
        self.name = name
        self.generation = generation
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.firmware_version = firmware_version
        self.status = status
        self.discovery_method = discovery_method
        self.hostname = hostname
        self.timezone = timezone
        self.location = location
        self.wifi_ssid = wifi_ssid
        self.cloud_enabled = cloud_enabled
        self.cloud_connected = cloud_connected
        self.mqtt_enabled = mqtt_enabled
        self.mqtt_server = mqtt_server
        self.eco_mode_enabled = eco_mode_enabled
        self.model = model
        self.slot = slot
        self.auth_enabled = auth_enabled
        self.auth_domain = auth_domain
        self.fw_id = fw_id
        self.raw_type = raw_type
        self.raw_model = raw_model
        self.raw_app = raw_app
        self.last_seen = last_seen or datetime.now()
        self.has_update = has_update  # Initialize new field
        self.restart_required = restart_required  # Track if device needs restart after config changes
        
        # Get device configuration
        self.config = device_config_manager.get_device_config(
            raw_type=raw_type or "",
            raw_app=raw_app or "",
            generation=generation.value,
            raw_model=raw_model or ""
        )
        
        # Set device properties from configuration
        if self.config:
            self.device_name = self.config.name
            self.device_type = self.config.type
            self.num_outputs = self.config.num_outputs
            self.num_meters = self.config.num_meters
            self.max_power = self.config.max_power
            self.features = self.config.features
        else:
            self.device_name = "Unknown Device"
            self.device_type = "unknown"
            self.num_outputs = None
            self.num_meters = None
            self.max_power = None
            self.features = []

    def __str__(self) -> str:
        return f"{self.name or self.id} ({self.device_name})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert device to dictionary for serialization"""
        return {
            "id": self.id,
            "name": self.name,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "generation": self.generation.value,
            "ip_address": self.ip_address,
            "mac_address": self.mac_address,
            "firmware_version": self.firmware_version,
            "status": self.status.value,
            "discovery_method": self.discovery_method,
            "last_seen": self.last_seen.isoformat(),
            "hostname": self.hostname,
            "timezone": self.timezone,
            "location": self.location,
            "wifi_ssid": self.wifi_ssid,
            "cloud_enabled": self.cloud_enabled,
            "cloud_connected": self.cloud_connected,
            "mqtt_enabled": self.mqtt_enabled,
            "mqtt_server": self.mqtt_server,
            "num_outputs": self.num_outputs,
            "num_meters": self.num_meters,
            "max_power": self.max_power,
            "eco_mode_enabled": self.eco_mode_enabled,
            "model": self.model,
            "slot": self.slot,
            "auth_enabled": self.auth_enabled,
            "auth_domain": self.auth_domain,
            "fw_id": self.fw_id,
            "raw_type": self.raw_type,
            "raw_model": self.raw_model,
            "raw_app": self.raw_app,
            "features": self.features,
            "has_update": self.has_update,
            "restart_required": self.restart_required
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Device":
        """Create device from dictionary"""
        # Remove computed properties that are set in constructor
        data = data.copy()
        data.pop("device_name", None)
        data.pop("device_type", None)
        data.pop("num_outputs", None)
        data.pop("num_meters", None)
        data.pop("max_power", None)
        data.pop("features", None)
        
        # Convert string values back to enums
        if "generation" in data:
            data["generation"] = DeviceGeneration(data["generation"])
        if "status" in data:
            data["status"] = DeviceStatus(data["status"])
        
        # Convert ISO format string back to datetime
        if "last_seen" in data:
            data["last_seen"] = datetime.fromisoformat(data["last_seen"])
        
        return cls(**data)

    def to_schema(self) -> "DeviceSchema":
        """Convert to DeviceSchema for API responses"""
        from src.shelly_manager.models.device_schema import DeviceSchema
        
        return DeviceSchema(
            id=self.id,
            name=self.name,
            device_name=self.device_name,
            device_type=self.device_type,
            generation=self.generation.value,
            ip_address=self.ip_address,
            mac_address=self.mac_address,
            firmware_version=self.firmware_version,
            status=self.status.value,
            discovery_method=self.discovery_method,
            last_seen=self.last_seen.isoformat() if self.last_seen else None,
            hostname=self.hostname,
            timezone=self.timezone,
            location=self.location,
            wifi_ssid=self.wifi_ssid,
            cloud_enabled=self.cloud_enabled,
            cloud_connected=self.cloud_connected,
            mqtt_enabled=self.mqtt_enabled,
            mqtt_server=self.mqtt_server,
            num_outputs=self.num_outputs,
            num_meters=self.num_meters,
            max_power=self.max_power,
            eco_mode_enabled=self.eco_mode_enabled,
            model=self.model,
            slot=self.slot,
            auth_enabled=self.auth_enabled,
            auth_domain=self.auth_domain,
            fw_id=self.fw_id,
            raw_type=self.raw_type,
            raw_model=self.raw_model,
            raw_app=self.raw_app,
            features=self.features,
            has_update=self.has_update,
            restart_required=self.restart_required
        ) 