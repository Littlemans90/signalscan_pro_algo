"""
SignalScan PRO - Main Entry Point
US Stock Market Momentum & Volatility Scanner
"""

import sys
import signal
import time
from core.file_manager import FileManager
from core.logger import Logger
from config.settings import SETTINGS
from config.api_keys import validate_api_keys
from scanners import (
    Tier1Alpaca,
    AlpacaValidator,
    TradierCategorizer,
    NewsAggregator,
    NasdaqHaltScanner
)


class SignalScanPRO:
    def __init__(self):
        # Initialize core systems
        self.file_manager = FileManager()
        self.logger = Logger()
        
        # Initialize scanners
        self.tier1 = None
        self.tier2 = None
        self.tier3 = None
        self.news = None
        self.halts = None
        
    def start(self):
        """Start SignalScan PRO"""
        print("=" * 60)
        print("SignalScan PRO - US Stock Market Scanner")
        print("=" * 60)
        print()
        
        # Phase 1: Foundation
        print("[INIT] Starting SignalScan PRO...\n")
        
        print("[FILE-MANAGER] Initializing data directories...")
        self.file_manager.init_directories()
        
        print("\n[LOGGER] Setting up logging system...")
        self.logger.scanner("[INIT] SignalScan PRO starting...")
        
        print("\n[CONFIG] Loading channel rules...")
        for channel in SETTINGS['channels']:
            print(f"  OK {channel['name']}")
        
        print("\n[API-KEYS] Checking API credentials...")
        if not validate_api_keys():
            print("[ERROR] Missing required API keys. Check .env file.")
            sys.exit(1)
        print("[API-KEYS] OK All required API keys loaded")
        
        print("\n" + "=" * 60)
        print("PHASE 1 STATUS: Foundation Complete OK")
        print("=" * 60)
        print()
        print("OK File system initialized")
        print("OK Configuration loaded")
        print("OK Logging system active")
        print("OK API keys verified")
        
        # Phase 2: Data Pipeline
        print("\n" + "=" * 60)
        print("PHASE 2: Starting Data Pipeline")
        print("=" * 60)
        print()
        
        # Start Tier 1: Alpaca Prefilter
        print("[TIER1] Starting Alpaca prefilter (6:30 AM, 9:30 AM, 1:30 PM EST)...")
        self.tier1 = Tier1Alpaca(self.file_manager, self.logger)
        self.tier1.start()
        
        # Start Tier 2: Alpaca Validator
        print("[TIER2] Starting Alpaca validator (WebSocket - always open)...")
        self.tier2 = AlpacaValidator(self.file_manager, self.logger)
        self.tier2.start()
        
        # Start Tier 3: Tradier Categorizer
        print("[TIER3] Starting Tradier categorizer (WebSocket - always open)...")
        self.tier3 = TradierCategorizer(self.file_manager, self.logger)
        self.tier3.start()
        
        # Start News Aggregator
        print("[NEWS] Starting news aggregator (Alpaca WS + rotating secondary)...")
        self.news = NewsAggregator(self.file_manager, self.logger)
        self.news.start()
        
        # Start NASDAQ Halt Scanner
        print("[HALTS] Starting NASDAQ halt scanner (every 30 seconds)...")
        self.halts = NasdaqHaltScanner(self.file_manager, self.logger)
        self.halts.start()
        
        print("\n" + "=" * 60)
        print("PHASE 2 STATUS: Data Pipeline Active OK")
        print("=" * 60)
        print()
        print("OK Tier 1: Alpaca prefilter running")
        print("OK Tier 2: Alpaca validator connected")
        print("OK Tier 3: Tradier categorizer connected")
        print("OK News aggregation active")
        print("OK NASDAQ halt scanner active")
        print()
        print("Scanner is now running. Press Ctrl+C to stop.")
        print("=" * 60)
        
        # Phase 3: Launch GUI
        print("\n" + "=" * 60)
        print("PHASE 3: Starting GUI")
        print("=" * 60)
        print()
        
        from PyQt5.QtWidgets import QApplication
        from gui.main_window import MainWindow
        
        print("[GUI] Initializing Qt application...")
        app = QApplication(sys.argv)
        
        print("[GUI] Creating main window...")
        window = MainWindow(
            file_manager=self.file_manager,
            logger=self.logger,
            tier1=self.tier1,
            tier3=self.tier3,
        )
        
        print("[GUI] Showing main window...")
        window.show()
        
        print("\n" + "=" * 60)
        print("PHASE 3 STATUS: GUI Active OK")
        print("=" * 60)
        print("\nScanner GUI is now running. Close window or press Ctrl+C to stop.")
        print("=" * 60)
        
        # Start Qt event loop
        try:
            sys.exit(app.exec_())
        except KeyboardInterrupt:
            self.stop()
            
    def stop(self):
        """Stop all scanners"""
        print("\n\n[SHUTDOWN] Stopping SignalScan PRO...")
        
        if self.tier1:
            self.tier1.stop()
            
        if self.tier2:
            self.tier2.stop()
            
        if self.tier3:
            self.tier3.stop()
            
        if self.news:
            self.news.stop()
            
        if self.halts:
            self.halts.stop()
            
        print("[SHUTDOWN] OK All scanners stopped")
        print("=" * 60)


if __name__ == '__main__':
    scanner = SignalScanPRO()
    scanner.start()
