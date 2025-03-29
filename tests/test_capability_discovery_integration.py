#!/usr/bin/env python
"""Tests for the integration between DiscoveryService and CapabilityDiscovery."""

import unittest
import os
import shutil
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# Add the project directory to the Python path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.shelly_manager.models.device import Device, DeviceGeneration, DeviceStatus
from src.shelly_manager.models.device_capabilities import DeviceCapability, DeviceCapabilities
from src.shelly_manager.discovery.discovery_service import DiscoveryService


class TestCapabilityDiscoveryIntegration(unittest.TestCase):
    """Tests for the integration between DiscoveryService and CapabilityDiscovery."""

    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for capability files
        self.temp_dir = tempfile.mkdtemp()
        
        # Patch the device_capabilities global instance
        self.capabilities_patch = patch('src.shelly_manager.models.device_capabilities.device_capabilities')
        self.mock_capabilities = self.capabilities_patch.start()
        
        # Create a capabilities manager for testing
        self.capabilities_manager = DeviceCapabilities(capabilities_dir=self.temp_dir)
        self.mock_capabilities.capabilities = {}
        self.mock_capabilities._type_to_capability = {}
        self.mock_capabilities.get_capability_for_device.return_value = None
        self.mock_capabilities.save_capability.return_value = True

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
            raw_app="Plus2PM",
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
        
        # Stop the patch
        self.capabilities_patch.stop()

    @patch('aiohttp.ClientSession')
    async def async_test_discover_capabilities(self, mock_session):
        """Test discovering capabilities for a device."""
        # Mock the HTTP response for the device APIs
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "type": "SHPLG-S",
            "name": "Test Plug",
            "eco_mode": True,
            "max_power": 2500
        }
        
        # Make the session's get and post methods return our mock response
        mock_session_instance = MagicMock()
        mock_session_instance.get = AsyncMock(return_value=mock_response)
        mock_session_instance.post = AsyncMock(return_value=mock_response)
        mock_session.return_value = mock_session_instance
        
        # Initialize discovery service
        discovery_service = DiscoveryService(debug=True)
        discovery_service._session = mock_session_instance
        discovery_service._capabilities = self.mock_capabilities
        
        # Test discovering capabilities for a Gen1 device
        result = await discovery_service.discover_device_capabilities(self.gen1_device)
        
        # Check that the capability discovery was successful
        self.assertTrue(result)
        
        # Check that the CapabilityDiscovery methods were called
        self.mock_capabilities.save_capability.assert_called()

    def test_discover_capabilities(self):
        """Run the async test."""
        asyncio.run(self.async_test_discover_capabilities())

    @patch('aiohttp.ClientSession')
    async def async_test_discover_capabilities_for_all_devices(self, mock_session):
        """Test discovering capabilities for all devices."""
        # Mock the HTTP response for the device APIs
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = {
            "type": "SHPLG-S",
            "name": "Test Plug",
            "eco_mode": True,
            "max_power": 2500
        }
        
        # Make the session's get and post methods return our mock response
        mock_session_instance = MagicMock()
        mock_session_instance.get = AsyncMock(return_value=mock_response)
        mock_session_instance.post = AsyncMock(return_value=mock_response)
        mock_session.return_value = mock_session_instance
        
        # Initialize discovery service with two devices
        discovery_service = DiscoveryService(debug=True)
        discovery_service._session = mock_session_instance
        discovery_service._capabilities = self.mock_capabilities
        discovery_service._devices = {
            self.gen1_device.id: self.gen1_device,
            self.gen2_device.id: self.gen2_device
        }
        
        # Test discovering capabilities for all devices
        results = await discovery_service.discover_capabilities_for_all_devices()
        
        # Check that the capability discovery was successful for both devices
        self.assertEqual(len(results), 2)
        self.assertTrue(results[self.gen1_device.id])
        self.assertTrue(results[self.gen2_device.id])
        
        # Check that the CapabilityDiscovery methods were called twice
        self.assertEqual(self.mock_capabilities.save_capability.call_count, 2)

    def test_discover_capabilities_for_all_devices(self):
        """Run the async test."""
        asyncio.run(self.async_test_discover_capabilities_for_all_devices())


if __name__ == '__main__':
    unittest.main() 