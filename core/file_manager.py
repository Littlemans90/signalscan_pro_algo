# core/file_manager.py

import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

class FileManager:
    """
    Handles all JSON file operations for SignalScan PRO
    - Load/save JSON files
    - Create directories
    - Backup system
    - Daily reset logic
    """
    
    def __init__(self):
        # Define all file paths
        self.DATA_DIR = "data"
        self.LOGS_DIR = "logs"
        self.BACKUP_DIR = os.path.join(self.DATA_DIR, "backups")
        
        self.files = {
            'prefilter': os.path.join(self.DATA_DIR, 'prefilter.json'),
            'validated': os.path.join(self.DATA_DIR, 'validated.json'),
            'news': os.path.join(self.DATA_DIR, 'news.json'),
            'bkgnews': os.path.join(self.DATA_DIR, 'bkgnews.json'),
            'halts': os.path.join(self.DATA_DIR, 'halts.json'),
            'active_halts': os.path.join(self.DATA_DIR, 'active_halts.json')
        }
        
        # Create directories if they don't exist
        self._create_directories()
        
        # Initialize empty files if they don't exist
        self._initialize_files()
    
    def _create_directories(self):
        """Create data, logs, and backup directories"""
        for directory in [self.DATA_DIR, self.LOGS_DIR, self.BACKUP_DIR]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"[FILE-MANAGER] Created directory: {directory}")
        
    def init_directories(self):
        """Public method to initialize/verify directories exist"""
        # Directories already created in __init__ via _create_directories()
        return True
    
    def _initialize_files(self):
        """Create empty JSON files if they don't exist"""
        for file_key, file_path in self.files.items():
            if not os.path.exists(file_path):
                default_data = {} if file_key != 'prefilter' and file_key != 'validated' else []
                self.save_json(file_key, default_data)
                print(f"[FILE-MANAGER] Initialized: {file_path}")
    
    def load_json(self, file_key: str, default: Any = None) -> Any:
        """
        Load JSON file by key
        
        Args:
            file_key: Key from self.files dict (e.g., 'prefilter', 'news')
            default: Default value if file doesn't exist or is invalid
        
        Returns:
            Loaded data or default value
        """
        try:
            file_path = self.files.get(file_key)
            
            if not file_path:
                #print(f"[FILE-MANAGER] ⚠️ Unknown file key: {file_key}")
                return default
            
            if not os.path.exists(file_path):
                #print(f"[FILE-MANAGER] ⚠️ File not found: {file_path}")
                return default
            
            with open(file_path, 'r') as f:
                data = json.load(f)
                #   print(f"[FILE-MANAGER] ✓ Loaded {file_key}: {len(data) if isinstance(data, (list, dict)) else 'N/A'} items")
                return data
        
        except json.JSONDecodeError as e:
            #print(f"[FILE-MANAGER] ❌ JSON decode error in {file_key}: {e}")
            return default
        
        except Exception as e:
            #print(f"[FILE-MANAGER] ❌ Error loading {file_key}: {e}")
            return default
    
    def save_json(self, file_key: str, data: Any) -> bool:
        """
        Save data to JSON file
        
        Args:
            file_key: Key from self.files dict
            data: Data to save (must be JSON-serializable)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self.files.get(file_key)
            
            if not file_path:
                #print(f"[FILE-MANAGER] ⚠️ Unknown file key: {file_key}")
                return False
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            #print(f"[FILE-MANAGER] ✓ Saved {file_key}: {len(data) if isinstance(data, (list, dict)) else 'N/A'} items")
            return True
        
        except Exception as e:
            print(f"[FILE-MANAGER] ❌ Error saving {file_key}: {e}")
            return False
    
    def backup_all(self, reason: str = "manual"):
        """
        Create timestamped backup of all data files
        
        Args:
            reason: Reason for backup (e.g., "pre-update", "daily", "manual")
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(self.BACKUP_DIR, f"{timestamp}_{reason}")
            
            os.makedirs(backup_path, exist_ok=True)
            
            backed_up = 0
            for file_key, file_path in self.files.items():
                if os.path.exists(file_path):
                    backup_file = os.path.join(backup_path, os.path.basename(file_path))
                    shutil.copy2(file_path, backup_file)
                    backed_up += 1

            #print(f"[FILE-MANAGER] ✓ Backup created: {backup_path} ({backed_up} files)")
            return backup_path
        
        except Exception as e:
            #print(f"[FILE-MANAGER] ❌ Backup error: {e}")
            return None
    
    def reset_daily_files(self):
        """
        Reset files that should be cleared at midnight:
        - bkgnews.json (breaking news)
        - halts.json (halt history)
        
        Does NOT reset:
        - news.json (persistent)
        - validated.json (persistent)
        - active_halts.json (ongoing halts persist)
        - prefilter.json (persistent)
        """
        try:
            #print("[FILE-MANAGER] Starting midnight reset...")
            
            # Backup before reset
            self.backup_all(reason="pre_midnight_reset")
            
            # Clear breaking news
            self.save_json('bkgnews', {})
            #print("[FILE-MANAGER] ✓ Cleared bkgnews.json")
            
            # Clear halt history
            self.save_json('halts', {})
            #print("[FILE-MANAGER] ✓ Cleared halts.json")

            #print("[FILE-MANAGER] ✓ Midnight reset complete")
            return True
        
        except Exception as e:
            #print(f"[FILE-MANAGER] ❌ Midnight reset error: {e}")
            return False
    
    def get_file_path(self, file_key: str) -> Optional[str]:
        """Get absolute file path by key"""
        return self.files.get(file_key)
    
    def file_exists(self, file_key: str) -> bool:
        """Check if file exists"""
        file_path = self.files.get(file_key)
        return os.path.exists(file_path) if file_path else False
    
    def get_file_size(self, file_key: str) -> int:
        """Get file size in bytes"""
        try:
            file_path = self.files.get(file_key)
            if file_path and os.path.exists(file_path):
                return os.path.getsize(file_path)
            return 0
        except Exception:
            return 0

    def load_prefilter(self) -> list:
        """Load prefilter symbols"""
        return self.load_json('prefilter', default=[])
    
    def save_prefilter(self, symbols: list):
        """Save prefilter symbols"""
        self.save_json('prefilter', symbols)
    
    def load_validated(self) -> list:
        """Load validated data"""
        return self.load_json('validated', default=[])
    
    def save_validated(self, data: list):
        """Save validated data"""
        self.save_json('validated', data)

    def load_active_halts(self) -> dict:
        """Load active halts"""
        return self.load_json('active_halts', default={})
    
    def save_active_halts(self, data: dict):
        """Save active halts"""
        self.save_json('active_halts', data)
    
    def load_halts(self) -> dict:
        """Load halt history"""
        return self.load_json('halts', default={})
    
    def save_halts(self, data: dict):
        """Save halt history"""
        self.save_json('halts', data)
    
    def load_news(self) -> dict:
        """Load general news"""
        return self.load_json('news', default={})
    
    def save_news(self, data: dict):
        """Save general news"""
        self.save_json('news', data)
    
    def load_bkgnews(self) -> dict:
        """Load breaking news"""
        return self.load_json('bkgnews', default={})
    
    def save_bkgnews(self, data: dict):
        """Save breaking news"""
        self.save_json('bkgnews', data)
        
# Singleton instance
file_manager = FileManager()