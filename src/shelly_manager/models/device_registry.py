"""
Device registry for managing device objects and loading from files.
"""
from typing import Dict, Optional, List
import os
import yaml
from pathlib import Path
import logging

from ..utils.logging import get_logger
from .device import Device, DeviceGeneration

# Get logger for this module
logger = get_logger(__name__)

class DeviceRegistry:
    """
    Registry for Shelly devices.
    
    This class manages a cache of device objects and provides methods
    to load devices from files when requested.
    """
    
    def __init__(self, devices_dir: str = "data/devices"):
        """
        Initialize the device registry.
        
        Args:
            devices_dir: Directory where device YAML files are stored
        """
        self.devices_dir = Path(devices_dir)
        self.devices: Dict[str, Device] = {}
        logger.debug(f"Initialized DeviceRegistry with directory: {self.devices_dir}")
    
    def get_device(self, device_id: str) -> Optional[Device]:
        """
        Get a device by ID. First checks the cache, then tries to load from file.
        
        Args:
            device_id: ID of the device to get
            
        Returns:
            Device object if found, None otherwise
        """
        # Check if device is already loaded
        if device_id in self.devices:
            return self.devices[device_id]
        
        # Try to load device from file
        device = self._load_device_from_file(device_id)
        if device:
            # Store in cache for future requests
            self.devices[device_id] = device
            return device
        
        return None
    
    def get_devices(self, device_ids: List[str]) -> List[Device]:
        """
        Get multiple devices by their IDs.
        
        Args:
            device_ids: List of device IDs to get
            
        Returns:
            List of found devices (may be shorter than input list if some devices aren't found)
        """
        result = []
        for device_id in device_ids:
            device = self.get_device(device_id)
            if device:
                result.append(device)
            else:
                logger.warning(f"Device not found: {device_id}")
        
        return result
    
    def add_device(self, device: Device) -> None:
        """
        Add a device to the registry.
        
        Args:
            device: Device to add
        """
        self.devices[device.id] = device
    
    def save_device(self, device: Device) -> bool:
        """
        Save a device to its file and update the registry.
        
        Args:
            device: Device to save
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Make sure the directory exists
            os.makedirs(self.devices_dir, exist_ok=True)
            
            # Convert device to dictionary
            device_data = device.to_dict()
            
            # Determine the display type based on device info
            if device.generation == DeviceGeneration.GEN1:
                display_type = device.raw_type or "unknown"
            elif device.generation == DeviceGeneration.GEN2:
                display_type = device.raw_app or "ShellyPlus" 
            elif device.generation == DeviceGeneration.GEN3:
                display_type = device.raw_app or "ShellyPro"
            else:
                display_type = "unknown"
            
            # Format MAC address (uppercase, no colons)
            mac_address = device.mac_address.replace(":", "").upper() if device.mac_address else "unknown"
            
            # Create filename with format "<type>_<mac-address>.yaml"
            filename = f"{display_type}_{mac_address}.yaml"
            filepath = self.devices_dir / filename
            
            # Save to file
            with open(filepath, 'w') as f:
                yaml.dump(device_data, f, default_flow_style=False)
            
            # Update registry
            self.devices[device.id] = device
            
            logger.debug(f"Saved device {device.id} to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save device {device.id}: {e}")
            return False
    
    def _load_device_from_file(self, device_id: str) -> Optional[Device]:
        """
        Load a device from its file.
        
        Args:
            device_id: ID of the device to load
            
        Returns:
            Device object if found, None otherwise
        """
        # Standardize MAC address format (uppercase, no colons)
        mac_address = device_id.replace(":", "").upper()
        
        # Check if the devices directory exists
        if not self.devices_dir.exists():
            logger.warning(f"Devices directory {self.devices_dir} does not exist")
            return None
        
        # Look for files matching the device ID
        device_file = None
        
        # First try to find by exact MAC address match
        for file_path in self.devices_dir.glob("*_*.yaml"):
            # Extract the MAC part from the filename pattern <type>_<mac>.yaml
            file_name = file_path.name
            if "_" in file_name:
                file_mac = file_name.split("_")[1].split(".")[0].upper()
                # Check if this file's MAC matches our device
                if file_mac == mac_address:
                    device_file = file_path
                    break
        
        if not device_file:
            # Try looking for files containing the MAC address
            for file_path in self.devices_dir.glob("*.yaml"):
                if mac_address in file_path.name.upper():
                    device_file = file_path
                    break
        
        if not device_file:
            logger.warning(f"No device file found for device_id: {device_id}")
            return None
        
        logger.debug(f"Found device file: {device_file}")
        
        try:
            # Load device data from YAML file
            with open(device_file, 'r') as f:
                device_data = yaml.safe_load(f)
            
            if device_data:
                # Clean up the data to match Device constructor parameters
                # The existing files might have fields that aren't in the Device constructor
                
                # Make a clean copy without unwanted fields
                clean_data = {}
                
                # Map field names that need conversion
                # Some fields might be named differently in the file vs. the Device class
                field_mapping = {
                    # Add mappings if needed for field name differences
                    "device_name": "name"  # example mapping
                }
                
                # Known fields in Device.__init__
                device_fields = [
                    "id", "name", "generation", "ip_address", "mac_address", 
                    "firmware_version", "status", "discovery_method", "hostname",
                    "timezone", "location", "wifi_ssid", "cloud_enabled", 
                    "cloud_connected", "mqtt_enabled", "mqtt_server", 
                    "eco_mode_enabled", "model", "slot", "auth_enabled", 
                    "auth_domain", "fw_id", "raw_type", "raw_model", "raw_app", 
                    "last_seen", "has_update"
                ]
                
                # Copy only valid fields to clean_data
                for field in device_fields:
                    mapped_field = field_mapping.get(field, field)
                    if mapped_field in device_data:
                        clean_data[field] = device_data[mapped_field]
                
                # Ensure required fields exist
                if "id" not in clean_data and "mac_address" in clean_data:
                    # Generate an ID from MAC if missing
                    mac = clean_data["mac_address"].replace(":", "").lower()
                    if device_data.get("generation") == "gen1":
                        clean_data["id"] = mac
                    else:
                        prefix = "shelly"
                        if "raw_app" in clean_data and clean_data["raw_app"]:
                            prefix = clean_data["raw_app"].lower()
                        clean_data["id"] = f"{prefix}-{mac}"
                
                # Convert the data to a Device object
                return Device.from_dict(clean_data)
            else:
                logger.warning(f"Empty device data in file: {device_file}")
                return None
                
        except Exception as e:
            logger.error(f"Error loading device from file {device_file}: {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
            
    def load_all_devices(self) -> List[Device]:
        """
        Load all devices from the devices directory.
        
        Returns:
            List of loaded devices
        """
        if not self.devices_dir.exists():
            logger.warning(f"Devices directory {self.devices_dir} does not exist")
            return []
        
        loaded_devices = []
        
        # Process all YAML files in the directory
        for file_path in self.devices_dir.glob("*.yaml"):
            try:
                with open(file_path, 'r') as f:
                    device_data = yaml.safe_load(f)
                
                if device_data:
                    # Clean up the data to match Device constructor parameters
                    # The existing files might have fields that aren't in the Device constructor
                    
                    # Make a clean copy without unwanted fields
                    clean_data = {}
                    
                    # Map field names that need conversion
                    # Some fields might be named differently in the file vs. the Device class
                    field_mapping = {
                        # Add mappings if needed for field name differences
                        "device_name": "name"  # example mapping
                    }
                    
                    # Known fields in Device.__init__
                    device_fields = [
                        "id", "name", "generation", "ip_address", "mac_address", 
                        "firmware_version", "status", "discovery_method", "hostname",
                        "timezone", "location", "wifi_ssid", "cloud_enabled", 
                        "cloud_connected", "mqtt_enabled", "mqtt_server", 
                        "eco_mode_enabled", "model", "slot", "auth_enabled", 
                        "auth_domain", "fw_id", "raw_type", "raw_model", "raw_app", 
                        "last_seen", "has_update"
                    ]
                    
                    # Copy only valid fields to clean_data
                    for field in device_fields:
                        mapped_field = field_mapping.get(field, field)
                        if mapped_field in device_data:
                            clean_data[field] = device_data[mapped_field]
                    
                    # Ensure required fields exist
                    if "id" not in clean_data and "mac_address" in clean_data:
                        # Generate an ID from MAC if missing
                        mac = clean_data["mac_address"].replace(":", "").lower()
                        if device_data.get("generation") == "gen1":
                            clean_data["id"] = mac
                        else:
                            prefix = "shelly"
                            if "raw_app" in clean_data and clean_data["raw_app"]:
                                prefix = clean_data["raw_app"].lower()
                            clean_data["id"] = f"{prefix}-{mac}"
                            
                    if "id" in clean_data:
                        # Create Device object
                        device = Device.from_dict(clean_data)
                        self.devices[device.id] = device
                        loaded_devices.append(device)
                        logger.debug(f"Loaded device {device.id} from {file_path}")
                    else:
                        logger.warning(f"Invalid device data (missing ID) in file: {file_path}")
                else:
                    logger.warning(f"Invalid device data in file: {file_path}")
            
            except Exception as e:
                logger.error(f"Failed to load device from {file_path}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        
        logger.info(f"Loaded {len(loaded_devices)} devices from {self.devices_dir}")
        return loaded_devices

    def get_device_by_ip(self, ip_address: str) -> Optional[Device]:
        """
        Find a device by IP address.
        
        Args:
            ip_address: IP address to search for
            
        Returns:
            Device if found, None otherwise
        """
        self.load_all_devices()
        for device in self.devices.values():
            if device.ip_address == ip_address:
                return device
        return None

# Create a global instance of the registry
device_registry = DeviceRegistry() 