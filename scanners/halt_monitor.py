"""
SignalScan PRO - Halt Monitor
Fetches halt data from NASDAQ API every 2.5 minutes
Tracks active halts and historical halts
"""

import requests
import json
from datetime import datetime
import time
from threading import Thread, Event
from PyQt5.QtCore import QObject, pyqtSignal
from core.file_manager import FileManager
from core.logger import Logger


class HaltMonitor(QObject):
    # PyQt5 signal for live GUI updates
    halt_signal = pyqtSignal(dict)
    
    def __init__(self, file_manager: FileManager, logger: Logger):
        super().__init__()  # Initialize QObject
        self.fm = file_manager
        self.log = logger
        self.stop_event = Event()
        self.thread = None
        
        # Fetch interval: 2.5 minutes
        self.fetch_interval = 150  # seconds
        
    def start(self):
        """Start halt monitoring"""
        self.log.halt("[HALT-MONITOR] Starting halt monitor (every 2.5 minutes)")
        self.stop_event.clear()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop halt monitoring"""
        self.log.halt("[HALT-MONITOR] Stopping halt monitor")
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
            
    def _run_loop(self):
        """Main loop: fetch halts every 2.5 minutes"""
        # Run immediately on start
        self._fetch_halts()
        
        # Then run every 2.5 minutes
        while not self.stop_event.is_set():
            self.stop_event.wait(self.fetch_interval)
            if not self.stop_event.is_set():
                self._fetch_halts()
                
    def _fetch_halts(self):
        """Fetch halt data from multiple sources and merge"""
        try:
            self.log.halt("[HALT-MONITOR] Fetching halt data from multiple sources...")
            
            # Source 1: NASDAQ HTML table (most reliable for NASDAQ stocks)
            nasdaq_html_halts = self._fetch_nasdaq_html_table()
            self.log.halt(f"[HALT-MONITOR] NASDAQ HTML: {len(nasdaq_html_halts)} halts")
            
            # Source 2: NASDAQ RSS feed (catches NYSE, AMEX, OTC halts)
            nasdaq_rss_halts = self._fetch_nasdaq_halts()
            self.log.halt(f"[HALT-MONITOR] NASDAQ RSS: {len(nasdaq_rss_halts)} halts")
            
            # Merge: HTML table takes priority (more accurate status)
            all_halts = {**nasdaq_rss_halts}  # Start with RSS
            
            # Override with HTML table data (more reliable)
            for symbol, halt_data in nasdaq_html_halts.items():
                all_halts[symbol] = halt_data
            
            # Filter: Only keep HALTED stocks from merged data
            active_halts_only = {
                symbol: data for symbol, data in all_halts.items()
                if data.get('status') == 'HALTED'
            }
            
            self.log.halt(f"[HALT-MONITOR] Total merged: {len(all_halts)}, Active halts: {len(active_halts_only)}")
            
            if active_halts_only:
                self._process_halts(active_halts_only)
                self.log.halt(f"[HALT-MONITOR] OK Processed {len(active_halts_only)} active halts")
            else:
                self.log.halt("[HALT-MONITOR] No active halts found")
                
        except Exception as e:
            self.log.crash(f"[HALT-MONITOR] Error fetching halts: {e}")
            
    def _fetch_nasdaq_halts(self) -> dict:
        """Fetch halts from NASDAQ API (JSON endpoint)"""
        self.log.halt(f"[HALT-MONITOR] Attempting to fetch from NASDAQ...")
        try:
            from xml.etree import ElementTree as ET
            import re
            import html
            
            url = "https://www.nasdaqtrader.com/rss.aspx?feed=tradehalts"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            self.log.halt(f"[HALT-MONITOR] Response: status={response.status_code}, length={len(response.content)}")
            
            if response.status_code != 200:
                self.log.halt(f"[HALT-MONITOR] NASDAQ API returned status {response.status_code}")
                return {}
            
            # Parse RSS/XML response
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            self.log.halt(f"[HALT-MONITOR] Found {len(items)} items in RSS feed")
            
            halts = {}
            
            for item in items:
                try:
                    title = item.find('title').text if item.find('title') is not None else ''
                    description = item.find('description').text if item.find('description') is not None else ''
                    pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ''
                    
                    # Extract halt reason CODE from HTML table description
                    reason_code = ''
                    if description:
                        # Priority 1: Look for "Reason Code" or "Reason Codes" field in table
                        reason_code_match = re.search(
                            r'Reason\s*Codes?[:\s]*</td>\s*<td[^>]*>([^<]+)</td>', 
                            description, 
                            re.IGNORECASE
                        )
                        if reason_code_match:
                            reason_code = reason_code_match.group(1).strip()
                            self.log.halt(f"[HALT-MONITOR] Extracted reason code from table: {reason_code}")
                        else:
                            # Priority 2: Search for known halt codes in description text
                            code_match = re.search(
                                r'\b(LUDP|LUDS|T1|T2|T3|T5|T6|T7|T8|T12|H4|H9|H10|H11|M1|M2|MWC[0-3]|IPO1|IPOQ|IPOE|O1|R[149]|C[349]|C11|M)\b',
                                description,
                                re.IGNORECASE
                            )
                            if code_match:
                                reason_code = code_match.group(1).upper()
                                self.log.halt(f"[HALT-MONITOR] Found halt code in text: {reason_code}")
                            else:
                                # Fallback: strip HTML and show cleaned text (first 50 chars)
                                clean_desc = re.sub(r'<[^>]+>', ' ', description)
                                clean_desc = re.sub(r'\s+', ' ', clean_desc).strip()
                                reason_code = html.unescape(clean_desc)[:50]
                                self.log.halt(f"[HALT-MONITOR] No code found, using description: {reason_code}")
                    
                    # Extract symbol from title (format: "XXXX - Company Name")
                    if ' - ' in title:
                        symbol = title.split(' - ')[0].strip()
                    else:
                        symbol = title.strip()
                    
                    if not symbol:
                        continue
                    
                    # Determine if halted or resumed from TITLE
                    title_lower = title.lower()
                    if 'resumption' in title_lower or 'resumed' in title_lower:
                        is_halted = False
                    elif 'halt' in title_lower or 'halted' in title_lower:
                        is_halted = True
                    else:
                        # Fallback to description
                        desc_lower = description.lower()
                        if 'resumption' in desc_lower:
                            is_halted = False
                        else:
                            is_halted = True
                    
                    self.log.halt(f"[HALT-MONITOR] Parsed: {symbol} - Status: {'HALTED' if is_halted else 'RESUMED'} - Code: {reason_code}")
                    
                    self.log.halt(f"[HALT-MONITOR] DEBUG: symbol={symbol}, pub_date='{pub_date}'")
                    
                    halts[symbol] = {
                        'symbol': symbol,
                        'halt_time': pub_date,
                        'resume_time': None if is_halted else pub_date,
                        'reason': reason_code,  # Store the extracted reason code
                        'status': 'HALTED' if is_halted else 'RESUMED',
                        'exchange': 'NASDAQ',
                        'timestamp': datetime.utcnow().isoformat(),
                        'price': 0.0
                    }
                    
                except Exception as e:
                    self.log.crash(f"[HALT-MONITOR] Error parsing halt item: {e}")
                    continue
            
            self.log.halt(f"[HALT-MONITOR] Returning {len(halts)} halts")
            return halts
            
        except Exception as e:
            self.log.crash(f"[HALT-MONITOR] NASDAQ fetch error: {e}")
            return {}

    def _fetch_nasdaq_html_table(self) -> dict:
        """Fetch ACTIVE halts from NASDAQ HTML table (more reliable)"""
        try:
            self.log.halt("[HALT-MONITOR] Fetching from NASDAQ HTML table...")
            
            url = "http://www.nasdaqtrader.com/trader.aspx?id=tradehalts"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            self.log.halt(f"[HALT-MONITOR] HTML response: status={response.status_code}")
            
            if response.status_code != 200:
                return {}
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try multiple selectors - NASDAQ changes their HTML structure
            table = (
                soup.find('table', {'id': 'HaltData'}) or
                soup.find('table', {'class': 'haltdata'}) or
                soup.find('table', string=lambda text: text and 'Halt' in text if text else False) or
                soup.find_all('table')[0] if soup.find_all('table') else None
            )
            
            if not table:
                self.log.halt("[HALT-MONITOR] WARNING: Could not find halt table - saving HTML for debug")
                with open('nasdaq_halt_page_debug.html', 'wb') as f:
                    f.write(response.content)
                self.log.halt("[HALT-MONITOR] Saved HTML to nasdaq_halt_page_debug.html for inspection")
                return {}
            
            halts = {}
            rows = table.find_all('tr')[1:]
            self.log.halt(f"[HALT-MONITOR] Found {len(rows)} rows in HTML table")
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    symbol = cols[0].text.strip()
                    halt_time = cols[1].text.strip()
                    resume_time = cols[2].text.strip() if len(cols) > 2 else ''
                    reason = cols[3].text.strip() if len(cols) > 3 else 'Unknown'
                    
                    if not resume_time or resume_time == '' or resume_time.isspace():
                        self.log.halt(f"[HALT-MONITOR] ACTIVE HALT: {symbol} at {halt_time} - Reason: {reason}")
                        halts[symbol] = {
                            'symbol': symbol,
                            'halt_time': halt_time,
                            'resume_time': None,
                            'reason': reason,
                            'status': 'HALTED',
                            'exchange': 'NASDAQ',
                            'timestamp': datetime.utcnow().isoformat(),
                            'price': 0.0
                        }
                    else:
                        self.log.halt(f"[HALT-MONITOR] RESUMED: {symbol} at {resume_time}")
            
            return halts
            
        except Exception as e:
            self.log.crash(f"[HALT-MONITOR] HTML table fetch error: {e}")
            import traceback
            self.log.crash(traceback.format_exc())
            return {}

    def _process_halts(self, halts: dict):
        """Process halt data, update files, and emit signals to GUI"""
        try:
            # Load existing data
            active_halts = self.fm.load_active_halts()
            historical_halts = self.fm.load_halts()
            
            for symbol, halt_data in halts.items():
                # Filter out Canadian stocks (TSX symbols)
                if symbol and ('TSX:' in symbol or symbol.endswith('.TO') or symbol.endswith('.TSX')):
                    self.log.halt(f"[HALT-MONITOR] Skipping Canadian stock: {symbol}")
                    continue
                
                # Enrich with price data from Tier3 if available
                if hasattr(self, 'tier3') and self.tier3 and hasattr(self.tier3, 'live_data'):
                    live_data = self.tier3.live_data.get(symbol, {})
                    prev_close = self.tier3.prev_closes.get(symbol, 0.0)
                    
                    price = live_data.get('price', 0.0)
                    if not price:
                        bid = live_data.get('bid', 0.0)
                        ask = live_data.get('ask', 0.0)
                        price = (bid + ask) / 2 if bid and ask else 0.0
                    
                    if price > 0:
                        halt_data['price'] = price
                        halt_data['prev_close'] = prev_close
                        change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0.0
                        halt_data['change_pct'] = change_pct
                        self.log.halt(f"[HALT-MONITOR] Enriched {symbol} with Tier3 price: ${price:.2f}")
                    else:
                        self.log.halt(f"[HALT-MONITOR] No Tier3 price data for {symbol}")

                status = halt_data.get('status', 'HALTED')
                
                if status == 'HALTED':
                    # Add to active halts
                    active_halts[symbol] = halt_data
                    self.log.halt(f"[HALT-MONITOR] HALTED: {symbol} @ ${halt_data.get('price', 0.0):.2f} - {halt_data.get('reason', 'Unknown')[:50]}")
                    
                    # Emit signal to GUI
                    self.halt_signal.emit(halt_data)
                    
                elif status == 'RESUMED':
                    # Remove from active halts if present
                    was_active = symbol in active_halts
                    if was_active:
                        del active_halts[symbol]
                        self.log.halt(f"[HALT-MONITOR] RESUMED: {symbol} @ ${halt_data.get('price', 0.0):.2f} (was active)")
                    
                    # Always save to historical (even if wasn't actively tracked)
                    halt_id = f"{symbol}_{int(time.time())}"
                    historical_halts[halt_id] = halt_data
                    
                    # Emit signal to GUI only if it was actively halted
                    if was_active:
                        self.halt_signal.emit(halt_data)
                    
            # Save updated data
            self.fm.save_active_halts(active_halts)
            self.fm.save_halts(historical_halts)
            
        except Exception as e:
            self.log.crash(f"[HALT-MONITOR] Error processing halts: {e}")
