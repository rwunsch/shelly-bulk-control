import asyncio
import logging
import os
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from ...discovery.discovery_service import DiscoveryService
from ...models.device import Device, DeviceGeneration
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

# Set up early debug detection from command line args
def configure_early_debug():
    """Configure early debug logging if --debug flag is detected in command line arguments"""
    if "--debug" in sys.argv:
        # Configure root logger immediately
        logging.basicConfig(level=logging.DEBUG)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Add a console handler for immediate output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # Enable debug for key modules
        for module in [
            "shelly_manager.config_manager",
            "shelly_manager.discovery",
            "shelly_manager.interfaces.cli",
            "shelly_manager.models",
            "shelly_manager.utils",
            "shelly_manager.parameter",
            "shelly_manager.grouping",
        ]:
            logging.getLogger(module).setLevel(logging.DEBUG)
            
        debug_logger = logging.getLogger("early_debug")
        debug_logger.debug("Early debug logging enabled via command line --debug flag")
        return True
    return False

# Enable early debug logging
early_debug_enabled = configure_early_debug()

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

def enable_full_debug_logging(debug: bool):
    """Enable comprehensive debug logging across all modules"""
    if debug:
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Make sure all module loggers have debug enabled
        for module in [
            "shelly_manager",
            "shelly_manager.config_manager",
            "shelly_manager.discovery",
            "shelly_manager.interfaces.cli",
            "shelly_manager.models",
            "shelly_manager.utils",
            "shelly_manager.parameter",
            "shelly_manager.grouping",
            "shelly_manager.services",
            "shelly_manager.state",
            "aiohttp",
        ]:
            module_logger = logging.getLogger(module)
            module_logger.setLevel(logging.DEBUG)
            logger.debug(f"Debug logging enabled for module: {module}")
            
        console.print("[yellow]Full debug mode enabled across all modules[/yellow]")
        logger.debug("Comprehensive debug logging enabled")

@app.callback()
def main(debug: bool = typer.Option(False, "--debug", help="Enable debug logging")):
    """
    Shelly Manager CLI - manage and control Shelly devices
    """
    # Check if debug was enabled early via command line
    debug = debug or "--debug" in sys.argv or early_debug_enabled
    
    # Configure logging
    log_config = LogConfig(
        app_name="shelly_manager",
        debug=debug,
        log_to_file=True,
        log_to_console=True
    )
    log_config.setup()
    
    # Enable comprehensive debug logging if requested
    if debug:
        enable_full_debug_logging(debug)
        logger.debug("Debug mode enabled in main callback")
    
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
        
        # Enable comprehensive debug if needed
        if debug:
            enable_full_debug_logging(debug)
            logger.debug("Debug mode enabled in discover command")
        
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
        # Enable comprehensive debug
        enable_full_debug_logging(debug)
        logger.debug("Debug mode enabled in get_settings command")
    
    # First try to get the device from registry
    device = device_registry.get_device(device_id)
    need_discovery = False
    
    if not device or not device.ip_address:
        need_discovery = True
        console.print("Device not found in registry or missing IP address. Starting discovery...", style="yellow")
        logger.debug(f"Device {device_id} not found in registry or missing IP. Starting discovery")
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
def set_settings(device_id: str, setting: list[str], debug: bool = typer.Option(False, help="Enable debug logging"), verbose: bool = typer.Option(False, help="Show verbose output including full settings")):
    """Set settings for a specific device (format: key=value)"""
    global discovery_service
    global config_manager
    
    if debug:
        # Configure detailed logging
        logging.basicConfig(level=logging.DEBUG)
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Add a console handler for immediate output
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        
        # Remove any existing handlers to avoid duplicates
        for handler in list(root_logger.handlers):
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                root_logger.removeHandler(handler)
        
        root_logger.addHandler(console_handler)
        
        # Enable comprehensive debug
        enable_full_debug_logging(debug)
        logger.debug("Debug mode enabled in set_settings command")
        logger.debug(f"Setting device {device_id} with values: {setting}")
    
    # First try to get the device from registry
    device = device_registry.get_device(device_id)
    need_discovery = False
    
    if not device or not device.ip_address:
        need_discovery = True
        console.print("Device not found in registry or missing IP address. Starting discovery...", style="yellow")
        logger.debug(f"Device {device_id} not found in registry or missing IP. Starting discovery")
        discovery_service = DiscoveryService(debug=debug)
    else:
        if debug:
            logger.info(f"Found device in registry: {device.id}, IP: {device.ip_address}, Gen: {device.generation}")
    
    settings = {}
    for s in setting:
        try:
            key, value = s.split("=", 1)
            # Store as string, type conversion will happen in config_manager
            settings[key] = value
            logger.debug(f"Added setting: {key}={value}")
        except ValueError:
            console.print(f"Invalid setting format: {s}", style="red")
            logger.error(f"Invalid setting format: {s}")
            raise typer.Exit(1)

    # Make sure we have a fresh ConfigManager with debug enabled if needed
    config_manager = ConfigManager()
    logger.debug("Created new ConfigManager instance")

    async def _set_settings():
        # If we need to discover devices, do that first
        if need_discovery:
            logger.debug("Starting discovery service")
            await discovery_service.start()
            await asyncio.sleep(2)  # Wait for device discovery
            
            # Try to find device by ID in discovered devices
            devices = {d.id: d for d in discovery_service.devices}
            logger.debug(f"Discovered devices: {list(devices.keys())}")
            
            if device_id not in devices:
                error_msg = f"Device {device_id} not found in discovery"
                logger.error(error_msg)
                console.print(error_msg, style="red")
                return False
            
            device_to_use = devices[device_id]
            logger.debug(f"Using discovered device: {device_to_use.id}, IP: {device_to_use.ip_address}")
        else:
            # Use the device from registry
            device_to_use = device
            logger.debug(f"Using device from registry: {device_to_use.id}, IP: {device_to_use.ip_address}")
        
        console.print(f"Applying settings to {device_to_use.id} ({device_to_use.ip_address}), generation: {device_to_use.generation}", style="blue")
        console.print(f"Settings to apply: {settings}", style="blue")
        
        # Get current settings before applying changes if debug mode is enabled
        current_settings = {}
        if debug:
            logger.info("Getting current settings before applying changes")
            await config_manager.start()
            current_settings = await config_manager.get_device_settings(device_to_use)
            
            if verbose:
                console.print("Current device settings:", style="cyan")
                import json
                console.print_json(data=current_settings)
            else:
                # Show only the settings we're about to change
                console.print("Current values of settings to be changed:", style="cyan")
                for key in settings.keys():
                    if "." in key and device_to_use.generation != DeviceGeneration.GEN1:
                        # Handle nested path
                        parts = key.split(".")
                        value = current_settings
                        for part in parts:
                            if part in value:
                                value = value[part]
                            else:
                                value = "Not found"
                                break
                        console.print(f"  {key} = {value}", style="cyan")
                    else:
                        # Direct key
                        if key in current_settings:
                            console.print(f"  {key} = {current_settings.get(key, 'Not found')}", style="cyan")
                        else:
                            console.print(f"  {key} = Not found", style="cyan")
            
            # For existing ConfigManager, continue with apply_settings
        else:
            # Apply settings using config manager
            logger.debug("Starting config manager")
            await config_manager.start()
        
        try:
            logger.debug("Calling apply_settings")
            success = await config_manager.apply_settings(device_to_use, settings)
            logger.debug(f"apply_settings result: {success}")
            
            # If in debug mode, get settings after the change and compare
            if debug:
                logger.info("Getting settings after applying changes for verification")
                after_settings = await config_manager.get_device_settings(device_to_use)
                
                if verbose:
                    console.print("Settings after applying changes:", style="cyan")
                    import json
                    console.print_json(data=after_settings)
                
                # Verify and display the changes
                console.print("Verification of changes:", style="cyan")
                all_verified = True
                
                for key, expected_value_str in settings.items():
                    # Special case for name property in GEN2 devices
                    if key == "name" and device_to_use.generation != DeviceGeneration.GEN1:
                        # For GEN2 devices, name is in sys.device.name
                        before_name = None
                        if "sys" in current_settings and "device" in current_settings["sys"]:
                            before_name = current_settings["sys"]["device"].get("name")
                        
                        after_name = None
                        if "sys" in after_settings and "device" in after_settings["sys"]:
                            after_name = after_settings["sys"]["device"].get("name")
                        
                        expected_value = expected_value_str
                        
                        if after_name == expected_value:
                            console.print(f"  [green]✓ {key}[/green]: Changed from {before_name} to {after_name}")
                        else:
                            console.print(f"  [red]✗ {key}[/red]: Expected {expected_value}, but got {after_name}", style="red")
                            all_verified = False
                        
                        # Skip the rest of the loop for this key
                        continue
                    
                    # Convert expected value string to appropriate type for comparison
                    expected_value = expected_value_str
                    if expected_value_str.lower() == 'true':
                        expected_value = True
                    elif expected_value_str.lower() == 'false':
                        expected_value = False
                    elif expected_value_str.isdigit():
                        expected_value = int(expected_value_str)
                    else:
                        try:
                            expected_value = float(expected_value_str)
                        except ValueError:
                            pass
                    
                    # For Gen2 devices, handle nested paths with dot notation
                    if "." in key and device_to_use.generation != DeviceGeneration.GEN1:
                        # Split the path
                        parts = key.split(".")
                        
                        # Get the original value if possible
                        try:
                            # Get the original value
                            orig = current_settings
                            orig_val = None
                            path_valid = True
                            for part in parts:
                                if isinstance(orig, dict) and part in orig:
                                    orig = orig[part]
                                else:
                                    path_valid = False
                                    break
                            if path_valid:
                                orig_val = orig
                            
                            # Get the new value
                            new_val = after_settings
                            new_path_valid = True
                            for part in parts:
                                if isinstance(new_val, dict) and part in new_val:
                                    new_val = new_val[part]
                                else:
                                    new_path_valid = False
                                    break
                            
                            if not new_path_valid:
                                console.print(f"  [red]✗ {key}[/red]: Path not found in device after update", style="red")
                                all_verified = False
                            elif new_val == expected_value:
                                console.print(f"  [green]✓ {key}[/green]: Changed from {orig_val} to {new_val}")
                            else:
                                console.print(f"  [red]✗ {key}[/red]: Expected {expected_value}, but got {new_val}", style="red")
                                all_verified = False
                        except Exception as e:
                            console.print(f"  [red]✗ {key}[/red]: Error checking path - {str(e)}", style="red")
                            all_verified = False
                    else:
                        # Simple direct path for Gen1
                        orig_val = current_settings.get(key, "Not found")
                        actual_val = after_settings.get(key, "Not found")
                        
                        if actual_val == "Not found":
                            console.print(f"  [red]✗ {key}[/red]: Not found in device after update", style="red")
                            all_verified = False
                        elif actual_val == expected_value:
                            console.print(f"  [green]✓ {key}[/green]: Changed from {orig_val} to {actual_val}")
                        else:
                            console.print(f"  [red]✗ {key}[/red]: Expected {expected_value}, but got {actual_val}", style="red")
                            all_verified = False
                
                if all_verified:
                    console.print("All settings were successfully verified!", style="green bold")
                else:
                    console.print("Some settings could not be verified or were not applied correctly.", style="yellow")
            
            return success
        except Exception as e:
            error_msg = f"Error applying settings: {str(e)}"
            logger.error(error_msg)
            console.print(error_msg, style="red")
            if debug:
                import traceback
                logger.error(traceback.format_exc())
            return False
        finally:
            logger.debug("Stopping config manager")
            await config_manager.stop()
            if need_discovery:
                logger.debug("Stopping discovery service")
                await discovery_service.stop()

    console.print("Sending settings to device...", style="blue")
    success = run_async(_set_settings())
    if success:
        console.print("Settings updated successfully", style="green")
        logger.info(f"Successfully updated settings for device {device_id}")
    else:
        console.print("Failed to update settings", style="red")
        logger.error(f"Failed to update settings for device {device_id}")

if __name__ == "__main__":
    app() 