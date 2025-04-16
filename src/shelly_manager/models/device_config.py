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
        """Get device configuration based on raw model, type, and app"""
        logger = get_logger(__name__)
        
        # Normalize inputs
        raw_model = raw_model.upper() if raw_model else ""
        raw_type = raw_type.upper() if raw_type else ""
        raw_app = raw_app.lower() if raw_app else ""
        
        logger.debug(f"Matching device: model={raw_model}, type={raw_type}, app={raw_app}, gen={generation}")
        
        # Get the appropriate device dictionary based on generation
        devices = {
            "gen1": self.gen1_devices,
            "gen2": self.gen2_devices,
            "gen3": self.gen3_devices,
            "gen4": self.gen4_devices,
        }.get(generation, {})
        
        # Try direct model match first (most reliable)
        if raw_model:
            for device_id, config in devices.items():
                if device_id.upper() == raw_model:
                    logger.debug(f"Matched device by model: {device_id}")
                    return config
            
        # For Gen1, try matching by raw_type (backward compatibility)
        if generation == "gen1" and raw_type:
            for device_id, config in devices.items():
                if device_id.upper() in raw_type:
                    logger.debug(f"Matched Gen1 device by type: {device_id}")
                    return config
                
        # As last resort, try matching by app
        if raw_app:
            # Try exact match
            for device_id, config in devices.items():
                if device_id.lower() == raw_app:
                    logger.debug(f"Matched device by app: {device_id}")
                    return config
            
            # Try partial match
            for device_id, config in devices.items():
                if device_id.lower() in raw_app or raw_app in device_id.lower():
                    logger.debug(f"Matched device by partial app: {device_id}")
                    return config
        
        logger.debug(f"No device match found for gen={generation}, model={raw_model}, type={raw_type}, app={raw_app}")
        return None

# Create a global instance
device_config_manager = DeviceConfigManager() 