"""Parameter mapping between different device generations."""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from ..utils.logging import get_logger

logger = get_logger(__name__)

class ParameterMapper:
    """Maps parameters between different device generations."""
    
    _instance = None
    _mappings_loaded = False
    _standard_to_gen1 = {}  # Gen2+ -> Gen1 mapping
    _gen1_to_standard = {}  # Gen1 -> Gen2+ mapping
    
    def __new__(cls):
        """Singleton implementation to ensure mappings are loaded only once."""
        if cls._instance is None:
            cls._instance = super(ParameterMapper, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the parameter mapper and load mappings."""
        if not ParameterMapper._mappings_loaded:
            self._load_mappings()
            ParameterMapper._mappings_loaded = True
    
    def _load_mappings(self):
        """Load parameter mappings from configuration file."""
        mapping_file = Path("config/parameter_mappings.yaml")
        
        # Create default mapping file if it doesn't exist
        if not mapping_file.exists():
            logger.info(f"Creating default parameter mappings file at {mapping_file}")
            self._create_default_mappings(mapping_file)
        
        try:
            with open(mapping_file, 'r') as f:
                data = yaml.safe_load(f)
                
            if not data or "mappings" not in data:
                logger.warning("Invalid parameter mappings file, using defaults")
                ParameterMapper._standard_to_gen1 = {"eco_mode": "eco_mode_enabled"}
            else:
                ParameterMapper._standard_to_gen1 = data["mappings"]
                
            # Create the reverse mapping automatically
            ParameterMapper._gen1_to_standard = {v: k for k, v in ParameterMapper._standard_to_gen1.items()}
            
            logger.info(f"Loaded {len(ParameterMapper._standard_to_gen1)} parameter mappings")
            logger.debug(f"Standard to Gen1 mappings: {ParameterMapper._standard_to_gen1}")
            
        except Exception as e:
            logger.error(f"Error loading parameter mappings: {str(e)}")
            # Fall back to default mapping
            ParameterMapper._standard_to_gen1 = {"eco_mode": "eco_mode_enabled"}
            ParameterMapper._gen1_to_standard = {"eco_mode_enabled": "eco_mode"}
    
    def _create_default_mappings(self, file_path: Path):
        """Create a default parameter mappings file."""
        os.makedirs(file_path.parent, exist_ok=True)
        
        default_content = {
            "mappings": {
                "eco_mode": "eco_mode_enabled"
            }
        }
        
        try:
            with open(file_path, 'w') as f:
                yaml.dump(default_content, f, default_flow_style=False, sort_keys=False)
        except Exception as e:
            logger.error(f"Failed to create default parameter mappings file: {str(e)}")
    
    @classmethod
    def to_gen1_parameter(cls, parameter_name: str) -> str:
        """
        Convert a standard parameter name to Gen1 parameter name.
        Used when forming API requests to Gen1 devices.
        
        Args:
            parameter_name: Standard parameter name (Gen2+ format)
            
        Returns:
            Gen1 parameter name or original if no mapping exists
        """
        if not cls._mappings_loaded:
            cls()  # Initialize singleton to load mappings
            
        return cls._standard_to_gen1.get(parameter_name, parameter_name)
    
    @classmethod
    def to_standard_parameter(cls, parameter_name: str) -> str:
        """
        Convert a Gen1 parameter name to standard parameter name.
        Used during capability discovery to standardize parameter names.
        
        Args:
            parameter_name: Gen1 parameter name
            
        Returns:
            Standard parameter name (Gen2+ format) or original if no mapping exists
        """
        if not cls._mappings_loaded:
            cls()  # Initialize singleton to load mappings
            
        return cls._gen1_to_standard.get(parameter_name, parameter_name)
    
    @staticmethod
    def map_parameter_value(parameter_name: str, value: Any, to_gen1: bool = False) -> Any:
        """
        Map parameter value based on generation-specific formatting needs.
        
        Args:
            parameter_name: Parameter name
            value: Parameter value
            to_gen1: Whether to convert to Gen1 format
            
        Returns:
            Mapped value
        """
        # Some parameters might need special value handling
        # For now, we just pass through the values as-is
        return value 