#!/usr/bin/env python3
"""Test script for Shelly group operations using the CLI interface."""

import os
import argparse
import subprocess
import logging
import time
from pathlib import Path
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('group_cli_test.log')
    ]
)
logger = logging.getLogger('group_cli_test')

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent))

# Command template
CLI_CMD = 'python -m src.shelly_manager.interfaces.cli.main groups operate {action} {group} {debug}'


def run_command(cmd):
    """Run a shell command and return the output."""
    logger.info(f"Running command: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"Command failed with exit code {result.returncode}")
            logger.error(f"Error output: {result.stderr}")
        else:
            logger.info(f"Command completed successfully")
            
        # Return both stdout and stderr
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return "", str(e), -1


def test_group_operations(group_name, debug=False, delay=3):
    """
    Test basic group operations through the CLI.
    
    Args:
        group_name: Name of the group to test
        debug: Whether to run in debug mode
        delay: Delay between operations in seconds
    """
    debug_flag = "--debug" if debug else ""
    results = []
    
    # Operation sequence: status, on, off, toggle
    operations = [
        ("status", "Getting status"),
        ("on", "Turning devices on"),
        ("off", "Turning devices off"),
        ("toggle", "Toggling devices")
    ]
    
    for action, description in operations:
        logger.info(f"--- {description} ---")
        cmd = CLI_CMD.format(
            action=action,
            group=group_name,
            debug=debug_flag
        )
        
        stdout, stderr, exitcode = run_command(cmd)
        results.append({
            "operation": action,
            "success": exitcode == 0,
            "output": stdout,
            "error": stderr
        })
        
        logger.info(f"Command output:\n{stdout}")
        if stderr:
            logger.warning(f"Command error output:\n{stderr}")
            
        logger.info(f"Waiting {delay} seconds before next operation...")
        time.sleep(delay)
    
    # Print summary
    logger.info("--- OPERATION SUMMARY ---")
    for result in results:
        status = "SUCCESS" if result["success"] else "FAILED"
        logger.info(f"{result['operation']}: {status}")


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Test group operations through the CLI")
    parser.add_argument("--group", "-g", required=True, help="Name of the group to test")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode")
    parser.add_argument("--delay", "-w", type=int, default=3, help="Delay between operations in seconds")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        test_group_operations(args.group, args.debug, args.delay)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.exception(f"Error during test: {e}") 