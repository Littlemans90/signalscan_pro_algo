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
        """Main loop: fetch halts every 60 seconds, cleanup at midnight"""
        last_cleanup_day = None
        
        while not self.stop_event.is_set():
            try:
                # Check if it's a new day and run cleanup
                import pytz
                est = pytz.timezone('US/Eastern')
                now_est = datetime.now(est)
                current_day = now_est.date()
                
                if last_cleanup_day != current_day and now_est.hour == 0:
                    self._daily_cleanup()
                    last_cleanup_day = current_day
                
                # Regular fetch
                self._fetch_halts()
                time.sleep(60)
            except Exception as e:
                self.log.crash(f"[TIER2-HALTS] Error in halt loop: {e}")
                time.sleep(60)
                
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
                    
                    # Combine date + time into ISO format
                    halt_date_str = halt_date_elem.text.strip() if halt_date_elem is not None and halt_date_elem.text else ''
                    halt_time_str = halt_time_elem.text.strip() if halt_time_elem is not None and halt_time_elem.text else ''
                    resume_date_str = resume_date_elem.text.strip() if resume_date_elem is not None and resume_date_elem.text else ''
                    resume_time_str = resume_time_elem.text.strip() if resume_time_elem is not None and resume_time_elem.text else ''
                    
                    # Convert to ISO datetime format
                    halt_time = self._parse_nasdaq_datetime(halt_date_str, halt_time_str)
                    resume_time = self._parse_nasdaq_datetime(resume_date_str, resume_time_str)
                    # DEBUG: Log resume data
                    if resume_date_str or resume_time_str:
                        self.log.halt(f"[TIER2-HALTS-DEBUG] {symbol} has resume  date='{resume_date_str}', time='{resume_time_str}', parsed={resume_time}")
                    
                    # Skip halts not from today
                    if halt_time:
                        try:
                            import pytz
                            halt_dt = datetime.fromisoformat(halt_time)
                            est = pytz.timezone('US/Eastern')
                            now_est = datetime.now(est)
                            today_start = now_est.replace(hour=0, minute=0, second=0, microsecond=0)
                            halt_dt_est = halt_dt.astimezone(est) if halt_dt.tzinfo else est.localize(halt_dt)
                            
                            # Debug logging
                            days_old = (now_est - halt_dt_est).days
                            self.log.halt(f"[TIER2-HALTS] {symbol}: halt_time={halt_dt_est.strftime('%Y-%m-%d %H:%M')}, days_old={days_old}")
                            
                            if halt_dt_est < today_start:
                                self.log.halt(f"[TIER2-HALTS] SKIPPING {symbol} - {days_old} days old")
                                continue
                        except Exception as e:
                            self.log.crash(f"[TIER2-HALTS] ERROR filtering {symbol}: {e}")
                            continue

                    reason = reason_elem.text.strip() if reason_elem is not None and reason_elem.text else 'Unknown'
                    
                    # Determine status - only count as resumed if resume_time is AFTER halt_time
                    is_resumed = False
                    if resume_time and halt_time:
                        try:
                            resume_dt = datetime.fromisoformat(resume_time)
                            halt_dt = datetime.fromisoformat(halt_time)
                            # Only resumed if resume time is after halt time
                            is_resumed = resume_dt > halt_dt
                        except Exception:
                            is_resumed = bool(resume_time)
                    elif resume_time:
                        is_resumed = True
                    
                    if not is_resumed:
                        # New halt - always overwrite even if previously resumed
                        if symbol not in self.active_halts or self.active_halts[symbol]['status'] == 'Resumed':
                            # New halt or re-halt after resume
                            if symbol in self.active_halts and self.active_halts[symbol]['status'] == 'Resumed':
                                self.log.halt(f"[TIER2-HALTS] RE-HALT: {symbol} was resumed, now halted again - {reason}")
                            else:
                                self.log.halt(f"[TIER2-HALTS] NEW HALT: {symbol} - {reason}")
                            
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
                    else:
                        # Resumed
                        if symbol in self.active_halts:
                            # Update existing halt to resumed
                            if self.active_halts[symbol]['status'] == 'Halted':
                                # Use current time as resume time (NASDAQ doesn't provide it)
                                import pytz
                                est = pytz.timezone('US/Eastern')
                                actual_resume_time = datetime.now(est).isoformat()
                                
                                self.active_halts[symbol]['status'] = 'Resumed'
                                self.active_halts[symbol]['resume_time'] = actual_resume_time
                                self.active_halts[symbol]['last_update'] = datetime.utcnow().isoformat()
                                self.log.halt(f"[TIER2-HALTS] RESUMED: {symbol} at {actual_resume_time}")
                                resumed += 1
                        else:
                            # Add resumed halt that we missed (halted before scanner started)
                            import pytz
                            est = pytz.timezone('US/Eastern')
                            actual_resume_time = datetime.now(est).isoformat()
                            
                            self.active_halts[symbol] = {
                                'symbol': symbol,
                                'status': 'Resumed',
                                'halt_time': halt_time,
                                'resume_time': actual_resume_time,
                                'reason': reason,
                                'price': 0,
                                'last_update': datetime.utcnow().isoformat()
                            }
                            self.log.halt(f"[TIER2-HALTS] RESUMED (HISTORICAL): {symbol}")
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
    
    def _parse_nasdaq_datetime(self, date_str, time_str):
        """Convert NASDAQ date (MM/DD/YYYY) + time (HH:MM:SS) to ISO format"""
        if not date_str:
            return None
        try:
            import pytz
            # If no time provided, use 00:00:00
            if not time_str:
                time_str = '00:00:00'
            # Parse MM/DD/YYYY HH:MM:SS
            dt_naive = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %H:%M:%S")
            # NASDAQ sends times in EST - localize as EST
            est = pytz.timezone('US/Eastern')
            dt_est = est.localize(dt_naive)
            # Return ISO format with timezone
            return dt_est.isoformat()
        except Exception:
            return None

    def _cleanup_old_halts(self):
        """Remove halts not from today (current trading day)"""
        from datetime import datetime
        import pytz
        
        # Get current date in EST (market time)
        est = pytz.timezone('US/Eastern')
        now_est = datetime.now(est)
        today_start = now_est.replace(hour=0, minute=0, second=0, microsecond=0)
        
        symbols_to_remove = []
        
        for symbol, halt_data in self.active_halts.items():
            halt_time_str = halt_data.get('halt_time')
            if halt_time_str:
                try:
                    # Parse ISO format halt time
                    halt_dt = datetime.fromisoformat(halt_time_str)
                    # Make timezone aware if not already
                    if halt_dt.tzinfo is None:
                        halt_dt = pytz.utc.localize(halt_dt)
                    # Convert to EST
                    halt_dt_est = halt_dt.astimezone(est)
                    
                    # Remove if not from today
                    if halt_dt_est < today_start:
                        symbols_to_remove.append(symbol)
                except Exception:
                    # If can't parse, remove it
                    symbols_to_remove.append(symbol)
        
        # Remove old halts
        for symbol in symbols_to_remove:
            del self.active_halts[symbol]
        
        if symbols_to_remove:
            self.log.halt(f"[TIER2-HALTS] Cleaned up {len(symbols_to_remove)} halts not from today")

    def _daily_cleanup(self):
        """Remove all halts from previous days at midnight EST"""
        import pytz
        from datetime import datetime, timedelta
        
        est = pytz.timezone('US/Eastern')
        now_est = datetime.now(est)
        today_start = now_est.replace(hour=0, minute=0, second=0, microsecond=0)
        
        removed = []
        for symbol in list(self.active_halts.keys()):
            halt_time_str = self.active_halts[symbol].get('halt_time')
            if halt_time_str:
                try:
                    halt_dt = datetime.fromisoformat(halt_time_str)
                    halt_dt_est = halt_dt.astimezone(est) if halt_dt.tzinfo else est.localize(halt_dt)
                    
                    # Remove if before today
                    if halt_dt_est < today_start:
                        removed.append(symbol)
                        del self.active_halts[symbol]
                except Exception:
                    pass
        
        if removed:
            self.log.halt(f"[TIER2-HALTS] MIDNIGHT CLEANUP: Removed {len(removed)} halts from previous days")
            self._save_active_halts()

    def _save_active_halts(self):
        """Save active halts to active_halts.json"""
        try:
            self.fm.save_active_halts(self.active_halts)
        except Exception as e:
            self.log.crash(f"[TIER2-HALTS] Error saving active halts: {e}")
