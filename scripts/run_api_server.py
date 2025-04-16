#!/usr/bin/env python3
"""
Run the Shelly Device Manager API Server

This script serves as an entry point for the API service
"""
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from src.shelly_manager.interfaces.api.server import run_server

if __name__ == "__main__":
    run_server() 