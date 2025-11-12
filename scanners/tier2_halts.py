"""
SignalScan PRO - Tier 2: NASDAQ Halt Scanner
Fetches live trading halts from NASDAQ Trader RSS feed
Updates active_halts.json every 30 seconds
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from threading import Thread, Event
import time
from core.file_manager import FileManager
from core.logger import Logger


class NasdaqHaltScanner:
    def __init__(self, file_manager: FileManager, logger: Logger):
        self.fm = file_manager
        self.log = logger
        self.stop_event = Event()
        self.thread = None
        
        # NASDAQ halt RSS feed
        self.halt_feed_url = "http://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
        
        # Track active halts
        self.active_halts = {}
        
    def start(self):
        """Start halt scanner"""
        self.log.halt("[TIER2-HALTS] Starting NASDAQ halt scanner")
        self.stop_event.clear()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop halt scanner"""
        self.log.halt("[TIER2-HALTS] Stopping halt scanner")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
            
    def _run_loop(self):
        """Main loop: fetch halts every 30 seconds"""
        while not self.stop_event.is_set():
            try:
                self._fetch_halts()
                time.sleep(30)
            except Exception as e:
                self.log.crash(f"[TIER2-HALTS] Error in halt loop: {e}")
                time.sleep(30)
                
    def _fetch_halts(self):
        """Fetch and parse NASDAQ halt RSS feed"""
        try:
            response = requests.get(self.halt_feed_url, timeout=10)
            response.raise_for_status()
            
            # Parse XML with namespace
            root = ET.fromstring(response.content)
            ns = {'ndaq': 'http://www.nasdaqtrader.com/'}
            
            new_halts = 0
            resumed = 0
            
            for item in root.findall(".//item"):
                try:
                    # Extract from NASDAQ namespace tags
                    symbol_elem = item.find('ndaq:IssueSymbol', ns)
                    halt_date_elem = item.find('ndaq:HaltDate', ns)
                    halt_time_elem = item.find('ndaq:HaltTime', ns)
                    reason_elem = item.find('ndaq:ReasonCode', ns)
                    resume_date_elem = item.find('ndaq:ResumptionDate', ns)
                    resume_time_elem = item.find('ndaq:ResumptionTime', ns)
                    
                    if symbol_elem is None or not symbol_elem.text:
                        continue
                        
                    symbol = symbol_elem.text.strip()
                    halt_time = halt_time_elem.text.strip() if halt_time_elem is not None and halt_time_elem.text else ''
                    reason = reason_elem.text.strip() if reason_elem is not None and reason_elem.text else 'Unknown'
                    resume_time = resume_time_elem.text.strip() if resume_time_elem is not None and resume_time_elem.text else ''
                    
                    # Determine status
                    is_resumed = bool(resume_time)
                    
                    if not is_resumed:
                        # New halt
                        if symbol not in self.active_halts:
                            self.active_halts[symbol] = {
                                'symbol': symbol,
                                'status': 'Halted',
                                'halt_time': halt_time,
                                'resume_time': None,
                                'reason': reason,
                                'price': 0,
                                'last_update': datetime.utcnow().isoformat()
                            }
                            new_halts += 1
                            self.log.halt(f"[TIER2-HALTS] NEW HALT: {symbol} - {reason}")
                    else:
                        # Resumed
                        if symbol in self.active_halts:
                            self.active_halts[symbol]['status'] = 'Resumed'
                            self.active_halts[symbol]['resume_time'] = resume_time
                            self.active_halts[symbol]['last_update'] = datetime.utcnow().isoformat()
                            self.log.halt(f"[TIER2-HALTS] RESUMED: {symbol}")
                            del self.active_halts[symbol]
                            resumed += 1
                
                except Exception as e:
                    self.log.crash(f"[TIER2-HALTS] Error parsing halt item: {e}")
                    continue
            
            # Save active halts
            self._save_active_halts()
            
            if new_halts > 0 or resumed > 0:
                self.log.halt(f"[TIER2-HALTS] Update: {new_halts} new, {resumed} resumed, {len(self.active_halts)} active")
            
        except Exception as e:
            self.log.crash(f"[TIER2-HALTS] Error fetching halts: {e}")
            
    def _save_active_halts(self):
        """Save active halts to active_halts.json"""
        try:
            self.fm.save_active_halts(self.active_halts)
        except Exception as e:
            self.log.crash(f"[TIER2-HALTS] Error saving active halts: {e}")
