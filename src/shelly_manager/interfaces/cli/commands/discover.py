"""CLI command for discovering Shelly devices."""

import click
from shelly_manager.discovery.discovery_service import DiscoveryService
from shelly_manager.utils.logging import get_logger, setup_logging
from shelly_manager.utils.network import get_default_network
from rich.table import Table
from rich.console import Console

# Get logger for this module
logger = get_logger(__name__)

@click.option('--network', help='Network to scan in CIDR notation (e.g. 192.168.1.0/24)')
@click.option('--force-http', is_flag=True, help='Force HTTP discovery even if mDNS devices are found')
@click.option('--debug', is_flag=True, help='Enable debug logging')
@click.option('--ips', help='Comma-separated list of specific IP addresses to probe')
@click.pass_context
async def discover(ctx, network, force_http, debug, ips):
    """Discover Shelly devices on the network"""
    # Configure logging
    setup_logging(debug=debug)
    
    # Create discovery service
    discovery_service = DiscoveryService()
    logger.debug(f"Discovery service initialized")
    
    ip_addresses = None
    if ips:
        # Parse comma-separated list of IPs
        ip_addresses = [ip.strip() for ip in ips.split(',')]
        logger.info(f"Will probe specific IP addresses: {ip_addresses}")

    # If no network is specified, try to detect the current network
    if not network:
        detected_network = get_default_network()
        if detected_network:
            network = detected_network
            logger.info(f"Using detected network: {network}")
        else:
            # Fallback to a common home network
            network = "192.168.1.0/24"
            logger.warning(f"Could not detect network, using default: {network}")
    
    # Start device discovery
    devices = await discovery_service.discover_devices(
        network=network,
        force_http=force_http,
        ip_addresses=ip_addresses
    ) 

    display_devices(devices)

def display_devices(devices):
    """Display discovered devices in a table"""
    if devices:
        # Create the table with standard style
        table = Table(title="Found devices", show_header=True, header_style="bold")
        
        # Add core columns
        table.add_column("Name", no_wrap=True)
        table.add_column("Type", no_wrap=True)
        table.add_column("Model", no_wrap=True)
        table.add_column("Generation", no_wrap=True)
        table.add_column("IP Address", no_wrap=True)
        table.add_column("MAC Address", no_wrap=True)
        table.add_column("Firmware", no_wrap=True)
        table.add_column("Discovery Method", no_wrap=True)
        
        # Add data
        for device in devices:
            table.add_row(
                device.name or "",
                device.raw_type or "",
                device.model or "",
                device.generation.value,
                device.ip_address,
                device.mac_address,
                device.firmware_version or "",
                device.discovery_method
            )
        
        # Create console for rich output
        console = Console()
        
        # Print the table
        console.print("\n")
        console.print(table)
        
        # Print additional information with regular print
        print("\nAdditional Device Information:")
        
        for device in devices:
            name_display = device.name if device.name else "Unknown Device"
            print(f"\n  Device: {name_display} ({device.ip_address})")
            print(f"  • Update Available: {'Yes' if device.has_update else 'No'}")
            print(f"  • Eco Mode Enabled: {'Yes' if device.eco_mode_enabled else 'No'}")
    else:
        logger.info("No devices found") 