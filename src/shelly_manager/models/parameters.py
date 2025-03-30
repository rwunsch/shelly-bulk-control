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
    )
}


# Map of model prefixes to available parameters
MODEL_PARAMETER_MAP = {
    # Plugs
    "shellyplug": ["eco_mode", "max_power"],
    "shellyplug-s": ["eco_mode", "max_power"],
    "shellyplug-us": ["eco_mode", "max_power"],
    "shellyplus1pm": ["eco_mode", "max_power"],
    "shellypro1pm": ["eco_mode", "max_power"],
    
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
    "shelly1": ["eco_mode", "max_power"],
    
    # Default parameters for all devices
    "default": ["eco_mode", "max_power"]  # Default to supporting both parameters
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