"""Models for device parameter management."""

from enum import Enum
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ParameterType(Enum):
    """Enum for parameter types."""
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    ENUM = "enum"
    OBJECT = "object"
    ARRAY = "array"


@dataclass
class ParameterDefinition:
    """Definition for a parameter."""
    name: str
    display_name: str
    parameter_type: ParameterType
    description: str
    read_only: bool = False
    default_value: Any = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    enum_values: Optional[List[Any]] = None
    unit: Optional[str] = None
    group: Optional[str] = None
    
    # Generation-specific endpoints
    gen1_endpoint: Optional[str] = None
    gen1_property: Optional[str] = None
    gen2_method: Optional[str] = None
    gen2_component: Optional[str] = None
    gen2_property: Optional[str] = None
    
    def validate_value(self, value: Any) -> bool:
        """Validate a value against this parameter definition."""
        if self.read_only:
            return False
            
        if value is None:
            return False
            
        if self.parameter_type == ParameterType.BOOLEAN:
            return isinstance(value, bool)
            
        elif self.parameter_type == ParameterType.INTEGER:
            if not isinstance(value, int):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
            return True
            
        elif self.parameter_type == ParameterType.FLOAT:
            if not isinstance(value, (int, float)):
                return False
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
            return True
            
        elif self.parameter_type == ParameterType.STRING:
            return isinstance(value, str)
            
        elif self.parameter_type == ParameterType.ENUM:
            if self.enum_values is None:
                return False
            return value in self.enum_values
            
        elif self.parameter_type == ParameterType.OBJECT:
            return isinstance(value, dict)
            
        elif self.parameter_type == ParameterType.ARRAY:
            return isinstance(value, list)
            
        return False
        
    def format_value_for_gen1(self, value: Any) -> str:
        """Format a value for the Gen1 API."""
        if self.parameter_type == ParameterType.BOOLEAN:
            # Convert boolean values to strings
            # For eco_mode specifically, use true/false instead of on/off
            if self.name == "eco_mode" or self.name == "eco_mode_enabled":
                return "true" if value else "false"
            else:
                return "on" if value else "off"
        elif self.parameter_type == ParameterType.INTEGER:
            return str(int(value))
        elif self.parameter_type == ParameterType.FLOAT:
            return str(float(value))
        else:
            return str(value)
        
    def format_value_for_gen2(self, value: Any) -> Any:
        """Format a value for Gen2 API."""
        return value


# Common parameter definitions for both generations
COMMON_PARAMETERS = {
    # Power Management Parameters
    "eco_mode": ParameterDefinition(
        name="eco_mode",
        display_name="ECO Mode",
        parameter_type=ParameterType.BOOLEAN,
        description="Energy saving mode",
        read_only=False,
        default_value=False,
        group="power",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="eco_mode",
        
        # Gen2 API mapping - Using correct Sys.SetConfig method
        gen2_method="Sys.SetConfig",
        gen2_component="device", 
        gen2_property="eco_mode"
    ),
    "max_power": ParameterDefinition(
        name="max_power",
        display_name="Maximum Power",
        parameter_type=ParameterType.FLOAT,
        description="Maximum power in watts",
        read_only=False,
        default_value=2500.0,
        min_value=0.0,
        max_value=3500.0,
        unit="W",
        group="power",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="max_power",
        
        # Gen2 API mapping - Using correct Sys.SetConfig method
        gen2_method="Sys.SetConfig",
        gen2_component="sys",
        gen2_property="max_power"
    ),
    "power_on_state": ParameterDefinition(
        name="power_on_state",
        display_name="Power On State",
        parameter_type=ParameterType.ENUM,
        description="Default state when the device is powered on",
        read_only=False,
        default_value="last",
        enum_values=["on", "off", "last"],
        group="power",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="default_state",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="switch:0",
        gen2_property="initial_state"
    ),
    "auto_on": ParameterDefinition(
        name="auto_on",
        display_name="Auto On",
        parameter_type=ParameterType.BOOLEAN,
        description="Automatically turn on after a specified time",
        read_only=False,
        default_value=False,
        group="power",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="auto_on",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="switch:0",
        gen2_property="auto_on"
    ),
    "auto_on_delay": ParameterDefinition(
        name="auto_on_delay",
        display_name="Auto On Delay",
        parameter_type=ParameterType.INTEGER,
        description="Time in seconds before auto on",
        read_only=False,
        default_value=60,
        min_value=0,
        max_value=86400,
        unit="s",
        group="power",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="auto_on_delay",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="switch:0",
        gen2_property="auto_on_delay"
    ),
    "auto_off": ParameterDefinition(
        name="auto_off",
        display_name="Auto Off",
        parameter_type=ParameterType.BOOLEAN,
        description="Automatically turn off after a specified time",
        read_only=False,
        default_value=False,
        group="power",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="auto_off",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="switch:0",
        gen2_property="auto_off"
    ),
    "auto_off_delay": ParameterDefinition(
        name="auto_off_delay",
        display_name="Auto Off Delay",
        parameter_type=ParameterType.INTEGER,
        description="Time in seconds before auto off",
        read_only=False,
        default_value=60,
        min_value=0,
        max_value=86400,
        unit="s",
        group="power",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="auto_off_delay",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="switch:0",
        gen2_property="auto_off_delay"
    ),
    
    # Network Parameters
    "static_ip_config": ParameterDefinition(
        name="static_ip_config",
        display_name="Static IP Configuration",
        parameter_type=ParameterType.BOOLEAN,
        description="Use static IP instead of DHCP",
        read_only=False,
        default_value=False,
        group="network",
        
        # Gen1 API mapping
        gen1_endpoint="settings/sta",
        gen1_property="ipv4_method",  # "static" or "dhcp"
        
        # Gen2 API mapping
        gen2_method="Wifi.SetConfig",
        gen2_component="wifi",
        gen2_property="sta_static_enable"
    ),
    "ip_address": ParameterDefinition(
        name="ip_address",
        display_name="IP Address",
        parameter_type=ParameterType.STRING,
        description="Static IP address",
        read_only=False,
        group="network",
        
        # Gen1 API mapping
        gen1_endpoint="settings/sta",
        gen1_property="ip",
        
        # Gen2 API mapping
        gen2_method="Wifi.SetConfig",
        gen2_component="wifi",
        gen2_property="sta_ip"
    ),
    "gateway": ParameterDefinition(
        name="gateway",
        display_name="Gateway",
        parameter_type=ParameterType.STRING,
        description="Network gateway",
        read_only=False,
        group="network",
        
        # Gen1 API mapping
        gen1_endpoint="settings/sta",
        gen1_property="gw",
        
        # Gen2 API mapping
        gen2_method="Wifi.SetConfig",
        gen2_component="wifi",
        gen2_property="sta_gw"
    ),
    "subnet_mask": ParameterDefinition(
        name="subnet_mask",
        display_name="Subnet Mask",
        parameter_type=ParameterType.STRING,
        description="Network subnet mask",
        read_only=False,
        default_value="255.255.255.0",
        group="network",
        
        # Gen1 API mapping
        gen1_endpoint="settings/sta",
        gen1_property="mask",
        
        # Gen2 API mapping
        gen2_method="Wifi.SetConfig",
        gen2_component="wifi",
        gen2_property="sta_mask"
    ),
    "dns_server": ParameterDefinition(
        name="dns_server",
        display_name="DNS Server",
        parameter_type=ParameterType.STRING,
        description="Primary DNS server",
        read_only=False,
        group="network",
        
        # Gen1 API mapping
        gen1_endpoint="settings/sta",
        gen1_property="dns",
        
        # Gen2 API mapping
        gen2_method="Wifi.SetConfig",
        gen2_component="wifi",
        gen2_property="sta_dns"
    ),
    
    # MQTT Parameters
    "mqtt_enable": ParameterDefinition(
        name="mqtt_enable",
        display_name="Enable MQTT",
        parameter_type=ParameterType.BOOLEAN,
        description="Enable MQTT client",
        read_only=False,
        default_value=False,
        group="mqtt",
        
        # Gen1 API mapping
        gen1_endpoint="settings/mqtt",
        gen1_property="enable",
        
        # Gen2 API mapping
        gen2_method="MQTT.SetConfig",
        gen2_component="mqtt",
        gen2_property="enable"
    ),
    "mqtt_server": ParameterDefinition(
        name="mqtt_server",
        display_name="MQTT Server",
        parameter_type=ParameterType.STRING,
        description="MQTT broker server address",
        read_only=False,
        group="mqtt",
        
        # Gen1 API mapping
        gen1_endpoint="settings/mqtt",
        gen1_property="server",
        
        # Gen2 API mapping
        gen2_method="MQTT.SetConfig",
        gen2_component="mqtt",
        gen2_property="server"
    ),
    "mqtt_port": ParameterDefinition(
        name="mqtt_port",
        display_name="MQTT Port",
        parameter_type=ParameterType.INTEGER,
        description="MQTT broker port",
        read_only=False,
        default_value=1883,
        min_value=1,
        max_value=65535,
        group="mqtt",
        
        # Gen1 API mapping
        gen1_endpoint="settings/mqtt",
        gen1_property="port",
        
        # Gen2 API mapping
        gen2_method="MQTT.SetConfig",
        gen2_component="mqtt",
        gen2_property="port"
    ),
    "mqtt_username": ParameterDefinition(
        name="mqtt_username",
        display_name="MQTT Username",
        parameter_type=ParameterType.STRING,
        description="MQTT authentication username",
        read_only=False,
        group="mqtt",
        
        # Gen1 API mapping
        gen1_endpoint="settings/mqtt",
        gen1_property="user",
        
        # Gen2 API mapping
        gen2_method="MQTT.SetConfig",
        gen2_component="mqtt",
        gen2_property="user"
    ),
    "mqtt_password": ParameterDefinition(
        name="mqtt_password",
        display_name="MQTT Password",
        parameter_type=ParameterType.STRING,
        description="MQTT authentication password",
        read_only=False,
        group="mqtt",
        
        # Gen1 API mapping
        gen1_endpoint="settings/mqtt",
        gen1_property="pass",
        
        # Gen2 API mapping
        gen2_method="MQTT.SetConfig",
        gen2_component="mqtt",
        gen2_property="pass"
    ),
    "mqtt_client_id": ParameterDefinition(
        name="mqtt_client_id",
        display_name="MQTT Client ID",
        parameter_type=ParameterType.STRING,
        description="MQTT client identifier",
        read_only=False,
        group="mqtt",
        
        # Gen1 API mapping
        gen1_endpoint="settings/mqtt",
        gen1_property="client_id",
        
        # Gen2 API mapping
        gen2_method="MQTT.SetConfig",
        gen2_component="mqtt",
        gen2_property="client_id"
    ),
    "mqtt_clean_session": ParameterDefinition(
        name="mqtt_clean_session",
        display_name="MQTT Clean Session",
        parameter_type=ParameterType.BOOLEAN,
        description="Start fresh MQTT session on connect",
        read_only=False,
        default_value=True,
        group="mqtt",
        
        # Gen1 API mapping
        gen1_endpoint="settings/mqtt",
        gen1_property="clean_session",
        
        # Gen2 API mapping
        gen2_method="MQTT.SetConfig",
        gen2_component="mqtt",
        gen2_property="clean_session"
    ),
    "mqtt_keep_alive": ParameterDefinition(
        name="mqtt_keep_alive",
        display_name="MQTT Keep Alive",
        parameter_type=ParameterType.INTEGER,
        description="MQTT keep alive interval in seconds",
        read_only=False,
        default_value=60,
        min_value=15,
        max_value=3600,
        group="mqtt",
        unit="s",
        
        # Gen1 API mapping
        gen1_endpoint="settings/mqtt",
        gen1_property="keep_alive",
        
        # Gen2 API mapping
        gen2_method="MQTT.SetConfig",
        gen2_component="mqtt",
        gen2_property="keepalive"
    ),
    
    # UI and Visual Settings
    "led_status_disable": ParameterDefinition(
        name="led_status_disable",
        display_name="Disable Status LED",
        parameter_type=ParameterType.BOOLEAN,
        description="Disable the status LED",
        read_only=False,
        default_value=False,
        group="ui",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="led_status_disable",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="sys",
        gen2_property="led_disable"
    ),
    "led_power_disable": ParameterDefinition(
        name="led_power_disable",
        display_name="Disable Power LED",
        parameter_type=ParameterType.BOOLEAN,
        description="Disable the power LED",
        read_only=False,
        default_value=False,
        group="ui",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="led_power_disable",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="sys",
        gen2_property="led_power_disable"
    ),
    "night_mode_enable": ParameterDefinition(
        name="night_mode_enable",
        display_name="Night Mode",
        parameter_type=ParameterType.BOOLEAN,
        description="Enable night mode (dimmed LEDs)",
        read_only=False,
        default_value=False,
        group="ui",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="night_mode",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="sys",
        gen2_property="night_mode"
    ),
    
    # Security Settings
    "cloud_enable": ParameterDefinition(
        name="cloud_enable",
        display_name="Cloud Enabled",
        parameter_type=ParameterType.BOOLEAN,
        description="Enable Shelly cloud connection",
        read_only=False,
        default_value=True,
        group="security",
        
        # Gen1 API mapping
        gen1_endpoint="settings/cloud",
        gen1_property="enabled",
        
        # Gen2 API mapping
        gen2_method="Cloud.SetConfig",
        gen2_component="cloud",
        gen2_property="enable"
    ),
    "login_enabled": ParameterDefinition(
        name="login_enabled",
        display_name="Enable Authentication",
        parameter_type=ParameterType.BOOLEAN,
        description="Enable authentication for device web access",
        read_only=False,
        default_value=False,
        group="security",
        
        # Gen1 API mapping
        gen1_endpoint="settings/login",
        gen1_property="enabled",
        
        # Gen2 API mapping - Not directly mappable for Gen2
        gen2_method="",
        gen2_component="",
        gen2_property=""
    ),
    "username": ParameterDefinition(
        name="username",
        display_name="Admin Username",
        parameter_type=ParameterType.STRING,
        description="Username for device web access",
        read_only=False,
        group="security",
        
        # Gen1 API mapping
        gen1_endpoint="settings/login",
        gen1_property="username",
        
        # Gen2 API mapping - Not directly mappable for Gen2
        gen2_method="",
        gen2_component="",
        gen2_property=""
    ),
    "password": ParameterDefinition(
        name="password",
        display_name="Admin Password",
        parameter_type=ParameterType.STRING,
        description="Password for device web access",
        read_only=False,
        group="security",
        
        # Gen1 API mapping
        gen1_endpoint="settings/login",
        gen1_property="password",
        
        # Gen2 API mapping - Not directly mappable for Gen2
        gen2_method="",
        gen2_component="",
        gen2_property=""
    ),
    
    # Sensor and Threshold Settings
    "temperature_unit": ParameterDefinition(
        name="temperature_unit",
        display_name="Temperature Unit",
        parameter_type=ParameterType.ENUM,
        description="Unit for temperature display",
        read_only=False,
        default_value="C",
        enum_values=["C", "F"],
        group="sensors",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="temperature_unit",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="sys",
        gen2_property="temperature_unit"
    ),
    "temperature_threshold": ParameterDefinition(
        name="temperature_threshold",
        display_name="Temperature Threshold",
        parameter_type=ParameterType.FLOAT,
        description="Temperature change threshold for reporting",
        read_only=False,
        default_value=1.0,
        min_value=0.1,
        max_value=10.0,
        unit="°C",
        group="sensors",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="temperature_threshold",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="temperature:0",
        gen2_property="report_threshold"
    ),
    "humidity_threshold": ParameterDefinition(
        name="humidity_threshold",
        display_name="Humidity Threshold",
        parameter_type=ParameterType.FLOAT,
        description="Humidity change threshold for reporting",
        read_only=False,
        default_value=5.0,
        min_value=1.0,
        max_value=20.0,
        unit="%",
        group="sensors",
        
        # Gen1 API mapping
        gen1_endpoint="settings",
        gen1_property="humidity_threshold",
        
        # Gen2 API mapping
        gen2_method="Sys.SetConfig",
        gen2_component="humidity:0",
        gen2_property="report_threshold"
    ),
}


# Map of model prefixes to available parameters
MODEL_PARAMETER_MAP = {
    # Plugs
    "shellyplug": ["eco_mode", "max_power", "power_on_state", "led_status_disable", "cloud_enable", "mqtt_enable"],
    "shellyplug-s": ["eco_mode", "max_power", "power_on_state", "led_status_disable", "cloud_enable", "mqtt_enable"],
    "shellyplug-us": ["eco_mode", "max_power", "power_on_state", "led_status_disable", "cloud_enable", "mqtt_enable"],
    "shellyplus1pm": ["eco_mode", "max_power", "power_on_state", "led_status_disable", "cloud_enable", "mqtt_enable"],
    "shellypro1pm": ["eco_mode", "max_power", "power_on_state", "led_status_disable", "cloud_enable", "mqtt_enable"],
    
    # Relays
    "shelly1": ["power_on_state", "auto_on", "auto_off", "led_status_disable", "cloud_enable", "mqtt_enable"],
    "shelly1pm": ["eco_mode", "max_power", "power_on_state", "auto_on", "auto_off", "led_status_disable", "cloud_enable", "mqtt_enable"],
    "shellyplus1": ["power_on_state", "auto_on", "auto_off", "led_status_disable", "cloud_enable", "mqtt_enable"],
    "shellyplus2pm": ["eco_mode", "max_power", "power_on_state", "auto_on", "auto_off", "led_status_disable", "cloud_enable", "mqtt_enable"],
    
    # Sensors
    "shellyht": ["temperature_threshold", "humidity_threshold", "temperature_unit", "cloud_enable", "mqtt_enable"],
    "shellyflood": ["temperature_threshold", "cloud_enable", "mqtt_enable"],
    
    # By device ID prefix (exact matches from debug logs)
    "shelly1pmmini-348518e03ae0": ["eco_mode", "max_power"],
    "shellyplus2pm-b0a73248b180": ["eco_mode", "max_power"],
    
    # By device model (exact matches from debug logs)
    "SNSW-001P8EU": ["eco_mode", "max_power"],  # Plus1PMMini model
    "SNSW-102P16EU": ["eco_mode", "max_power"],  # Plus2PM model
    
    # By MAC prefix (Plus1PMMini devices)
    "348518E03AE0": ["eco_mode", "max_power"],  # Plus1PMMini device
    "B0A73248B180": ["eco_mode", "max_power"],  # Plus2PM device
    "E868E7EA6333": ["eco_mode", "max_power"],  # SHPLG-S device
    "C82B9611458F": ["eco_mode", "max_power"],  # SHSW-1 device
    
    # By device ID prefix
    "shelly1pmmini": ["eco_mode", "max_power"],
    "shellyplus2pm": ["eco_mode", "max_power"],
    "shellyplg-s": ["eco_mode", "max_power"],
    
    # Default parameters for all devices
    "default": ["power_on_state", "led_status_disable", "cloud_enable", "mqtt_enable"]
}


def get_parameters_for_model(model: str) -> Dict[str, ParameterDefinition]:
    """
    Get parameter definitions for a specific model.
    
    Args:
        model: Device model name or prefix
    
    Returns:
        Dictionary of parameter definitions by name
    """
    if not model:
        logger.warning("No model provided, using default parameters")
        model = "default"
    
    # Try to find a direct match first
    if model in MODEL_PARAMETER_MAP:
        parameter_names = MODEL_PARAMETER_MAP[model]
        return {name: COMMON_PARAMETERS[name] for name in parameter_names if name in COMMON_PARAMETERS}
    
    # Check if this is a MAC address match
    for mac_prefix in [key for key in MODEL_PARAMETER_MAP.keys() if len(key) == 12 and all(c in "0123456789ABCDEF" for c in key)]:
        if model.upper().replace(":", "").replace("-", "").startswith(mac_prefix):
            parameter_names = MODEL_PARAMETER_MAP[mac_prefix]
            return {name: COMMON_PARAMETERS[name] for name in parameter_names if name in COMMON_PARAMETERS}
    
    # Try matching by prefix
    matching_prefix = None
    for prefix in MODEL_PARAMETER_MAP.keys():
        # Skip MAC address keys (they're 12 chars of hex)
        if len(prefix) == 12 and all(c in "0123456789ABCDEF" for c in prefix):
            continue
            
        if model.lower().startswith(prefix.lower()):
            matching_prefix = prefix
            break
    
    # Use default if no match found
    if matching_prefix is None:
        logger.debug(f"No parameter mapping found for model '{model}', using default")
        matching_prefix = "default"
    
    # Get parameter names for the model
    parameter_names = MODEL_PARAMETER_MAP[matching_prefix]
    
    # Return parameter definitions
    return {name: COMMON_PARAMETERS[name] for name in parameter_names if name in COMMON_PARAMETERS} 