#!/usr/bin/env python
"""Tests for the device capabilities system."""

import unittest
import os
import shutil
import tempfile
from pathlib import Path
import yaml

# Add the project directory to the Python path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.shelly_manager.models.device import Device, DeviceGeneration, DeviceStatus
from src.shelly_manager.models.device_capabilities import DeviceCapability, DeviceCapabilities

class TestDeviceCapabilities(unittest.TestCase):
    """Tests for the device capabilities system."""

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for capability files
        self.temp_dir = tempfile.mkdtemp()
        self.capabilities_manager = DeviceCapabilities(capabilities_dir=self.temp_dir)

        # Create test device objects
        self.gen1_device = Device(
            id="aabbccddeeff",
            name="Test Gen1 Device",
            generation=DeviceGeneration.GEN1,
            raw_type="SHPLG-S",
            ip_address="192.168.1.100",
            mac_address="AA:BB:CC:DD:EE:FF",
            status=DeviceStatus.ONLINE,
            firmware_version="20230913-112003/v1.14.0",
            discovery_method="mDNS"
        )

        self.gen2_device = Device(
            id="shellyplus2pm-b0a73248b180",
            name="Test Gen2 Device",
            generation=DeviceGeneration.GEN2,
            raw_type="",
            raw_app="shellyplus2pm",
            raw_model="SNSW-102P16EU",
            ip_address="192.168.1.101",
            mac_address="B0:A7:32:48:B1:80",
            status=DeviceStatus.ONLINE,
            firmware_version="1.4.4",
            discovery_method="mDNS",
            eco_mode_enabled=True
        )

        # Create test capability definitions
        self.gen1_capability = DeviceCapability(
            device_type="SHPLG-S",
            name="Shelly Plug S",
            generation="gen1",
            data={
                "apis": {
                    "settings": {
                        "description": "Device settings API"
                    },
                    "status": {
                        "description": "Device status API"
                    }
                },
                "parameters": {
                    "name": {
                        "type": "string",
                        "description": "Device name",
                        "api": "settings",
                        "parameter_path": "name"
                    },
                    "max_power": {
                        "type": "integer",
                        "description": "Maximum power in watts",
                        "api": "settings",
                        "parameter_path": "max_power",
                        "default": 2500
                    },
                    "eco_mode": {
                        "type": "boolean",
                        "description": "Energy saving mode",
                        "api": "settings",
                        "parameter_path": "eco_mode",
                        "default": False
                    }
                },
                "type_mappings": ["SHPLG-S"]
            }
        )

        self.gen2_capability = DeviceCapability(
            device_type="Plus2PM",
            name="Shelly Plus 2PM",
            generation="gen2",
            data={
                "apis": {
                    "Shelly.GetStatus": {
                        "description": "Get device status"
                    },
                    "Sys.GetConfig": {
                        "description": "Get system configuration"
                    },
                    "Sys.SetConfig": {
                        "description": "Set system configuration"
                    }
                },
                "parameters": {
                    "name": {
                        "type": "string",
                        "description": "Device name",
                        "api": "Shelly.SetConfig",
                        "parameter_path": "name"
                    },
                    "eco_mode": {
                        "type": "boolean",
                        "description": "Energy saving mode",
                        "api": "Sys.SetConfig",
                        "parameter_path": "device.eco_mode",
                        "default": False
                    }
                },
                "type_mappings": ["shellyplus2pm"]
            }
        )

    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_capability_creation(self):
        """Test creating device capabilities."""
        # Check the Gen1 capability
        self.assertEqual(self.gen1_capability.device_type, "SHPLG-S")
        self.assertEqual(self.gen1_capability.name, "Shelly Plug S")
        self.assertEqual(self.gen1_capability.generation, "gen1")
        self.assertEqual(len(self.gen1_capability.apis), 2)
        self.assertEqual(len(self.gen1_capability.parameters), 3)
        
        # Check the Gen2 capability
        self.assertEqual(self.gen2_capability.device_type, "Plus2PM")
        self.assertEqual(self.gen2_capability.name, "Shelly Plus 2PM")
        self.assertEqual(self.gen2_capability.generation, "gen2")
        self.assertEqual(len(self.gen2_capability.apis), 3)
        self.assertEqual(len(self.gen2_capability.parameters), 2)

    def test_save_and_load_capability(self):
        """Test saving and loading a capability definition."""
        # Save the Gen1 capability
        result = self.capabilities_manager.save_capability(self.gen1_capability)
        self.assertTrue(result)
        
        # Check that the file exists
        expected_file = Path(self.temp_dir) / "SHPLG-S.yaml"
        self.assertTrue(expected_file.exists())
        
        # Clear the capabilities manager's cache
        self.capabilities_manager.capabilities = {}
        self.capabilities_manager._type_to_capability = {}
        
        # Reload the capabilities
        self.capabilities_manager.load_all_capabilities()
        
        # Check that the capability was loaded
        self.assertIn("SHPLG-S", self.capabilities_manager.capabilities)
        loaded_capability = self.capabilities_manager.capabilities["SHPLG-S"]
        self.assertEqual(loaded_capability.device_type, "SHPLG-S")
        self.assertEqual(loaded_capability.name, "Shelly Plug S")
        self.assertEqual(loaded_capability.generation, "gen1")
        self.assertEqual(len(loaded_capability.apis), 2)
        self.assertEqual(len(loaded_capability.parameters), 3)
        self.assertEqual(loaded_capability.parameters["eco_mode"]["type"], "boolean")

    def test_get_capability_for_device(self):
        """Test matching a device to its capability definition."""
        # Save both capabilities
        self.capabilities_manager.save_capability(self.gen1_capability)
        self.capabilities_manager.save_capability(self.gen2_capability)
        
        # Get capability for Gen1 device
        capability = self.capabilities_manager.get_capability_for_device(self.gen1_device)
        self.assertIsNotNone(capability)
        self.assertEqual(capability.device_type, "SHPLG-S")
        
        # Get capability for Gen2 device
        capability = self.capabilities_manager.get_capability_for_device(self.gen2_device)
        self.assertIsNotNone(capability)
        self.assertEqual(capability.device_type, "Plus2PM")

    def test_parameter_checks(self):
        """Test checking if a parameter is supported."""
        # Create a capability with various parameters
        capability = DeviceCapability(
            device_type="TestDevice",
            name="Test Device",
            generation="gen2",
            data={
                "parameters": {
                    "name": {
                        "type": "string",
                        "description": "Device name",
                        "api": "Shelly.SetConfig",
                        "parameter_path": "name"
                    },
                    "eco_mode": {
                        "type": "boolean",
                        "description": "Energy saving mode",
                        "api": "Sys.SetConfig",
                        "parameter_path": "device.eco_mode"
                    },
                    "max_power": {
                        "type": "integer",
                        "description": "Maximum power in watts",
                        "api": "Switch.SetConfig",
                        "parameter_path": "power_limit"
                    }
                }
            }
        )
        
        # Check if parameters are supported
        self.assertTrue(capability.has_parameter("name"))
        self.assertTrue(capability.has_parameter("eco_mode"))
        self.assertTrue(capability.has_parameter("max_power"))
        self.assertFalse(capability.has_parameter("nonexistent"))
        
        # Get parameter details
        eco_mode_details = capability.get_parameter_details("eco_mode")
        self.assertEqual(eco_mode_details["type"], "boolean")
        self.assertEqual(eco_mode_details["api"], "Sys.SetConfig")
        self.assertEqual(eco_mode_details["parameter_path"], "device.eco_mode")
        
        # Get API for parameter
        eco_mode_api = capability.get_parameter_api("eco_mode")
        self.assertEqual(eco_mode_api, "Sys.SetConfig")

    def test_device_capabilities(self):
        """Test the DeviceCapabilities class."""
        # Save both capabilities
        self.capabilities_manager.save_capability(self.gen1_capability)
        self.capabilities_manager.save_capability(self.gen2_capability)
        
        # Check that the capabilities were loaded
        self.assertEqual(len(self.capabilities_manager.capabilities), 2)
        
        # Check that the type mappings were created
        self.assertEqual(self.capabilities_manager._type_to_capability["SHPLG-S"], "SHPLG-S")
        self.assertEqual(self.capabilities_manager._type_to_capability["shellyplus2pm"], "Plus2PM")
        
        # Get capability by ID
        capability = self.capabilities_manager.get_capability("SHPLG-S")
        self.assertIsNotNone(capability)
        self.assertEqual(capability.device_type, "SHPLG-S")
        
        # Get nonexistent capability
        capability = self.capabilities_manager.get_capability("nonexistent")
        self.assertIsNone(capability)

if __name__ == "__main__":
    unittest.main() 