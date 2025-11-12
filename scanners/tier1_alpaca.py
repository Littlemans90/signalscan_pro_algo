"""
SignalScan PRO - Tier 1: Alpaca Prefilter

Fetches bulk snapshots from Alpaca, filters US stocks by volume/price
Saves to data/prefilter.json
Runs 3x daily: 6:30 AM, 9:30 AM, 1:30 PM EST
"""

import json
import time
from datetime import datetime
from pathlib import Path
from threading import Thread, Event
import pytz
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockSnapshotRequest
from config.api_keys import API_KEYS
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import timedelta


class Tier1Alpaca:
    def __init__(self, file_manager, logger):
        self.file_manager = file_manager
        self.log = logger
        self.master_registry_path = Path('master_registry.json')
        
        # Scan times (EST): 6:30 AM, 9:30 AM, 1:30 PM
        self.scan_times = ["06:30", "09:30", "13:30"]
        
        # Initialize Alpaca data client
        self.data_client = StockHistoricalDataClient(
            API_KEYS['ALPACA_API_KEY'],
            API_KEYS['ALPACA_SECRET_KEY']
        )
        
        # Threading support
        self.stop_event = Event()
        self.thread = None

    def load_master_tickers(self):
        """Load all tickers from master_registry.json"""
        try:
            if not self.master_registry_path.exists():
                self.log.crash(f"[TIER1-ALPACA] master_registry.json not found")
                return []
        
            with open(self.master_registry_path, 'r') as f:
                data = json.load(f)
        
            # Extract ticker symbols from the "tickers" object
            # Filter out preferred stocks (symbols with $)
            all_tickers = list(data.get('tickers', {}).keys())
            tickers = [t for t in all_tickers if '$' not in t]
        
            self.log.scanner(f"[TIER1-ALPACA] Loaded {len(tickers)} common stock tickers (filtered {len(all_tickers) - len(tickers)} preferred stocks)")
            return tickers
        except Exception as e:
            self.log.crash(f"[TIER1-ALPACA] Error loading master_registry.json: {e}")
            return []

    def calculate_avg_volumes(self, symbols):
        """
        Calculate 30-day average volume for all symbols
        Returns dict: {symbol: avg_volume}
        """
        self.log.scanner(f"[TIER1-ALPACA] Calculating 30-day average volumes for {len(symbols)} symbols...")
    
        avg_volumes = {}
        batch_size = 60
    
        # Process in batches
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(symbols) + batch_size - 1) // batch_size
        
            try:
                # Get 30 days of historical bars
                request = StockBarsRequest(
                    symbol_or_symbols=batch,
                    timeframe=TimeFrame.Day,
                    start=datetime.now() - timedelta(days=30),
                    end=datetime.now()
                )
                bars = self.data_client.get_stock_bars(request)
                # Debug: Log what was returned
                bars_dict = bars.data if hasattr(bars, 'data') else bars
                self.log.scanner(f"[TIER1-ALPACA-DEBUG] Batch {batch_num} - bars type: {type(bars)}, symbol count: {len(bars_dict) if bars_dict else 0}")
                
                # Access .data attribute if BarSet, otherwise use dict directly
                bars_dict = bars.data if hasattr(bars, 'data') else bars

                for symbol, symbol_bars in bars_dict.items():
                    if symbol_bars and len(symbol_bars) > 0:
                        total_volume = sum([bar.volume for bar in symbol_bars])
                        avg_volumes[symbol] = total_volume / len(symbol_bars)

                self.log.scanner(f"[TIER1-ALPACA] Avg volume batch {batch_num}/{total_batches}: {len(avg_volumes)} calculated")
            
                # Breather between batches
                time.sleep(0.5)
            
            except Exception as e:
                self.log.crash(f"[TIER1-ALPACA] Error calculating avg volume batch {batch_num}: {e}")
                continue
    
        self.log.scanner(f"[TIER1-ALPACA] OK Calculated average volumes for {len(avg_volumes)} symbols")
        return avg_volumes

    def filter_tickers_with_volumes(self, symbols, avg_volumes):
        """
        Filter tickers by:
        - AverageVolume > 5M (30-day average)
        - Price > $.45
        - Price < $17.00
    
        Uses pre-calculated avg_volumes to avoid recalculating
        """
        filtered = []
        total = len(symbols)
        batch_size = 75
        self.log.scanner(f"[TIER1-ALPACA] Starting filter on {total} symbols (batches of {batch_size})...")

        # Process in batches of 75
        for i in range(0, len(symbols), batch_size):
            if self.stop_event.is_set():
                break
            
            batch = symbols[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(symbols) + batch_size - 1) // batch_size
        
            try:
                # Fetch snapshots for batch
                request = StockSnapshotRequest(symbol_or_symbols=batch)
                snapshots = self.data_client.get_stock_snapshot(request)
            
                for symbol, snapshot in snapshots.items():
                    try:
                        # Get price and volume from daily bar
                        if not snapshot.daily_bar:
                            continue
                            
                        price = snapshot.daily_bar.close
                    
                        # Get 30-day average volume
                        avg_volume = avg_volumes.get(symbol, 0)
                    
                        # Apply filters (using average volume, not today's volume)
                        if avg_volume > 3_000_000 and 0.50 < price < 10.00:
                            filtered.append(symbol)

                    except Exception as e:
                        # Skip problematic symbols
                        continue
            
                self.log.scanner(f"[TIER1-ALPACA] Batch {batch_num}/{total_batches}: {len(filtered)} passed so far")
            
                # Breather between batches (0.5 seconds)
                time.sleep(0.5)
        
            except Exception as e:
                self.log.crash(f"[TIER1-ALPACA] Error in batch {batch_num}: {e}")
                continue
    
        self.log.scanner(f"[TIER1-ALPACA] OK Filtered: {len(filtered)}/{total} symbols passed")
        return filtered
    
    def force_scan(self):
        """Force an immediate prefilter scan."""
        self.log.scanner("[TIER1-ALPACA] Force scan triggered by GUI")
        self.run_scan()

    def run_scan(self):
        """Run single scan cycle"""
        self.log.scanner("[TIER1-ALPACA] Starting prefilter scan...")
    
        # Load symbols from master_registry.json
        symbols = self.load_master_tickers()
        if not symbols:
            self.log.crash("[TIER1-ALPACA] No symbols to scan")
            return
    
        # Calculate 30-day average volumes for all symbols
        avg_volumes = self.calculate_avg_volumes(symbols)
    
        # Filter symbols
        filtered = self.filter_tickers_with_volumes(symbols, avg_volumes)
    
        # Save to prefilter.json WITH volume_avg
        prefilter_data = [
            {'symbol': sym, 'volume_avg': avg_volumes.get(sym, 0)} 
            for sym in filtered
        ]
        self.file_manager.save_prefilter(prefilter_data)
        self.log.scanner(f"[TIER1-ALPACA] OK Saved {len(filtered)} symbols with volume_avg to prefilter.json")

    def start(self):
        """Start prefilter scanner (runs 3x daily at scheduled times)"""
        self.log.scanner("[TIER1-ALPACA] Starting prefilter scanner (6:30 AM, 9:30 AM, 1:30 PM EST)")
        self.stop_event.clear()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        """Background thread loop - runs at scheduled times"""
        est = pytz.timezone('America/New_York')
        
        # Run first scan immediately on startup
        self.log.scanner("[TIER1-ALPACA] Running initial scan...")
        self.run_scan()
        
        while not self.stop_event.is_set():
            try:
                # Get current time in EST
                now_est = datetime.now(est)
                current_time = now_est.strftime("%H:%M")
                
                # Check if it's time to scan
                if current_time in self.scan_times:
                    self.log.scanner(f"[TIER1-ALPACA] Scheduled scan triggered: {current_time} EST")
                    self.run_scan()
                    # Sleep for 61 seconds to avoid running same scan twice in same minute
                    time.sleep(61)
                else:
                    # Check every 30 seconds
                    time.sleep(30)
            
            except Exception as e:
                self.log.crash(f"[TIER1-ALPACA] Error in scan loop: {e}")
                time.sleep(60)

    def stop(self):
        """Stop the scanner"""
        self.log.scanner("[TIER1-ALPACA] Stopping prefilter scanner")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
