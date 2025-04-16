"""Parameter mapping between different device generations."""

import os
import yaml
from typing import Dict, List, Any, Optional, Set
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
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
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    enum_values: Optional[List[Any]] = None
    unit: Optional[str] = None
    group: Optional[str] = None
    
    # Generation-specific endpoints
    gen1_endpoint: Optional[str] = None
    gen1_property: Optional[str] = None
    gen2_method: Optional[str] = None
    gen2_component: Optional[str] = None
    gen2_property: Optional[str] = None
    requires_restart: bool = False
    
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


class ParameterManager:
    """
    Manages parameter definitions and mappings between device generations.
    
    This class loads parameter definitions from configuration and provides
    methods to access and convert parameters between different formats.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Singleton implementation."""
        if cls._instance is None:
            cls._instance = super(ParameterManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the parameter manager."""
        if ParameterManager._initialized:
            return
            
        self.parameter_definitions = {}
        self.common_parameter_groups = {}
        self.gen1_to_standard = {}
        self.standard_to_gen1 = {}
        
        self._load_parameter_mappings()
        ParameterManager._initialized = True
    
    def _load_parameter_mappings(self):
        """Load parameter mappings from configuration file."""
        mapping_file = Path("config/parameter_mappings.yaml")
        
        # Create default mapping file if it doesn't exist
        if not mapping_file.exists():
            logger.info(f"Creating default parameter mappings file at {mapping_file}")
            self._create_default_mappings(mapping_file)
        
        try:
            with open(mapping_file, 'r') as f:
                data = yaml.safe_load(f)
                
            if not data:
                logger.warning("Empty parameter mappings file, using defaults")
                return
                
            # Load parameter definitions
            if "parameters" in data:
                for param_name, param_data in data["parameters"].items():
                    self.parameter_definitions[param_name] = self._create_parameter_definition(
                        param_name, param_data
                    )
            
            # Load common parameter groups
            if "common_parameter_groups" in data:
                self.common_parameter_groups = data["common_parameter_groups"]
            
            # Load Gen1 to standard mappings
            if "gen1_to_standard" in data:
                self.gen1_to_standard = data["gen1_to_standard"]
                # Create reverse mapping
                self.standard_to_gen1 = {v: k for k, v in self.gen1_to_standard.items()}
            
            logger.info(f"Loaded {len(self.parameter_definitions)} parameter definitions from configuration")
            
        except Exception as e:
            logger.error(f"Error loading parameter mappings: {str(e)}")
    
    def _create_parameter_definition(self, name: str, data: Dict[str, Any]) -> ParameterDefinition:
        """Create a parameter definition from configuration data."""
        param_type_str = data.get("type", "string").lower()
        param_type = ParameterType.STRING
        
        # Map string type to ParameterType enum
        for pt in ParameterType:
            if pt.value == param_type_str:
                param_type = pt
                break
        
        return ParameterDefinition(
            name=name,
            display_name=data.get("display_name", name),
            parameter_type=param_type,
            description=data.get("description", ""),
            read_only=data.get("read_only", False),
            default_value=data.get("default_value"),
            min_value=data.get("min_value"),
            max_value=data.get("max_value"),
            enum_values=data.get("enum_values"),
            unit=data.get("unit"),
            group=data.get("group"),
            gen1_endpoint=data.get("gen1", {}).get("endpoint"),
            gen1_property=data.get("gen1", {}).get("property"),
            gen2_method=data.get("gen2", {}).get("method"),
            gen2_component=data.get("gen2", {}).get("component"),
            gen2_property=data.get("gen2", {}).get("property"),
            requires_restart=data.get("requires_restart", False)
        )
    
    def _create_default_mappings(self, file_path: Path):
        """Create a default parameter mappings file."""
        os.makedirs(file_path.parent, exist_ok=True)
        
        default_content = {
            "parameters": {
                "eco_mode": {
                    "display_name": "ECO Mode",
                    "description": "Energy saving mode",
                    "type": "boolean",
                    "group": "power",
                    "gen1": {"endpoint": "settings", "property": "eco_mode"},
                    "gen2": {"method": "Sys.SetConfig", "component": "device", "property": "eco_mode"}
                }
            },
            "common_parameter_groups": {
                "power": ["eco_mode"]
            },
            "gen1_to_standard": {
                "eco_mode_enabled": "eco_mode"
            }
        }
        
        try:
            with open(file_path, 'w') as f:
                yaml.dump(default_content, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            logger.error(f"Failed to create default parameter mappings file: {str(e)}")
    
    def get_parameter_definition(self, parameter_name: str) -> Optional[ParameterDefinition]:
        """Get a parameter definition by name."""
        return self.parameter_definitions.get(parameter_name)
    
    def get_all_parameter_definitions(self) -> Dict[str, ParameterDefinition]:
        """Get all parameter definitions."""
        return self.parameter_definitions
    
    def get_parameters_by_group(self, group_name: str) -> List[ParameterDefinition]:
        """Get all parameters in a specific group."""
        if group_name not in self.common_parameter_groups:
            return []
            
        param_names = self.common_parameter_groups[group_name]
        return [self.parameter_definitions[name] for name in param_names 
                if name in self.parameter_definitions]
    
    def get_all_common_parameters(self) -> List[ParameterDefinition]:
        """Get all common parameters across all groups."""
        result = []
        for group in self.common_parameter_groups.values():
            for param_name in group:
                if param_name in self.parameter_definitions and param_name not in [p.name for p in result]:
                    result.append(self.parameter_definitions[param_name])
        return result
    
    def to_gen1_parameter(self, parameter_name: str) -> str:
        """Convert a standard parameter name to Gen1 parameter name."""
        return self.standard_to_gen1.get(parameter_name, parameter_name)
    
    def to_standard_parameter(self, parameter_name: str) -> str:
        """Convert a Gen1 parameter name to standard parameter name."""
        return self.gen1_to_standard.get(parameter_name, parameter_name)
    
    def map_parameter_value(self, parameter_name: str, value: Any, to_gen1: bool = False) -> Any:
        """Map parameter value based on generation-specific formatting needs."""
        param_def = self.get_parameter_definition(parameter_name)
        if not param_def:
            return value
            
        if to_gen1:
            return param_def.format_value_for_gen1(value)
        else:
            return param_def.format_value_for_gen2(value)


# Create a singleton instance
parameter_manager = ParameterManager()


class ParameterMapper:
    """Legacy class for backward compatibility."""
    
    @classmethod
    def to_gen1_parameter(cls, parameter_name: str) -> str:
        """Convert a standard parameter name to Gen1 parameter name."""
        return parameter_manager.to_gen1_parameter(parameter_name)
    
    @classmethod
    def to_standard_parameter(cls, parameter_name: str) -> str:
        """Convert a Gen1 parameter name to standard parameter name."""
        return parameter_manager.to_standard_parameter(parameter_name)
    
    @staticmethod
    def map_parameter_value(parameter_name: str, value: Any, to_gen1: bool = False) -> Any:
        """Map parameter value based on generation-specific formatting needs."""
        return parameter_manager.map_parameter_value(parameter_name, value, to_gen1) 