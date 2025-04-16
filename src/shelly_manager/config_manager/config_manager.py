import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional, List
from ..models.device import Device, DeviceGeneration

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Initialize the config manager"""
        self._session = aiohttp.ClientSession()

    async def stop(self):
        """Clean up resources"""
        if self._session:
            await self._session.close()

    async def get_device_settings(self, device: Device) -> Dict[str, Any]:
        """Get current settings from a device"""
        if not self._session:
            raise RuntimeError("ConfigManager not started")

        if device.generation == DeviceGeneration.GEN1:
            url = f"http://{device.ip_address}/settings"
        else:  # GEN2
            url = f"http://{device.ip_address}/rpc/Shelly.GetConfig"

        try:
            async with self._session.get(url) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logger.error(f"Error getting settings from {device.id} ({device.ip_address}): {str(e)}")
            return {}

    async def apply_settings(self, device: Device, settings: Dict[str, Any]) -> bool:
        """Apply settings to a device"""
        if not self._session:
            raise RuntimeError("ConfigManager not started")

        logger.debug(f"Applying settings to {device.id} ({device.ip_address}), generation: {device.generation}")
        logger.debug(f"Settings to apply: {settings}")

        try:
            # Get current settings before applying changes
            before_settings = await self.get_device_settings(device)
            logger.debug(f"Settings before change: {before_settings}")
            
            if device.generation == DeviceGeneration.GEN1:
                # For Gen1, we need to convert string values to appropriate types
                processed_settings = self._process_gen1_settings(settings)
                logger.debug(f"Processed Gen1 settings: {processed_settings}")
                
                # For Gen1 devices, first get current settings to verify supported keys
                logger.debug(f"Current Gen1 settings structure: {list(before_settings.keys())}")
                
                # Check if keys exist in current settings
                for key in processed_settings.keys():
                    if key not in before_settings and '.' not in key:
                        logger.warning(f"Key '{key}' not found in current settings for {device.id}")
                
                url = f"http://{device.ip_address}/settings"
                logger.debug(f"Sending POST request to {url}")
                
                async with self._session.post(url, json=processed_settings) as response:
                    response.raise_for_status()
                    response_text = await response.text()
                    logger.debug(f"Gen1 device response: {response_text}")
                    
                    # Wait a moment for the device to apply settings
                    await asyncio.sleep(1)
                    
                    # Get settings after change
                    after_settings = await self.get_device_settings(device)
                    
                    # Verify changes
                    success = self._verify_settings_changed(processed_settings, before_settings, after_settings)
                    
                    if success:
                        logger.info(f"Settings successfully verified for device {device.id}")
                    else:
                        logger.warning(f"Some settings may not have been applied correctly for device {device.id}")
                    
                    return success
            else:  # GEN2
                # Get current config structure to verify paths and handle nested settings
                logger.debug(f"Current Gen2 config structure: {list(before_settings.keys())}")
                
                # Process settings for Gen2
                processed_settings = self._process_gen2_settings(settings, before_settings)
                
                # For Gen2, settings need to be in {"config": settings} format
                request_data = {"config": processed_settings}
                logger.debug(f"Gen2 request data: {request_data}")
                
                url = f"http://{device.ip_address}/rpc/Shelly.SetConfig"
                logger.debug(f"Sending POST request to {url}")
                
                async with self._session.post(url, json=request_data) as response:
                    response.raise_for_status()
                    response_json = await response.json()
                    logger.debug(f"Gen2 device response: {response_json}")
                    
                    # Check if there's an error in the response
                    if isinstance(response_json, dict) and response_json.get('error'):
                        logger.error(f"Error from Gen2 device: {response_json['error']}")
                        return False
                    
                    # Wait a moment for the device to apply settings
                    await asyncio.sleep(1)
                    
                    # Get settings after change
                    after_settings = await self.get_device_settings(device)
                    
                    # Verify changes for Gen2
                    success = self._verify_gen2_settings_changed(processed_settings, before_settings, after_settings)
                    
                    if success:
                        logger.info(f"Settings successfully verified for device {device.id}")
                    else:
                        logger.warning(f"Some settings may not have been applied correctly for device {device.id}")
                    
                    return success
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error applying settings to {device.id} ({device.ip_address}): {e.status}, {e.message}")
            return False
        except Exception as e:
            logger.error(f"Error applying settings to {device.id} ({device.ip_address}): {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return False

    def _process_gen1_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Process settings for Gen1 devices - convert string values to appropriate types"""
        result = {}
        for key, value in settings.items():
            if not isinstance(value, str):
                result[key] = value
                continue
                
            # Convert string 'true'/'false' to boolean
            if value.lower() == 'true':
                result[key] = True
            elif value.lower() == 'false':
                result[key] = False
            # Try to convert to number if it looks like one
            elif value.isdigit():
                result[key] = int(value)
            elif self._is_float(value):
                result[key] = float(value)
            else:
                result[key] = value
        return result
    
    def _process_gen2_settings(self, settings: Dict[str, Any], current_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process settings for Gen2 devices
        - Convert string values to appropriate types
        - Handle nested paths with dot notation (e.g., "wifi.sta.ssid")
        """
        result = {}
        for key, value in settings.items():
            # Handle nested paths with dot notation
            if "." in key:
                # Split by dots to get nested keys
                parts = key.split(".")
                
                # Start with the result dict
                current = result
                
                # Navigate through all but the last key, creating dictionaries as needed
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                    current = current[part]
                
                # Set the value at the last key
                value_to_set = self._convert_value_type(value)
                current[parts[-1]] = value_to_set
                logger.debug(f"Set nested key {key} to {value_to_set}")
            else:
                # Regular non-nested key
                result[key] = self._convert_value_type(value)
                
        return result
        
    def _convert_value_type(self, value: Any) -> Any:
        """Convert string values to appropriate types for both Gen1 and Gen2 devices"""
        if not isinstance(value, str):
            return value
            
        # Convert string 'true'/'false' to boolean
        if value.lower() == 'true':
            return True
        elif value.lower() == 'false':
            return False
        # Try to convert to number if it looks like one
        elif value.isdigit():
            return int(value)
        elif self._is_float(value):
            return float(value)
        else:
            return value
    
    def _is_float(self, value: str) -> bool:
        """Check if a string can be converted to float"""
        try:
            float(value)
            return True
        except ValueError:
            return False

    def _verify_settings_changed(self, settings_to_apply: Dict[str, Any], 
                               before_settings: Dict[str, Any], 
                               after_settings: Dict[str, Any]) -> bool:
        """Verify that settings were correctly applied for GEN1 devices"""
        all_verified = True
        
        for key, expected_value in settings_to_apply.items():
            # Check if the setting exists in the after settings
            if key not in after_settings:
                logger.warning(f"Setting '{key}' does not exist in device response after update")
                all_verified = False
                continue
                
            actual_value = after_settings[key]
            original_value = before_settings.get(key)
            
            # Check if the value was actually changed to what we expected
            if actual_value != expected_value:
                logger.warning(f"Setting '{key}' was not updated correctly. Expected: {expected_value}, Actual: {actual_value}")
                all_verified = False
            else:
                logger.debug(f"Verified setting '{key}' changed from {original_value} to {actual_value}")
                
        return all_verified
        
    def _verify_gen2_settings_changed(self, settings_to_apply: Dict[str, Any], 
                                    before_settings: Dict[str, Any], 
                                    after_settings: Dict[str, Any]) -> bool:
        """Verify that settings were correctly applied for GEN2 devices"""
        all_verified = True
        
        # For Gen2 we need to handle both direct settings and nested ones
        for key, expected_value in settings_to_apply.items():
            if isinstance(expected_value, dict):
                # Handle nested dictionary
                for nested_key, nested_value in self._flatten_dict(expected_value, parent_key=key):
                    verified = self._verify_gen2_setting(nested_key, nested_value, 
                                                       before_settings, after_settings)
                    all_verified = all_verified and verified
            else:
                # Handle direct key
                verified = self._verify_gen2_setting(key, expected_value, 
                                                   before_settings, after_settings)
                all_verified = all_verified and verified
                
        return all_verified
        
    def _verify_gen2_setting(self, key: str, expected_value: Any, 
                           before_settings: Dict[str, Any], 
                           after_settings: Dict[str, Any]) -> bool:
        """Verify a single Gen2 setting by navigating the nested structure"""
        # Split the key path for nested settings
        key_parts = key.split('.')
        
        # Navigate to the actual setting in both before and after
        before_value = before_settings
        after_value = after_settings
        
        # Try to navigate to the deepest level of the setting
        try:
            for part in key_parts:
                if part in before_value:
                    before_value = before_value[part]
                else:
                    before_value = None
                    break
                    
            for part in key_parts:
                if part in after_value:
                    after_value = after_value[part]
                else:
                    logger.warning(f"Setting path '{key}' not found in device after update")
                    return False
                    
            # Check if the value was actually changed to what we expected
            if after_value != expected_value:
                logger.warning(f"Setting '{key}' was not updated correctly. Expected: {expected_value}, Actual: {after_value}")
                return False
            else:
                logger.debug(f"Verified setting '{key}' changed from {before_value} to {after_value}")
                return True
                
        except (KeyError, TypeError) as e:
            logger.warning(f"Error accessing nested setting '{key}': {str(e)}")
            return False
    
    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = '') -> List[tuple]:
        """Flatten a nested dictionary into (key, value) pairs with dot notation keys"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key))
            else:
                items.append((new_key, v))
                
        return items

    async def apply_bulk_settings(self, devices: List[Device], settings: Dict[str, Any]) -> Dict[str, bool]:
        """Apply settings to multiple devices in parallel"""
        tasks = [self.apply_settings(device, settings) for device in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            device.id: isinstance(result, bool) and result 
            for device, result in zip(devices, results)
        } 