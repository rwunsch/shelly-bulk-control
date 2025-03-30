import pytest
from shelly_manager.models.device import Device, DeviceGeneration, DeviceStatus
from shelly_manager.models.device_config import DeviceConfigManager, DeviceTypeConfig

def test_device_config_loading():
    """Test loading device configurations from YAML"""
    config_manager = DeviceConfigManager()
    
    # Test Gen1 device config
    gen1_config = config_manager.get_device_config(
        raw_type="SHPLG-S",
        raw_app="",
        generation="gen1"
    )
    assert gen1_config is not None
    assert gen1_config.name == "Shelly Plug S"
    assert gen1_config.type == "plug"
    assert gen1_config.num_outputs == 1
    assert gen1_config.num_meters == 1
    assert gen1_config.max_power == 2500
    assert "power_monitoring" in gen1_config.features
    
    # Test Gen2 device config - explicitly use 'plus1pm' for Plus1PM
    gen2_config = config_manager.get_device_config(
        raw_type="",
        raw_app="plus1pm",
        generation="gen2"
    )
    assert gen2_config is not None
    assert gen2_config.name == "Shelly Plus 1PM"
    assert gen2_config.type == "relay"
    assert gen2_config.num_outputs == 1
    assert gen2_config.num_meters == 1
    assert "power_monitoring" in gen2_config.features

def test_device_creation():
    """Test device creation with configuration"""
    # Create a Gen1 device
    gen1_device = Device(
        id="abc123",
        name="Kitchen Plug",
        generation=DeviceGeneration.GEN1,
        raw_type="SHPLG-S",
        ip_address="192.168.1.100",
        mac_address="AA:BB:CC:DD:EE:FF"
    )
    assert gen1_device.device_name == "Shelly Plug S"
    assert gen1_device.device_type == "plug"
    assert gen1_device.num_outputs == 1
    assert gen1_device.num_meters == 1
    assert gen1_device.max_power == 2500
    assert "power_monitoring" in gen1_device.features
    
    # Create a Gen2 device - explicitly set raw_app to plus1pm
    gen2_device = Device(
        id="def456",
        name="Living Room Light",
        generation=DeviceGeneration.GEN2,
        raw_type="ShellyPlus1PM",
        raw_app="plus1pm",
        ip_address="192.168.1.101",
        mac_address="11:22:33:44:55:66"
    )
    assert gen2_device.device_name == "Shelly Plus 1PM"
    assert gen2_device.device_type == "relay"
    assert gen2_device.num_outputs == 1
    assert gen2_device.num_meters == 1
    assert "power_monitoring" in gen2_device.features
    
    # Test unknown device
    unknown_device = Device(
        id="xyz789",
        name="Unknown Device",
        generation=DeviceGeneration.UNKNOWN,
        raw_type="unknown",
        ip_address="192.168.1.102",
        mac_address="99:88:77:66:55:44"
    )
    assert unknown_device.device_name == "Unknown Device"
    assert unknown_device.device_type == "unknown"
    assert unknown_device.num_outputs is None
    assert unknown_device.num_meters is None
    assert unknown_device.max_power is None
    assert len(unknown_device.features) == 0

def test_device_serialization():
    """Test device serialization and deserialization"""
    # Create a device
    original_device = Device(
        id="abc123",
        name="Kitchen Plug",
        generation=DeviceGeneration.GEN1,
        raw_type="SHPLG-S",
        ip_address="192.168.1.100",
        mac_address="AA:BB:CC:DD:EE:FF",
        status=DeviceStatus.ONLINE,
        firmware_version="1.0.0",
        wifi_ssid="MyWiFi",
        cloud_enabled=True
    )
    
    # Convert to dict
    device_dict = original_device.to_dict()
    
    # Create new device from dict
    restored_device = Device.from_dict(device_dict)
    
    # Verify properties
    assert restored_device.id == original_device.id
    assert restored_device.name == original_device.name
    assert restored_device.device_name == original_device.device_name
    assert restored_device.device_type == original_device.device_type
    assert restored_device.generation == original_device.generation
    assert restored_device.status == original_device.status
    assert restored_device.features == original_device.features 