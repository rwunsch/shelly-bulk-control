import aiohttp
import asyncio
import logging
import json
from typing import Dict, Any, Optional, List
from ..models.device import Device, DeviceGeneration
import os
from pathlib import Path

logger = logging.getLogger(__name__)

class Config:
    """Simple configuration class to hold paths to config files"""
    def __init__(self, config_file: Optional[Path] = None, devices_file: Optional[Path] = None):
        self.config_file = config_file or Path("config/config.yaml")
        self.devices_file = devices_file or Path("config/devices.yaml")
        logger.debug(f"Config initialized with config_file={self.config_file}, devices_file={self.devices_file}")

class ConfigManager:
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        logger.debug("ConfigManager initialized")

    async def start(self):
        """Initialize the config manager"""
        self._session = aiohttp.ClientSession()
        logger.debug("ConfigManager session started")

    async def stop(self):
        """Clean up resources"""
        if self._session:
            await self._session.close()
            logger.debug("ConfigManager session closed")

    async def get_device_settings(self, device: Device) -> Dict[str, Any]:
        """Get current settings from a device"""
        if not self._session:
            error_msg = "ConfigManager not started"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.debug(f"Getting settings for device {device.id} at {device.ip_address} (Generation: {device.generation})")
        
        if device.generation == DeviceGeneration.GEN1:
            url = f"http://{device.ip_address}/settings"
            logger.debug(f"Using Gen1 settings endpoint: {url}")
        else:  # GEN2
            url = f"http://{device.ip_address}/rpc/Shelly.GetConfig"
            logger.debug(f"Using Gen2 settings endpoint: {url}")

        try:
            logger.debug(f"Sending GET request to {url}")
            async with self._session.get(url) as response:
                logger.debug(f"Response status: {response.status}")
                response.raise_for_status()
                
                settings = await response.json()
                logger.debug(f"Successfully retrieved settings from {device.id}")
                if logger.isEnabledFor(logging.DEBUG):
                    # Pretty print settings for debugging but limit output size
                    settings_str = json.dumps(settings, indent=2)
                    if len(settings_str) > 1000:
                        settings_str = settings_str[:1000] + "... [truncated]"
                    logger.debug(f"Settings content: {settings_str}")
                
                return settings
        except aiohttp.ClientResponseError as e:
            logger.error(f"HTTP error getting settings from {device.id} ({device.ip_address}): {e.status}, {e.message}")
            return {}
        except Exception as e:
            logger.error(f"Error getting settings from {device.id} ({device.ip_address}): {str(e)}")
            import traceback
            logger.debug(traceback.format_exc())
            return {}

    async def apply_settings(self, device: Device, settings: Dict[str, Any]) -> bool:
        """Apply settings to a device"""
        if not self._session:
            error_msg = "ConfigManager not started"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        logger.debug(f"Applying settings to {device.id} ({device.ip_address}), generation: {device.generation}")
        logger.debug(f"Settings to apply: {json.dumps(settings, indent=2)}")

        try:
            # Get current settings before applying changes for comparison
            logger.debug(f"Getting current settings for {device.id} before applying changes")
            before_settings = await self.get_device_settings(device)
            if not before_settings:
                logger.error(f"Failed to get current settings for {device.id}, cannot proceed")
                return False
                
            logger.debug(f"Current settings retrieved successfully for {device.id}")
            
            if device.generation == DeviceGeneration.GEN1:
                # For Gen1, we need to convert string values to appropriate types
                processed_settings = self._process_gen1_settings(settings)
                logger.debug(f"Processed Gen1 settings: {json.dumps(processed_settings, indent=2)}")
                
                # For Gen1 devices, verify supported keys
                logger.debug(f"Current Gen1 settings structure: {list(before_settings.keys())}")
                
                # Check if keys exist in current settings
                for key in processed_settings.keys():
                    if key not in before_settings and '.' not in key:
                        logger.warning(f"Key '{key}' not found in current settings for {device.id}. May not be supported.")
                
                # Try different approaches for GEN1 devices
                success = False
                
                # Approach 1: Standard settings endpoint with POST
                if not success:
                    try:
                        url = f"http://{device.ip_address}/settings"
                        logger.debug(f"Trying Gen1 approach 1: POST to {url}")
                        logger.debug(f"Request data: {json.dumps(processed_settings)}")
                        
                        async with self._session.post(url, json=processed_settings) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                # We need to check if the change is actually reflected
                                # in the API response, as some devices return 200 even if they
                                # don't apply the change
                                
                                # Wait to ensure settings are applied
                                await asyncio.sleep(2)
                                
                                # Get settings after to verify
                                after_check = await self.get_device_settings(device)
                                
                                # Check if settings actually changed
                                if "name" in processed_settings and "name" in after_check:
                                    if after_check["name"] == processed_settings["name"]:
                                        logger.debug("Name change verified in approach 1")
                                        success = True
                                    else:
                                        logger.debug(f"Name not changed in response. Expected: {processed_settings['name']}, Got: {after_check['name']}")
                                else:
                                    success = True  # Assume success for other settings
                            else:
                                logger.debug(f"POST to settings endpoint failed: {response.status}")
                    except Exception as e:
                        logger.debug(f"Approach 1 failed: {str(e)}")
                
                # Approach 2: Settings/name endpoint
                if not success and "name" in processed_settings:
                    try:
                        name_value = processed_settings["name"]
                        url = f"http://{device.ip_address}/settings/name?name={name_value}"
                        logger.debug(f"Trying Gen1 approach 2: GET to {url}")
                        
                        async with self._session.get(url) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                success = True
                                logger.debug("Name change succeeded using direct settings/name endpoint")
                            else:
                                logger.debug(f"Direct name endpoint failed: {response.status}")
                    except Exception as e:
                        logger.debug(f"Approach 2 failed: {str(e)}")
                
                # Approach 2b: URL-encoded name using settings endpoint
                if not success and "name" in processed_settings:
                    try:
                        import urllib.parse
                        name_value = urllib.parse.quote(processed_settings["name"])
                        url = f"http://{device.ip_address}/settings?name={name_value}"
                        logger.debug(f"Trying Gen1 approach 2b: GET to {url} with URL-encoded name")
                        
                        async with self._session.get(url) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                # Wait a bit and check if it actually changed
                                await asyncio.sleep(2)
                                check_settings = await self.get_device_settings(device)
                                if check_settings.get("name") == processed_settings["name"]:
                                    success = True
                                    logger.debug("Name change succeeded using URL-encoded GET")
                                else:
                                    logger.debug(f"Name not changed. Got: {check_settings.get('name')}")
                            else:
                                logger.debug(f"URL-encoded name endpoint failed: {response.status}")
                    except Exception as e:
                        logger.debug(f"Approach 2b failed: {str(e)}")
                
                # Approach 3: Form-encoded POST
                if not success:
                    try:
                        url = f"http://{device.ip_address}/settings"
                        # Convert to form encoded data
                        form_data = aiohttp.FormData()
                        for key, value in processed_settings.items():
                            form_data.add_field(key, str(value))
                            
                        logger.debug(f"Trying Gen1 approach 3: Form POST to {url}")
                        
                        async with self._session.post(url, data=form_data) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                success = True
                                logger.debug("Settings change succeeded using form-encoded POST")
                            else:
                                logger.debug(f"Form-encoded POST failed: {response.status}")
                    except Exception as e:
                        logger.debug(f"Approach 3 failed: {str(e)}")
                
                # Approach 4: Using settings/relay/0 endpoint specifically for relays
                if not success and any(key.startswith("relay") for key in processed_settings.keys()):
                    try:
                        # Extract relay settings
                        relay_settings = {key: value for key, value in processed_settings.items() 
                                        if key.startswith("relay")}
                        
                        url = f"http://{device.ip_address}/settings/relay/0"
                        logger.debug(f"Trying Gen1 approach 4: POST to {url} for relay settings")
                        logger.debug(f"Request data: {json.dumps(relay_settings)}")
                        
                        async with self._session.post(url, json=relay_settings) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                success = True
                                logger.debug("Relay settings change succeeded")
                    except Exception as e:
                        logger.debug(f"Approach 4 failed: {str(e)}")
                
                # Approach 5: Direct parameter update via query string
                if not success:
                    try:
                        # Build query string with all parameters
                        params = []
                        for key, value in processed_settings.items():
                            # Convert boolean values to on/off strings for query params
                            if isinstance(value, bool):
                                value = "on" if value else "off"
                            params.append(f"{key}={value}")
                        
                        query_str = "&".join(params)
                        url = f"http://{device.ip_address}/settings?{query_str}"
                        logger.debug(f"Trying Gen1 approach 5: GET with parameters to {url}")
                        
                        async with self._session.get(url) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                success = True
                                logger.debug("Settings change succeeded using direct parameter GET")
                            else:
                                logger.debug(f"Direct parameter GET failed: {response.status}")
                    except Exception as e:
                        logger.debug(f"Approach 5 failed: {str(e)}")
                
                # Approach 6: Settings update with save flag
                if not success:
                    try:
                        url = f"http://{device.ip_address}/settings"
                        # Add save flag to the settings
                        save_settings = processed_settings.copy()
                        save_settings["save"] = True
                        
                        logger.debug(f"Trying Gen1 approach 6: POST to {url} with save flag")
                        logger.debug(f"Request data: {json.dumps(save_settings)}")
                        
                        async with self._session.post(url, json=save_settings) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                success = True
                                logger.debug("Settings change with save flag succeeded")
                            else:
                                logger.debug(f"Settings with save flag failed: {response.status}")
                    except Exception as e:
                        logger.debug(f"Approach 6 failed: {str(e)}")
                
                # Approach 7: Direct MQTT endpoint for MQTT-specific settings
                if not success and "mqtt" in processed_settings:
                    try:
                        mqtt_settings = processed_settings["mqtt"]
                        url = f"http://{device.ip_address}/settings/mqtt"
                        logger.debug(f"Trying Gen1 approach 7: POST to {url} for MQTT settings")
                        logger.debug(f"MQTT Request data: {json.dumps(mqtt_settings)}")
                        
                        async with self._session.post(url, json=mqtt_settings) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                # Wait to ensure settings are applied
                                await asyncio.sleep(2)
                                
                                # For MQTT settings, we need to check the status endpoint
                                # since the mqtt settings may not appear in the settings response
                                status_url = f"http://{device.ip_address}/status"
                                async with self._session.get(status_url) as status_response:
                                    status_response_text = await status_response.text()
                                    logger.debug(f"Status response status: {status_response.status}")
                                    logger.debug(f"Status response text: {status_response_text}")
                                    
                                    if status_response.status == 200:
                                        status_data = status_response.json() if hasattr(status_response, 'json') else json.loads(status_response_text)
                                        
                                        # Check if the mqtt status matches what we expect
                                        if "mqtt" in status_data:
                                            if ("enable" in mqtt_settings and mqtt_settings["enable"] and status_data["mqtt"]["connected"]) or \
                                               ("enable" in mqtt_settings and not mqtt_settings["enable"] and not status_data["mqtt"]["connected"]):
                                                success = True
                                                logger.debug("MQTT settings successfully applied via direct MQTT endpoint")
                                            else:
                                                logger.debug(f"MQTT status does not match expected settings after update")
                                        else:
                                            # If we can't verify, assume success
                                            success = True
                                            logger.debug("MQTT endpoint returned success, but cannot verify status")
                                
                                # If we got a 200 but couldn't verify, still consider it a success
                                if not success:
                                    success = True
                                    logger.debug("MQTT settings POST succeeded, but connection status could not be verified")
                            else:
                                logger.debug(f"MQTT settings endpoint failed: {response.status}")
                    except Exception as e:
                        logger.debug(f"Approach 7 (MQTT endpoint) failed: {str(e)}")
                
                # If none of the approaches worked, try a save/reboot combination
                if not success:
                    try:
                        # First try to save
                        url = f"http://{device.ip_address}/settings?save=1"
                        logger.debug(f"Trying Gen1 final approach: GET to {url} to save settings")
                        
                        async with self._session.get(url) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                logger.debug("Save command succeeded")
                                
                                # Wait a moment for save to complete
                                await asyncio.sleep(2)
                                
                                # Check if settings were saved
                                after_save = await self.get_device_settings(device)
                                
                                if "name" in processed_settings and "name" in after_save:
                                    if after_save["name"] == processed_settings["name"]:
                                        logger.debug("Name change verified after save")
                                        success = True
                            else:
                                logger.debug(f"Save command failed: {response.status}")
                    except Exception as e:
                        logger.debug(f"Final approach failed: {str(e)}")
                
                if not success:
                    logger.error(f"Failed to apply settings to GEN1 device {device.id} - all approaches failed")
                    return False
                
                # Wait a moment for the device to apply settings
                logger.debug(f"Waiting for Gen1 device {device.id} to apply settings...")
                await asyncio.sleep(2)
                
                # Get settings after change
                logger.debug(f"Getting settings after change for {device.id}")
                after_settings = await self.get_device_settings(device)
                
                if not after_settings:
                    logger.error(f"Failed to get settings after change for {device.id}")
                    return False
                
                # Verify changes
                logger.debug(f"Verifying settings changes for {device.id}")
                verified = self._verify_gen1_settings_changed(processed_settings, before_settings, after_settings)
                
                if verified:
                    logger.info(f"Settings successfully verified for Gen1 device {device.id}")
                else:
                    logger.warning(f"Some settings may not have been applied correctly for Gen1 device {device.id}")
                
                return verified
            else:  # GEN2
                # Get current config structure
                logger.debug(f"Current Gen2 config structure: {list(before_settings.keys())}")
                
                # Process settings for Gen2
                processed_settings = self._process_gen2_settings(settings, before_settings)
                logger.debug(f"Processed Gen2 settings: {json.dumps(processed_settings, indent=2)}")
                
                # Try different endpoints for GEN2 devices
                success = False
                
                # Let's try Shelly.SetConfig first
                if not success:
                    try:
                        url = f"http://{device.ip_address}/rpc/Shelly.SetConfig"
                        request_data = {"config": processed_settings}
                        logger.debug(f"Trying Gen2 endpoint (1): {url}")
                        logger.debug(f"Request data: {json.dumps(request_data, indent=2)}")
                        
                        async with self._session.post(url, json=request_data) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                success = True
                                logger.debug(f"Successfully set settings with Shelly.SetConfig")
                            else:
                                logger.debug(f"Shelly.SetConfig failed with status {response.status}")
                    except Exception as e:
                        logger.debug(f"Shelly.SetConfig failed: {str(e)}")
                
                # If Shelly.SetConfig failed, try updating individual components
                if not success and "sys" in processed_settings and "device" in processed_settings["sys"]:
                    try:
                        url = f"http://{device.ip_address}/rpc/Shelly.SetDeviceConfig"
                        request_data = processed_settings["sys"]["device"]
                        logger.debug(f"Trying Gen2 endpoint (2): {url}")
                        logger.debug(f"Request data: {json.dumps(request_data, indent=2)}")
                        
                        async with self._session.post(url, json=request_data) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                success = True
                                logger.debug(f"Successfully set settings with Shelly.SetDeviceConfig")
                            else:
                                logger.debug(f"Shelly.SetDeviceConfig failed with status {response.status}")
                    except Exception as e:
                        logger.debug(f"Shelly.SetDeviceConfig failed: {str(e)}")
                
                # Another possible endpoint
                if not success and "name" in settings:
                    try:
                        url = f"http://{device.ip_address}/rpc/Sys.SetConfig"
                        request_data = {"config": {"device": {"name": settings["name"]}}}
                        logger.debug(f"Trying Gen2 endpoint (3): {url}")
                        logger.debug(f"Request data: {json.dumps(request_data, indent=2)}")
                        
                        async with self._session.post(url, json=request_data) as response:
                            response_text = await response.text()
                            logger.debug(f"Response status: {response.status}")
                            logger.debug(f"Response text: {response_text}")
                            
                            if response.status == 200:
                                success = True
                                logger.debug(f"Successfully set settings with Sys.SetConfig")
                            else:
                                logger.debug(f"Sys.SetConfig failed with status {response.status}")
                    except Exception as e:
                        logger.debug(f"Sys.SetConfig failed: {str(e)}")
                
                if not success:
                    logger.error(f"Failed to set settings for GEN2 device {device.id} - all API endpoints failed")
                    return False
                
                # Wait a moment for the device to apply settings
                logger.debug(f"Waiting for Gen2 device {device.id} to apply settings...")
                await asyncio.sleep(2)
                
                # Get settings after change
                logger.debug(f"Getting settings after change for {device.id}")
                after_settings = await self.get_device_settings(device)
                
                if not after_settings:
                    logger.error(f"Failed to get settings after change for {device.id}")
                    return False
                
                # Verify changes for Gen2
                logger.debug(f"Verifying settings changes for Gen2 device {device.id}")
                
                # Special verification for name
                if "name" in settings:
                    before_name = None
                    after_name = None
                    
                    # Try to find name in different locations
                    if "sys" in before_settings and "device" in before_settings["sys"]:
                        before_name = before_settings["sys"]["device"].get("name")
                    
                    if "sys" in after_settings and "device" in after_settings["sys"]:
                        after_name = after_settings["sys"]["device"].get("name")
                    
                    if after_name == settings["name"]:
                        logger.info(f"Device name successfully changed from '{before_name}' to '{after_name}'")
                        return True
                    else:
                        logger.warning(f"Failed to change device name. Expected: '{settings['name']}', Actual: '{after_name}'")
                        return False
                
                # For other settings, use the standard verification
                verified = self._verify_gen2_settings_changed(processed_settings, before_settings, after_settings)
                
                if verified:
                    logger.info(f"Settings successfully verified for Gen2 device {device.id}")
                else:
                    logger.warning(f"Some settings may not have been applied correctly for Gen2 device {device.id}")
                
                return verified
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
        logger.debug("Processing Gen1 settings")
        result = {}
        for key, value in settings.items():
            if not isinstance(value, str):
                result[key] = value
                logger.debug(f"Gen1 setting '{key}': keeping non-string value '{value}' as is")
                continue
                
            # Convert string 'true'/'false' to boolean
            if value.lower() == 'true':
                result[key] = True
                logger.debug(f"Gen1 setting '{key}': converted string 'true' to boolean True")
            elif value.lower() == 'false':
                result[key] = False
                logger.debug(f"Gen1 setting '{key}': converted string 'false' to boolean False")
            # Try to convert to number if it looks like one
            elif value.isdigit():
                result[key] = int(value)
                logger.debug(f"Gen1 setting '{key}': converted string '{value}' to integer {int(value)}")
            elif self._is_float(value):
                result[key] = float(value)
                logger.debug(f"Gen1 setting '{key}': converted string '{value}' to float {float(value)}")
            else:
                result[key] = value
                logger.debug(f"Gen1 setting '{key}': keeping string value '{value}' as is")
        return result
    
    def _process_gen2_settings(self, settings: Dict[str, Any], current_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process settings for Gen2 devices
        - Convert string values to appropriate types
        - Handle nested paths with dot notation (e.g., "wifi.sta.ssid")
        """
        logger.debug("Processing Gen2 settings")
        result = {}
        
        # Handle special properties that need to be in specific locations
        if "name" in settings:
            # For GEN2 devices, 'name' should be in sys.device.name
            if "sys" not in result:
                result["sys"] = {}
            if "device" not in result["sys"]:
                result["sys"]["device"] = {}
            result["sys"]["device"]["name"] = settings["name"]
            logger.debug(f"Gen2 setting: moved 'name' to sys.device.name with value '{settings['name']}'")
            
        # Process all other settings
        for key, value in settings.items():
            # Skip 'name' as we've already processed it specially
            if key == "name":
                continue
                
            # Handle nested paths with dot notation
            if "." in key:
                # Split by dots to get nested keys
                parts = key.split(".")
                logger.debug(f"Gen2 setting: processing nested key '{key}' with parts {parts}")
                
                # Start with the result dict
                current = result
                
                # Navigate through all but the last key, creating dictionaries as needed
                for part in parts[:-1]:
                    if part not in current:
                        current[part] = {}
                        logger.debug(f"Gen2 setting: created nested dict for part '{part}'")
                    current = current[part]
                
                # Set the value at the last key
                value_to_set = self._convert_value_type(value)
                current[parts[-1]] = value_to_set
                logger.debug(f"Gen2 setting: set nested key '{key}' to {value_to_set}")
            else:
                # Regular non-nested key
                converted_value = self._convert_value_type(value)
                result[key] = converted_value
                logger.debug(f"Gen2 setting: set direct key '{key}' to {converted_value}")
                
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
            
    def _verify_gen1_settings_changed(self, settings_to_apply: Dict[str, Any], 
                               before_settings: Dict[str, Any], 
                               after_settings: Dict[str, Any]) -> bool:
        """Verify that settings were correctly applied for GEN1 devices"""
        logger.debug("Verifying Gen1 settings changes")
        all_verified = True
        
        for key, expected_value in settings_to_apply.items():
            # Check if the setting exists in the after settings
            if key not in after_settings:
                logger.warning(f"Setting '{key}' does not exist in Gen1 device response after update")
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
        logger.debug("Verifying Gen2 settings changes")
        all_verified = True
        
        # For Gen2 we need to handle both direct settings and nested ones
        for key, expected_value in settings_to_apply.items():
            if isinstance(expected_value, dict):
                # Handle nested dictionary
                for nested_key, nested_value in self._flatten_dict(expected_value, parent_key=key):
                    logger.debug(f"Verifying nested Gen2 setting: {nested_key}")
                    verified = self._verify_gen2_setting(nested_key, nested_value, 
                                                       before_settings, after_settings)
                    all_verified = all_verified and verified
            else:
                # Handle direct key
                logger.debug(f"Verifying direct Gen2 setting: {key}")
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
        logger.debug(f"Verifying Gen2 setting '{key}' with parts {key_parts}")
        
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
                    logger.debug(f"Part '{part}' of path '{key}' not found in before settings")
                    break
                    
            for part in key_parts:
                if part in after_value:
                    after_value = after_value[part]
                else:
                    logger.warning(f"Setting path '{key}', part '{part}' not found in device after update")
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
        logger.debug(f"Applying bulk settings to {len(devices)} devices")
        tasks = [self.apply_settings(device, settings) for device in devices]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        result_map = {
            device.id: isinstance(result, bool) and result 
            for device, result in zip(devices, results)
        }
        
        logger.debug(f"Bulk settings results: {result_map}")
        return result_map 