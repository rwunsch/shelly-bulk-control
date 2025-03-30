"""
Network utility functions for the Shelly Manager.

This module provides functions to identify network information
across different platforms (Windows, Linux).
"""
import ipaddress
import logging
import platform
import socket
import subprocess
from typing import List, Optional, Tuple

from ..utils.logging import get_logger

logger = get_logger(__name__)

def get_default_interface() -> Optional[str]:
    """
    Get the name of the default network interface.
    
    Returns:
        Name of the default network interface, or None if it cannot be determined
    """
    system = platform.system().lower()
    
    try:
        if system == "windows":
            # On Windows, use ipconfig to find the active interface
            output = subprocess.check_output(["ipconfig"], universal_newlines=True)
            
            # Find the default interface by looking for the one with a default gateway
            for section in output.split("\n\n"):
                if "Default Gateway" in section and not "0.0.0.0" in section:
                    # Extract adapter name
                    lines = section.split("\n")
                    adapter_line = lines[0].strip()
                    if adapter_line.endswith(":"):
                        return adapter_line[:-1]  # Remove the trailing colon
        
        elif system == "linux":
            # On Linux, use ip route to find the default interface
            output = subprocess.check_output(["ip", "route"], universal_newlines=True)
            
            # Look for the default route
            for line in output.splitlines():
                if line.startswith("default"):
                    parts = line.split()
                    dev_index = parts.index("dev") if "dev" in parts else -1
                    if dev_index != -1 and dev_index + 1 < len(parts):
                        return parts[dev_index + 1]
        
        else:
            logger.warning(f"Unsupported platform: {system}")
            
    except Exception as e:
        logger.error(f"Error determining default interface: {e}")
    
    return None

def get_interface_addresses() -> List[Tuple[str, str, str]]:
    """
    Get the IP addresses, netmasks, and interface names for all network interfaces.
    
    Returns:
        List of tuples containing (interface_name, ip_address, netmask)
    """
    result = []
    system = platform.system().lower()
    
    try:
        if system == "windows":
            # On Windows, use ipconfig to get interface info
            output = subprocess.check_output(["ipconfig", "/all"], universal_newlines=True)
            
            current_interface = None
            ip_address = None
            subnet_mask = None
            
            for line in output.splitlines():
                line = line.strip()
                
                # New adapter section
                if line.endswith(":") and not line.startswith(" "):
                    # Save the previous adapter if we have an IP and mask
                    if current_interface and ip_address and subnet_mask:
                        result.append((current_interface, ip_address, subnet_mask))
                        ip_address = None
                        subnet_mask = None
                    
                    current_interface = line[:-1]  # Remove trailing colon
                
                # Look for IPv4 address
                elif "IPv4 Address" in line and ":" in line:
                    ip_address = line.split(":")[-1].strip()
                    # Remove (Preferred) suffix if present
                    if "(" in ip_address:
                        ip_address = ip_address.split("(")[0].strip()
                
                # Look for subnet mask
                elif "Subnet Mask" in line and ":" in line:
                    subnet_mask = line.split(":")[-1].strip()
            
            # Add the last interface
            if current_interface and ip_address and subnet_mask:
                result.append((current_interface, ip_address, subnet_mask))
                
        elif system == "linux":
            # On Linux, use ip addr to get interface info
            output = subprocess.check_output(["ip", "-4", "addr", "show"], universal_newlines=True)
            
            current_interface = None
            
            for line in output.splitlines():
                line = line.strip()
                
                # New interface section
                if line.startswith(tuple(str(i) for i in range(10))) and ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        current_interface = parts[1].strip().split()[0]
                
                # Look for inet line with IPv4 info
                elif line.startswith("inet ") and current_interface:
                    parts = line.split()
                    if len(parts) >= 2:
                        ip_cidr = parts[1]  # Format: IP/CIDR
                        if "/" in ip_cidr:
                            ip, cidr = ip_cidr.split("/")
                            # Convert CIDR to netmask
                            netmask = str(ipaddress.IPv4Network(f"0.0.0.0/{cidr}", strict=False).netmask)
                            result.append((current_interface, ip, netmask))
        
        else:
            logger.warning(f"Unsupported platform: {system}")
    
    except Exception as e:
        logger.error(f"Error getting interface addresses: {e}")
    
    return result

def detect_current_networks() -> List[str]:
    """
    Detect the current networks the device is connected to.
    
    Returns:
        List of networks in CIDR notation (e.g., "192.168.1.0/24")
    """
    networks = []
    
    # Get all interface addresses
    interfaces = get_interface_addresses()
    
    for interface, ip, netmask in interfaces:
        try:
            # Skip loopback or special addresses
            if ip.startswith("127.") or ip.startswith("169.254."):
                continue
                
            # Create an IPv4 address and netmask
            ip_obj = ipaddress.IPv4Address(ip)
            mask_obj = ipaddress.IPv4Address(netmask)
            
            # Calculate the network address
            # Convert IP and netmask to integers, perform bitwise AND, convert back to IPv4Address
            network_int = int(ip_obj) & int(mask_obj)
            network_addr = str(ipaddress.IPv4Address(network_int))
            
            # Calculate CIDR prefix length from netmask
            prefix_len = bin(int(mask_obj)).count('1')
            
            # Create CIDR notation
            cidr = f"{network_addr}/{prefix_len}"
            
            # Create a properly formatted network
            network = str(ipaddress.IPv4Network(cidr, strict=False))
            networks.append(network)
            
            logger.debug(f"Detected network {network} for interface {interface} (IP: {ip}, Mask: {netmask})")
            
        except Exception as e:
            logger.error(f"Error calculating network for {interface} ({ip}/{netmask}): {e}")
    
    # If we found multiple networks, prioritize common home/office networks
    if len(networks) > 1:
        for network in networks:
            if (network.startswith("192.168.") or 
                network.startswith("10.") or 
                network.startswith("172.16.")):
                # Move this network to the front of the list
                networks.remove(network)
                networks.insert(0, network)
    
    return networks

def get_default_network() -> Optional[str]:
    """
    Get the default network to scan for devices.
    
    Returns:
        Default network in CIDR notation, or None if it cannot be determined
    """
    networks = detect_current_networks()
    
    if networks:
        default_network = networks[0]
        logger.info(f"Using detected network: {default_network}")
        return default_network
    
    # Fallback to a common home network
    fallback = "192.168.1.0/24"
    logger.warning(f"Could not detect current network, using fallback: {fallback}")
    return fallback
    
def get_local_ip() -> Optional[str]:
    """
    Get the local IP address of the device.
    
    Returns:
        Local IP address, or None if it cannot be determined
    """
    try:
        # Create a socket and connect to an external server (doesn't actually connect)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Error determining local IP: {e}")
        return None 