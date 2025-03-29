#!/usr/bin/env python
"""Tests for the DeviceRegistry class that manages device objects and loading from files."""

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
from src.shelly_manager.models.device_registry import DeviceRegistry


class TestDeviceRegistry(unittest.TestCase):
    """Tests for the DeviceRegistry class."""

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for device files
        self.temp_dir = tempfile.mkdtemp()
        self.device_registry = DeviceRegistry(devices_dir=self.temp_dir)

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
            id="shelly-b0a73248b180",
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

    def tearDown(self):
        """Clean up the test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)

    def test_save_device(self):
        """Test saving a device to a file."""
        # Save the gen1 device
        result = self.device_registry.save_device(self.gen1_device)
        self.assertTrue(result)

        # Check that the file exists
        device_files = list(Path(self.temp_dir).glob("*.yaml"))
        self.assertEqual(len(device_files), 1)
        
        # Verify filename format
        filename = device_files[0].name
        self.assertTrue(filename.startswith("SHPLG-S_"))
        self.assertTrue(filename.endswith(".yaml"))
        
        # Check the file contents
        with open(device_files[0], 'r') as f:
            loaded_data = yaml.safe_load(f)
        
        self.assertEqual(loaded_data["id"], self.gen1_device.id)
        self.assertEqual(loaded_data["name"], self.gen1_device.name)
        self.assertEqual(loaded_data["generation"], "gen1")
        self.assertEqual(loaded_data["mac_address"], self.gen1_device.mac_address)
        self.assertEqual(loaded_data["discovery_method"], "mDNS")

    def test_save_gen2_device(self):
        """Test saving a Gen2 device to a file."""
        # Save the gen2 device
        result = self.device_registry.save_device(self.gen2_device)
        self.assertTrue(result)

        # Check that the file exists
        device_files = list(Path(self.temp_dir).glob("*.yaml"))
        self.assertEqual(len(device_files), 1)
        
        # Verify filename format
        filename = device_files[0].name
        self.assertTrue(filename.startswith("shellyplus2pm_"))
        self.assertTrue(filename.endswith(".yaml"))
        
        # Check the file contents
        with open(device_files[0], 'r') as f:
            loaded_data = yaml.safe_load(f)
        
        self.assertEqual(loaded_data["id"], self.gen2_device.id)
        self.assertEqual(loaded_data["name"], self.gen2_device.name)
        self.assertEqual(loaded_data["generation"], "gen2")
        self.assertEqual(loaded_data["mac_address"], self.gen2_device.mac_address)
        self.assertEqual(loaded_data["discovery_method"], "mDNS")
        self.assertEqual(loaded_data["eco_mode_enabled"], True)

    def test_get_device(self):
        """Test getting a device by ID."""
        # Save a device first
        self.device_registry.save_device(self.gen1_device)
        
        # Clear the registry's cache to force loading from file
        self.device_registry.devices.clear()
        
        # Get the device
        loaded_device = self.device_registry.get_device(self.gen1_device.id)
        
        # Check that the device was loaded correctly
        self.assertIsNotNone(loaded_device)
        self.assertEqual(loaded_device.id, self.gen1_device.id)
        self.assertEqual(loaded_device.name, self.gen1_device.name)
        self.assertEqual(loaded_device.generation, self.gen1_device.generation)
        self.assertEqual(loaded_device.mac_address, self.gen1_device.mac_address)
        self.assertEqual(loaded_device.discovery_method, self.gen1_device.discovery_method)

    def test_get_nonexistent_device(self):
        """Test getting a device that doesn't exist."""
        # Try to get a device that doesn't exist
        loaded_device = self.device_registry.get_device("nonexistent")
        
        # Check that None was returned
        self.assertIsNone(loaded_device)

    def test_get_devices(self):
        """Test getting multiple devices by ID."""
        # Save both devices
        self.device_registry.save_device(self.gen1_device)
        self.device_registry.save_device(self.gen2_device)
        
        # Get the devices - don't clear the cache since we just saved them
        # and we want to test the get_devices method more than the file loading
        loaded_devices = self.device_registry.get_devices([
            self.gen1_device.id, 
            self.gen2_device.id,
            "nonexistent"  # This should be ignored
        ])
        
        # Check that the correct devices were loaded
        self.assertEqual(len(loaded_devices), 2)
        
        # Verify the devices in the result
        device_ids = [device.id for device in loaded_devices]
        self.assertIn(self.gen1_device.id, device_ids)
        self.assertIn(self.gen2_device.id, device_ids)

    def test_load_all_devices(self):
        """Test loading all devices from the devices directory."""
        # Save both devices
        self.device_registry.save_device(self.gen1_device)
        self.device_registry.save_device(self.gen2_device)
        
        # Clear the registry's cache to force loading from file
        self.device_registry.devices.clear()
        
        # Load all devices
        loaded_devices = self.device_registry.load_all_devices()
        
        # Check that both devices were loaded
        self.assertEqual(len(loaded_devices), 2)
        
        # Verify the devices in the result
        device_ids = [device.id for device in loaded_devices]
        self.assertIn(self.gen1_device.id, device_ids)
        self.assertIn(self.gen2_device.id, device_ids)
        
        # Verify the cache was updated
        self.assertEqual(len(self.device_registry.devices), 2)
        self.assertIn(self.gen1_device.id, self.device_registry.devices)
        self.assertIn(self.gen2_device.id, self.device_registry.devices)

    def test_file_persistence(self):
        """Test that device data is correctly saved to and loaded from files."""
        # Save a device
        device = Device(
            id="test-persistence",
            name="Test Persistence Device",
            generation=DeviceGeneration.GEN2,
            mac_address="AA:BB:CC:DD:EE:FF",
            ip_address="192.168.1.102"
        )
        
        # Save the device
        result = self.device_registry.save_device(device)
        self.assertTrue(result)
        
        # List files in the directory to verify it was saved
        files = list(Path(self.temp_dir).glob("*.yaml"))
        self.assertEqual(len(files), 1)
        
        # Create a new registry instance to test loading from file
        new_registry = DeviceRegistry(devices_dir=self.temp_dir)
        
        # Try to load the device using MAC address
        # MAC address lookup is the primary method used by DeviceRegistry
        loaded_device = new_registry.get_device("AABBCCDDEEFF")
        
        # Verify the device was loaded correctly
        self.assertIsNotNone(loaded_device, "Device should be loaded from file by MAC address")
        self.assertEqual(loaded_device.id, device.id)
        self.assertEqual(loaded_device.name, device.name)
        self.assertEqual(loaded_device.mac_address, device.mac_address)
        
        # Clear the registry to test loading again
        new_registry.devices.clear()
        
        # The registry should also be able to find the device using its original ID
        # if it was previously loaded (for example, during load_all_devices)
        # For this test, we'll manually add it first
        new_registry.load_all_devices()
        
        # Now try to get it by ID
        loaded_by_id = new_registry.get_device("test-persistence")
        self.assertIsNotNone(loaded_by_id, "Device should be found by ID after loading all devices")
        self.assertEqual(loaded_by_id.id, device.id)

    def test_missing_devices_dir(self):
        """Test behavior when devices directory doesn't exist."""
        # Create a registry with a nonexistent directory
        nonexistent_dir = os.path.join(self.temp_dir, "nonexistent")
        registry = DeviceRegistry(devices_dir=nonexistent_dir)
        
        # Try to load all devices
        loaded_devices = registry.load_all_devices()
        
        # Should return an empty list
        self.assertEqual(len(loaded_devices), 0)
        
        # Try to save a device
        result = registry.save_device(self.gen1_device)
        
        # Should create the directory and save successfully
        self.assertTrue(result)
        self.assertTrue(os.path.exists(nonexistent_dir))

    def test_invalid_file_data(self):
        """Test handling of invalid data in device files."""
        # Create an invalid device file
        invalid_file_path = Path(self.temp_dir) / "invalid_device.yaml"
        with open(invalid_file_path, 'w') as f:
            f.write("invalid: yaml: content")
        
        # Create a registry and try to load all devices
        registry = DeviceRegistry(devices_dir=self.temp_dir)
        loaded_devices = registry.load_all_devices()
        
        # Should not crash and should return empty list
        self.assertEqual(len(loaded_devices), 0)
        
        # Verify that we can still add and retrieve devices normally
        registry.add_device(self.gen1_device)
        retrieved_device = registry.get_device(self.gen1_device.id)
        self.assertIsNotNone(retrieved_device)
        self.assertEqual(retrieved_device.id, self.gen1_device.id)

    def test_device_cache(self):
        """Test adding and retrieving devices from the registry cache."""
        # Add a device to the registry
        self.device_registry.add_device(self.gen1_device)
        
        # Retrieve the device from the cache
        device = self.device_registry.get_device(self.gen1_device.id)
        self.assertIsNotNone(device)
        self.assertEqual(device.id, self.gen1_device.id)
        
        # Verify it's the same object (by identity)
        self.assertIs(device, self.gen1_device)
        
        # Add a second device
        self.device_registry.add_device(self.gen2_device)
        
        # Get multiple devices
        devices = self.device_registry.get_devices([
            self.gen1_device.id,
            self.gen2_device.id
        ])
        
        # Verify both devices were retrieved
        self.assertEqual(len(devices), 2)
        self.assertIn(self.gen1_device, devices)
        self.assertIn(self.gen2_device, devices)


if __name__ == "__main__":
    unittest.main() 