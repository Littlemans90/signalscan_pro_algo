# core/logger.py

import logging
import os
from datetime import datetime

class Logger:
    """
    Centralized logging system for SignalScan PRO
    Creates separate log files for different components
    """
    
    def __init__(self):
        self.logs_dir = "logs"
        
        # Ensure logs directory exists
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
        
        # Define log files
        today = datetime.now().strftime('%Y%m%d')
        self.log_files = {
            'scanner': os.path.join(self.logs_dir, f'scanner_debug_{today}.log'),
            'news': os.path.join(self.logs_dir, f'news_debug_{today}.log'),
            'halt': os.path.join(self.logs_dir, f'halt_debug_{today}.log'),
            'crash': os.path.join(self.logs_dir, f'crash_log_{today}.log')
        }
        
        # Log initialization
        for log_type, log_path in self.log_files.items():
            print(f"[LOGGER] Logging {log_type} to: {log_path}")
    
    def _setup_loggers(self):
        """Set up loggers for different components"""
        date_str = datetime.now().strftime('%Y%m%d')
        
        # Define log files
        log_files = {
            'scanner': f"scanner_debug_{date_str}.log",
            'news': f"news_debug_{date_str}.log",
            'halt': f"halt_debug_{date_str}.log",
            'crash': f"crash_log_{date_str}.log"
        }
        
        # Create logger for each component
        for name, filename in log_files.items():
            logger = logging.getLogger(name)
            logger.setLevel(logging.DEBUG)
            
            # File handler
            file_path = os.path.join(self.LOGS_DIR, filename)
            file_handler = logging.FileHandler(file_path)
            file_handler.setLevel(logging.DEBUG)
            
            # Format
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            # Add handler
            logger.addHandler(file_handler)
            
            self.loggers[name] = logger
            print(f"[LOGGER] Logging {name} to: {file_path}")
    
    def get_logger(self, name: str):
        """Get logger by name"""
        return self.loggers.get(name, self.loggers.get('scanner'))
    
    def log_crash(self, error: Exception, context: str = ""):
        """Log crash to dedicated crash log"""
        crash_logger = self.loggers.get('crash')
        if crash_logger:
            crash_logger.error(f"CRASH - {context}: {str(error)}", exc_info=True)

    def scanner(self, message: str):
        """Log scanner activity"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.log_files['scanner'], 'a') as f:
            f.write(log_entry)
        
        print(message)
    
    def news(self, message: str):
        """Log news activity"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.log_files['news'], 'a') as f:
            f.write(log_entry)
        
        print(message)
    
    def halt(self, message: str):
        """Log halt activity"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        with open(self.log_files['halt'], 'a') as f:
            f.write(log_entry)
        
        print(message)
    
    def crash(self, message: str):
        """Log errors and crashes"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] ERROR: {message}\n"
        
        with open(self.log_files['crash'], 'a') as f:
            f.write(log_entry)
        
        print(f"[ERROR] {message}")

# Singleton instance
logger_system = Logger()