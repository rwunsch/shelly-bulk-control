from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import yaml
from pathlib import Path
from ..utils.logging import get_logger

@dataclass
class DeviceTypeConfig:
    """Configuration for a device type"""
    name: str
    type: str
    generation: str
    num_outputs: int
    num_meters: int
    max_power: Optional[int] = None
    features: List[str] = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = []

class DeviceConfigManager:
    """Manages device configurations from YAML"""
    
    def __init__(self, config_file: str = "config/device_types.yaml"):
        self.config_file = config_file
        self.gen1_devices: Dict[str, DeviceTypeConfig] = {}
        self.gen2_devices: Dict[str, DeviceTypeConfig] = {}
        self.gen3_devices: Dict[str, DeviceTypeConfig] = {}
        self.gen4_devices: Dict[str, DeviceTypeConfig] = {}
        self._load_config()
    
    def _load_config(self):
        """Load device configurations from YAML file"""
        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Load Gen1 devices
            for device_id, device_data in config.get('gen1_devices', {}).items():
                self.gen1_devices[device_id] = DeviceTypeConfig(
                    name=device_data['name'],
                    type=device_data['type'],
                    generation='gen1',
                    num_outputs=device_data['num_outputs'],
                    num_meters=device_data['num_meters'],
                    max_power=device_data.get('max_power'),
                    features=device_data['features']
                )
            
            # Load Gen2 devices
            for device_id, device_data in config.get('gen2_devices', {}).items():
                self.gen2_devices[device_id] = DeviceTypeConfig(
                    name=device_data['name'],
                    type=device_data['type'],
                    generation='gen2',
                    num_outputs=device_data['num_outputs'],
                    num_meters=device_data['num_meters'],
                    max_power=device_data.get('max_power'),
                    features=device_data['features']
                )
            
            # Load Gen3 devices
            for device_id, device_data in config.get('gen3_devices', {}).items():
                self.gen3_devices[device_id] = DeviceTypeConfig(
                    name=device_data['name'],
                    type=device_data['type'],
                    generation='gen3',
                    num_outputs=device_data['num_outputs'],
                    num_meters=device_data['num_meters'],
                    max_power=device_data.get('max_power'),
                    features=device_data['features']
                )
            
            # Load Gen4 devices (if any exist)
            gen4_devices = config.get('gen4_devices', {})
            if isinstance(gen4_devices, dict):  # Only process if it's a dictionary
                for device_id, device_data in gen4_devices.items():
                    self.gen4_devices[device_id] = DeviceTypeConfig(
                        name=device_data['name'],
                        type=device_data['type'],
                        generation='gen4',
                        num_outputs=device_data['num_outputs'],
                        num_meters=device_data['num_meters'],
                        max_power=device_data.get('max_power'),
                        features=device_data['features']
                    )
        except Exception as e:
            raise RuntimeError(f"Failed to load device configurations: {str(e)}")
    
    def get_device_config(self, raw_type: str, raw_app: str, generation: str, raw_model: str = None) -> Optional[DeviceTypeConfig]:
        """Get device configuration based on raw type and app"""
        # Convert to lowercase for comparison
        raw_type = raw_type.lower() if raw_type else ""
        raw_app = raw_app.lower() if raw_app else ""
        raw_model = raw_model.lower() if raw_model else ""
        
        logger = get_logger(__name__)
        logger.debug(f"Matching device type: gen={generation}, raw_type={raw_type}, raw_app={raw_app}, raw_model={raw_model}")
        
        # Special case for Gen1 devices - match by raw_type
        if generation == "gen1":
            for device_id, device_config in self.gen1_devices.items():
                if raw_type and device_id.lower() in raw_type.lower():
                    logger.debug(f"Matched Gen1 device: {device_id}")
                    return device_config
            logger.debug(f"No Gen1 device match found for raw_type={raw_type}")
            return None
        
        # For all other generations (Gen2+), match by app field
        device_types = {
            "gen2": self.gen2_devices,
            "gen3": self.gen3_devices,
            "gen4": self.gen4_devices
        }.get(generation, {})
        
        logger.debug(f"Available {generation} devices: {list(device_types.keys())}")
        
        # First try exact match by app field (case-insensitive)
        if raw_app:
            for device_id, device_config in device_types.items():
                # Case-insensitive comparison
                logger.debug(f"Comparing {device_id.lower()} with {raw_app.lower()}")
                if device_id.lower() == raw_app.lower():
                    logger.debug(f"Matched {generation} device by app (exact): {device_id}")
                    return device_config
            
            # If no exact match, try more specific matches first (longer device IDs)
            # Sort by length descending so we check longer names first (e.g., Plus1PM before Plus1)
            sorted_device_ids = sorted(device_types.keys(), key=len, reverse=True)
            
            for device_id in sorted_device_ids:
                device_config = device_types[device_id]
                # Try to see if the app name contains the device ID
                logger.debug(f"Trying partial match (specific-first) - {device_id.lower()} vs {raw_app.lower()}")
                if device_id.lower() in raw_app.lower():
                    logger.debug(f"Matched {generation} device by app (specific-first): {device_id} - {raw_app}")
                    return device_config
            
            # If still no match, try contains match in either direction
            for device_id, device_config in device_types.items():
                logger.debug(f"Trying fallback partial match - {device_id.lower()} vs {raw_app.lower()}")
                if raw_app.lower() in device_id.lower():
                    logger.debug(f"Matched {generation} device by app (fallback): {device_id} - {raw_app}")
                    return device_config
        
        # Additional mapping for special cases - adding common name mappings
        app_mappings = {
            # Gen2 mappings
            "plugs": "PlusPlugS",     # Shelly Plus Plug S
            "plug": "PlusPlugS",      # Alternate name
            "plus1pm": "Plus1PM",     # Shelly Plus 1PM
            "plus1": "Plus1",         # Shelly Plus 1 (without PM)
            "plus2pm": "Plus2PM",     # Shelly Plus 2PM
            "plus2": "Plus2",         # Shelly Plus 2 (without PM)
            "plus4pm": "Plus4PM",     # Shelly Plus 4PM
            "plus4": "Plus4",         # Shelly Plus 4 (without PM)
            
            # Gen3 mappings
            "mini1pmg3": "Mini1PMG3", # Shelly Mini 1PM Gen3
            "minig3": "Mini1PMG3",    # Alternate name
        }
        
        logger.debug(f"Checking app mappings for {raw_app}")
        if raw_app and raw_app.lower() in app_mappings:
            mapped_device_id = app_mappings[raw_app.lower()]
            logger.debug(f"Found app mapping: {raw_app} -> {mapped_device_id}")
            if mapped_device_id in device_types:
                logger.debug(f"Matched {generation} device through app mapping: {raw_app} -> {mapped_device_id}")
                return device_types[mapped_device_id]
        
        # If still no match, try model-based matching as last resort
        # This is useful for devices that don't have a clear app value that matches our device types
        model_mappings = {
            # Gen2 model mappings
            "snpl-00112eu": "PlusPlugS",  # Shelly Plus Plug S
            "snsw-001p16eu": "Plus1PM",   # Shelly Plus 1PM
            
            # Gen3 model mappings
            "s3sw-001p8eu": "Mini1PMG3",  # Shelly Mini 1PM Gen3
        }
        
        # Try to match using raw_model if available
        logger.debug(f"Checking model mappings for {raw_model}")
        for model_pattern, device_id in model_mappings.items():
            logger.debug(f"Comparing model pattern {model_pattern} with {raw_model}")
            if model_pattern in raw_model:
                if device_id in device_types:
                    logger.debug(f"Matched {generation} device through model mapping: {raw_model} -> {device_id}")
                    return device_types[device_id]
        
        logger.debug(f"No {generation} device match found for raw_app={raw_app}, raw_model={raw_model}")
        return None

# Create a global instance
device_config_manager = DeviceConfigManager() 