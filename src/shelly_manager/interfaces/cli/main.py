import asyncio
import logging
import os
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from ...discovery.discovery_service import DiscoveryService
from ...models.device import Device
from ...utils.logging import LogConfig, get_logger
import sys
from rich.layout import Layout
from rich.spinner import Spinner
from rich.text import Text
from rich import box

# Create Typer app
app = typer.Typer()

# Create console for rich output
console = Console()

# Get logger for this module
logger = get_logger(__name__)

# Global discovery service instance
discovery_service = None

def run_async(coro):
    """Run an async function in a synchronous context"""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)

def truncate_firmware(firmware_version: str) -> str:
    """Truncate firmware version to a reasonable length for display"""
    if not firmware_version:
        return "unknown"
    if len(firmware_version) > 30:
        return firmware_version[:27] + "..."
    return firmware_version

@app.command()
def discover(
    network: str = typer.Option(None, "--network", help="Network address to scan (CIDR notation)"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
    force_http: bool = typer.Option(False, "--force-http", help="Force HTTP probing even if mDNS devices are found"),
    ips: str = typer.Option(None, "--ips", help="Comma-separated list of specific IP addresses to probe")
):
    """Discover Shelly devices on the network"""
    try:
        # Configure logging
        log_config = LogConfig(
            app_name="shelly_manager",
            debug=debug,
            log_to_file=True,
            log_to_console=True
        )
        log_config.setup()
        
        logger.info("Starting device discovery")
        
        # Create discovery service
        discovery_service = DiscoveryService(debug=debug)
        
        # Define callback for device discovery
        def on_device_discovered(device: Device):
            # Show the correct device type based on generation
            if device.generation.value == "gen1":
                device_type = device.raw_type or "unknown"
            else:
                device_type = device.raw_app or "unknown"
            
            logger.info(f"Found device: {device.name or device.id} ({device_type})")
            logger.info(f"  IP: {device.ip_address}")
            logger.info(f"  MAC: {device.mac_address}")
            logger.info(f"  Generation: {device.generation.value}")
            logger.info(f"  Firmware: {device.firmware_version}")
            logger.info(f"  Discovery Method: {device.discovery_method}")
            logger.info("")
        
        # Add callback
        discovery_service.add_callback(on_device_discovered)
        
        # Parse specific IP addresses if provided
        ip_addresses = None
        if ips:
            ip_addresses = [ip.strip() for ip in ips.split(',')]
            logger.info(f"Will probe specific IP addresses: {ip_addresses}")
        elif not network:
            # If neither network nor IPs provided, use default network
            network = "192.168.1.0/24"
            logger.info(f"No network or IPs specified, using default network: {network}")
        
        # Start discovery - using a separate asyncio function
        async def run_discovery():
            return await discovery_service.discover_devices(
                network=network, 
                force_http=force_http,
                ip_addresses=ip_addresses
            )
            
        # Run the discovery process
        devices = asyncio.run(run_discovery())
        
        if not devices:
            logger.info("No devices found.")
        else:
            logger.info(f"\nFound {len(devices)} devices:")
            
            # Create table
            table = Table(show_header=True, header_style="bold magenta", box=box.DOUBLE_EDGE)
            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Model")
            table.add_column("Generation")
            table.add_column("IP Address")
            table.add_column("MAC Address")
            table.add_column("Firmware")
            table.add_column("Updates")
            table.add_column("Eco Mode")
            table.add_column("Discovery Method")
            
            # Import needed for Text objects
            from rich.text import Text
            
            # Create colored Text objects for YES/NO values
            update_yes = Text("YES", style="green bold")
            update_no = Text("NO", style="red")
            eco_yes = Text("YES", style="green bold")
            eco_no = Text("NO", style="red")
            
            # Add devices to table
            for device in devices:
                # Determine device type based on generation
                if device.generation.value == "gen1":
                    type_display = device.raw_type or "unknown"
                else:
                    type_display = device.raw_app or "unknown"
                
                table.add_row(
                    device.name or device.id,
                    type_display,
                    device.raw_model or "unknown",
                    device.generation.value,
                    device.ip_address,
                    device.mac_address,
                    truncate_firmware(device.firmware_version),
                    update_yes if device.has_update else update_no,
                    eco_yes if device.eco_mode_enabled else eco_no,
                    device.discovery_method
                )
            
            # Print table
            console = Console()
            console.print(table)
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if debug:
            import traceback
            logger.error(traceback.format_exc())
        raise typer.Exit(1)

@app.command()
def get_settings(device_id: str, debug: bool = typer.Option(False, help="Enable debug logging")):
    """Get settings for a specific device"""
    global discovery_service
    
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        console.print("[yellow]Debug mode enabled[/yellow]")
    
    discovery_service = DiscoveryService(debug=debug)
    
    async def _get_settings():
        await discovery_service.start()
        await asyncio.sleep(2)  # Wait for device discovery
        
        devices = {d.id: d for d in discovery_service.devices}
        if device_id not in devices:
            console.print(f"Device {device_id} not found", style="red")
            return

        await config_manager.start()
        settings = await config_manager.get_device_settings(devices[device_id])
        await config_manager.stop()
        await discovery_service.stop()
        return settings

    settings = run_async(_get_settings())
    if settings:
        console.print_json(data=settings)

@app.command()
def set_settings(device_id: str, setting: list[str], debug: bool = typer.Option(False, help="Enable debug logging")):
    """Set settings for a specific device (format: key=value)"""
    global discovery_service
    
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
        console.print("[yellow]Debug mode enabled[/yellow]")
    
    discovery_service = DiscoveryService(debug=debug)
    
    settings = {}
    for s in setting:
        try:
            key, value = s.split("=", 1)
            settings[key] = value
        except ValueError:
            console.print(f"Invalid setting format: {s}", style="red")
            return

    async def _set_settings():
        await discovery_service.start()
        await asyncio.sleep(2)  # Wait for device discovery
        
        devices = {d.id: d for d in discovery_service.devices}
        if device_id not in devices:
            console.print(f"Device {device_id} not found", style="red")
            return

        await config_manager.start()
        success = await config_manager.apply_settings(devices[device_id], settings)
        await config_manager.stop()
        await discovery_service.stop()
        return success

    if run_async(_set_settings()):
        console.print("Settings updated successfully", style="green")
    else:
        console.print("Failed to update settings", style="red")

if __name__ == "__main__":
    app() 