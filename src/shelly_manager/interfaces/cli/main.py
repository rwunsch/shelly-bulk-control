import asyncio
import logging
import os
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from ...discovery.discovery_service import DiscoveryService
from ...models.device import Device
from ...models.device_registry import device_registry
from ...utils.logging import LogConfig, get_logger
from ...config_manager.config_manager import ConfigManager
import sys
from rich.layout import Layout
from rich.spinner import Spinner
from rich.text import Text
from rich import box

# Import the groups app
from .commands.groups import app as groups_app
from .commands.parameters import app as parameters_app

# Import the capabilities command module
from .commands import capabilities

# Create Typer app
app = typer.Typer()

# Add sub-apps
app.add_typer(groups_app, name="groups", help="Manage device groups")
app.add_typer(parameters_app, name="parameters", help="Manage device parameters dynamically")
app.add_typer(capabilities.app, name="capabilities", help="Manage device capabilities and features")

# Create console for rich output
console = Console()

# Get logger for this module
logger = get_logger(__name__)

# Global discovery service instance
discovery_service = None
# Global config manager instance
config_manager = ConfigManager()

def run_async(coro):
    """Run an async function in a synchronous context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def truncate_firmware(firmware_version: str) -> str:
    """Truncate firmware version to a reasonable length for display"""
    if not firmware_version:
        return "unknown"
    if len(firmware_version) > 30:
        return firmware_version[:27] + "..."
    return firmware_version

@app.callback()
def main(debug: bool = typer.Option(False, "--debug", help="Enable debug logging")):
    """
    Shelly Manager CLI - manage and control Shelly devices
    """
    # Configure logging
    log_config = LogConfig(
        app_name="shelly_manager",
        debug=debug,
        log_to_file=True,
        log_to_console=True
    )
    log_config.setup()
    
    # Initialize device registry by loading all devices
    try:
        devices = device_registry.load_all_devices()
        if devices:
            logger.debug(f"Loaded {len(devices)} devices into registry at startup")
    except Exception as e:
        logger.error(f"Error loading device registry: {e}")
        if debug:
            import traceback
            logger.error(traceback.format_exc())

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
    
    # First try to get the device from registry
    device = device_registry.get_device(device_id)
    need_discovery = False
    
    if not device or not device.ip_address:
        need_discovery = True
        console.print("Device not found in registry or missing IP address. Starting discovery...", style="yellow")
        discovery_service = DiscoveryService(debug=debug)
    
    async def _get_settings():
        # If we need to discover devices, do that first
        if need_discovery:
            await discovery_service.start()
            await asyncio.sleep(2)  # Wait for device discovery
            
            # Try to find device by ID in discovered devices
            devices = {d.id: d for d in discovery_service.devices}
            if device_id not in devices:
                console.print(f"Device {device_id} not found", style="red")
                return None
            
            device_to_use = devices[device_id]
        else:
            # Use the device from registry
            device_to_use = device
        
        # Get settings using config manager
        await config_manager.start()
        try:
            settings = await config_manager.get_device_settings(device_to_use)
            return settings
        finally:
            await config_manager.stop()
            if need_discovery:
                await discovery_service.stop()

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
        # Also enable debug for config_manager
        logging.getLogger("shelly_manager.config_manager").setLevel(logging.DEBUG)
    
    # First try to get the device from registry
    device = device_registry.get_device(device_id)
    need_discovery = False
    
    if not device or not device.ip_address:
        need_discovery = True
        console.print("Device not found in registry or missing IP address. Starting discovery...", style="yellow")
        discovery_service = DiscoveryService(debug=debug)
    
    settings = {}
    for s in setting:
        try:
            key, value = s.split("=", 1)
            # Store as string, type conversion will happen in config_manager
            settings[key] = value
            logging.debug(f"Added setting: {key}={value}")
        except ValueError:
            console.print(f"Invalid setting format: {s}", style="red")
            raise typer.Exit(1)

    async def _set_settings():
        # If we need to discover devices, do that first
        if need_discovery:
            await discovery_service.start()
            await asyncio.sleep(2)  # Wait for device discovery
            
            # Try to find device by ID in discovered devices
            devices = {d.id: d for d in discovery_service.devices}
            if device_id not in devices:
                console.print(f"Device {device_id} not found", style="red")
                return False
            
            device_to_use = devices[device_id]
        else:
            # Use the device from registry
            device_to_use = device
        
        console.print(f"Applying settings to {device_to_use.id} ({device_to_use.ip_address}), generation: {device_to_use.generation}", style="blue")
        console.print(f"Settings to apply: {settings}", style="blue")
        
        # Apply settings using config manager
        await config_manager.start()
        try:
            success = await config_manager.apply_settings(device_to_use, settings)
            return success
        finally:
            await config_manager.stop()
            if need_discovery:
                await discovery_service.stop()

    success = run_async(_set_settings())
    if success:
        console.print("Settings updated and verified successfully", style="green bold")
    else:
        console.print("Settings were sent to the device but some settings may not have been applied correctly", style="yellow")
        console.print("Check the log file for more details", style="yellow")

if __name__ == "__main__":
    app() 