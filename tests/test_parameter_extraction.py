#!/usr/bin/env python3
"""Test module for parameter extraction functionality."""

import unittest
import os
import asyncio
import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Add the src directory to the path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.shelly_manager.models.device import Device, DeviceGeneration
from src.shelly_manager.models.device_capabilities import CapabilityDiscovery
from src.shelly_manager.parameter.parameter_service import ParameterService
from src.shelly_manager.models.device_parameters import ParameterDefinition, ParameterType


class TestParameterExtraction(unittest.TestCase):
    """Test class for parameter extraction functionality."""

    def setUp(self):
        """Set up test devices."""
        self.gen1_device = Device(
            id="test_gen1",
            name="Test Gen1 Device",
            generation=DeviceGeneration.GEN1,
            ip_address="192.168.1.100",
            device_type="SHPLG-S"
        )
        
        self.gen2_device = Device(
            id="test_gen2",
            name="Test Gen2 Device",
            generation=DeviceGeneration.GEN2,
            ip_address="192.168.1.101",
            device_type="Plus1PM"
        )
        
        # Create a capability discovery instance
        self.capability_discovery = CapabilityDiscovery()
        
        # Load test data
        self.gen1_settings_data = self._load_test_data("gen1_settings.json")
        self.gen1_status_data = self._load_test_data("gen1_status.json")
        self.gen1_shelly_data = self._load_test_data("gen1_shelly.json")
        self.gen2_data = self._load_test_data("gen2_config.json")
    
    def _load_test_data(self, filename):
        """Load test data from JSON file."""
        test_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(test_dir, "data", filename)
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            # Return empty dict if file doesn't exist yet
            return {}
    
    def test_parameter_mapping(self):
        """Test parameter mapping functionality."""
        # Test mapping of basic parameters
        param1 = ParameterDefinition(
            name="test_string",
            path="test/path",
            param_type=ParameterType.STRING,
            description="Test string parameter"
        )
        
        param2 = ParameterDefinition(
            name="test_bool",
            path="test/bool_path",
            param_type=ParameterType.BOOLEAN,
            description="Test boolean parameter"
        )
        
        self.assertEqual(param1.name, "test_string")
        self.assertEqual(param1.path, "test/path")
        self.assertEqual(param1.param_type, ParameterType.STRING)
        
        self.assertEqual(param2.name, "test_bool")
        self.assertEqual(param2.path, "test/bool_path")
        self.assertEqual(param2.param_type, ParameterType.BOOLEAN)
    
    def test_extract_parameters_recursive(self):
        """Test recursive parameter extraction from JSON data."""
        test_data = {
            "settings": {
                "led": {
                    "mode": "switch",
                    "power_on": True
                },
                "relay0": {
                    "name": "Main Relay",
                    "default_state": "on"
                }
            },
            "wifi_ap": {
                "enabled": False,
                "ssid": "test_ssid",
                "password": "password123"
            }
        }
        
        parameters = []
        # Call the private method of CapabilityDiscovery to extract parameters
        self.capability_discovery._extract_parameters_recursive(
            parameters, test_data, "", "test"
        )
        
        # Verify parameters were extracted correctly
        self.assertTrue(any(p.name == "settings.led.mode" for p in parameters))
        self.assertTrue(any(p.name == "settings.led.power_on" for p in parameters))
        self.assertTrue(any(p.name == "settings.relay0.name" for p in parameters))
        self.assertTrue(any(p.name == "settings.relay0.default_state" for p in parameters))
        self.assertTrue(any(p.name == "wifi_ap.enabled" for p in parameters))
        self.assertTrue(any(p.name == "wifi_ap.ssid" for p in parameters))
        self.assertTrue(any(p.name == "wifi_ap.password" for p in parameters))
        
        # Check parameter types
        for param in parameters:
            if param.name == "settings.led.power_on" or param.name == "wifi_ap.enabled":
                self.assertEqual(param.param_type, ParameterType.BOOLEAN)
            elif param.name == "settings.led.mode" or param.name == "settings.relay0.name":
                self.assertEqual(param.param_type, ParameterType.STRING)
    
    @patch('aiohttp.ClientSession')
    async def test_gen1_parameter_endpoints(self, mock_session):
        """Test Gen1 parameter endpoints."""
        # Set up mock response for each endpoint
        mock_response = AsyncMock()
        mock_response.json.side_effect = [
            self.gen1_settings_data,
            self.gen1_status_data,
            self.gen1_shelly_data,
            # Add mock responses for other Gen1 endpoints as needed
        ]
        mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
        
        # Create a parameter service with mocked session
        param_service = ParameterService()
        param_service.session = mock_session
        
        # Extract parameters for Gen1 device
        params = await self.capability_discovery._discover_gen1_capabilities(self.gen1_device)
        
        # Verify parameters were extracted from different endpoints
        self.assertGreater(len(params.parameters), 0)
        
        # Check if parameters from different endpoints are present
        settings_params = [p for p in params.parameters if p.path.startswith("/settings")]
        status_params = [p for p in params.parameters if p.path.startswith("/status")]
        shelly_params = [p for p in params.parameters if p.path.startswith("/shelly")]
        
        self.assertGreater(len(settings_params), 0, "No settings parameters found")
        self.assertGreater(len(status_params), 0, "No status parameters found")
        self.assertGreater(len(shelly_params), 0, "No shelly parameters found")
    
    def test_parameter_type_detection(self):
        """Test automatic parameter type detection from values."""
        # Test string detection
        self.assertEqual(
            self.capability_discovery._get_parameter_type("test_string"),
            ParameterType.STRING
        )
        
        # Test boolean detection
        self.assertEqual(
            self.capability_discovery._get_parameter_type(True),
            ParameterType.BOOLEAN
        )
        
        # Test integer detection
        self.assertEqual(
            self.capability_discovery._get_parameter_type(42),
            ParameterType.INTEGER
        )
        
        # Test float detection
        self.assertEqual(
            self.capability_discovery._get_parameter_type(3.14),
            ParameterType.FLOAT
        )
        
        # Test null/None handling
        self.assertEqual(
            self.capability_discovery._get_parameter_type(None),
            ParameterType.UNKNOWN
        )
    
    def test_skip_internal_fields(self):
        """Test skipping of internal fields during parameter extraction."""
        test_data = {
            "settings": {
                "_updated_at": 12345,  # Should be skipped
                "relay0": {
                    "name": "Main Relay",
                    "_internal": True  # Should be skipped
                }
            }
        }
        
        parameters = []
        self.capability_discovery._extract_parameters_recursive(
            parameters, test_data, "", "test"
        )
        
        # Verify that internal fields were skipped
        self.assertFalse(any(p.name == "settings._updated_at" for p in parameters))
        self.assertFalse(any(p.name == "settings.relay0._internal" for p in parameters))
        self.assertTrue(any(p.name == "settings.relay0.name" for p in parameters))


@pytest.mark.asyncio
async def test_async_parameter_extraction():
    """Test async parameter extraction functionality."""
    # Create a capability discovery instance
    capability_discovery = CapabilityDiscovery()
    
    # Create a test device
    test_device = Device(
        id="test_async",
        name="Test Async Device",
        generation=DeviceGeneration.GEN1,
        ip_address="192.168.1.102",
        device_type="SHPLG-S"
    )
    
    # Mock HTTP responses
    with patch('aiohttp.ClientSession') as mock_session:
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "wifi_sta": {"enabled": True, "ssid": "Test_Network"},
            "relay0": {"ison": False, "has_timer": False},
            "meters": [{"power": 0.0, "is_valid": True}]
        }
        mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
        
        # Test parameter discovery
        params = await capability_discovery._discover_gen1_capabilities(test_device)
        
        # Verify parameters were extracted
        assert len(params.parameters) > 0
        assert any(p.name == "wifi_sta.enabled" for p in params.parameters)
        assert any(p.name == "relay0.ison" for p in params.parameters)


if __name__ == "__main__":
    unittest.main() 