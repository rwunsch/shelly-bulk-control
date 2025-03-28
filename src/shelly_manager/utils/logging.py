import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional

class LogConfig:
    """Centralized logging configuration"""
    
    def __init__(
        self,
        app_name: str = "shelly_manager",
        log_dir: str = "logs",
        debug: bool = False,
        log_to_file: bool = True,
        log_to_console: bool = True,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5
    ):
        self.app_name = app_name
        self.log_dir = log_dir
        self.debug = debug
        self.log_to_file = log_to_file
        self.log_to_console = log_to_console
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        
        # Create logs directory if it doesn't exist
        if log_to_file:
            os.makedirs(log_dir, exist_ok=True)
    
    def setup(self):
        """Configure logging for the application"""
        # Get the root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        
        # Remove any existing handlers
        root_logger.handlers = []
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # File handler with daily rotation
        if self.log_to_file:
            # Create filename with current date
            current_date = datetime.now().strftime("%Y%m%d")
            log_file = os.path.join(
                self.log_dir,
                f"{self.app_name}_{current_date}.log"
            )
            
            # Use TimedRotatingFileHandler for daily rotation
            file_handler = logging.handlers.TimedRotatingFileHandler(
                log_file,
                when='midnight',
                interval=1,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG if self.debug else logging.INFO)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        
        # Console handler
        if self.log_to_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)  # Console always shows INFO and above
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # Log startup information
        root_logger.info(f"Logging configured for {self.app_name}")
        root_logger.info(f"Debug mode: {self.debug}")
        root_logger.info(f"Log directory: {os.path.abspath(self.log_dir)}")
        if self.log_to_file:
            root_logger.info(f"Log files will be rotated daily")
            root_logger.info(f"Keeping {self.backup_count} backup files")

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name) 