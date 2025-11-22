"""
SignalScan PRO - Tier 3: Tradier Categorizer
Subscribes to validated symbols via Tradier WebSocket
Categorizes by channel rules, maintains live data for GUI
Subscribes to: alpaca_validated, active_halts, bkgnews
"""

import json
import time
import websocket
import requests
from threading import Thread, Event
from datetime import datetime
from queue import Queue
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from core.file_manager import FileManager
from core.logger import Logger
from config.api_keys import API_KEYS
from .channel_detector import ChannelDetector

class TradierCategorizer(QObject):
    # PyQt5 signals for live GUI updates
    pregap_signal = pyqtSignal(dict)
    hod_signal = pyqtSignal(dict)
    runup_signal = pyqtSignal(dict)
    reversal_signal = pyqtSignal(dict)
    
    def __init__(self, file_manager: FileManager, logger: Logger):
        super().__init__()  # Initialize QObject
        self.fm = file_manager
        self.log = logger
        self.stop_event = Event()
        self.thread = None
        
        # Thread-safe queue for signal emissions
        self.signal_queue = Queue()
        
        # Timer to process queued signals on main thread
        self.signal_timer = QTimer()
        self.signal_timer.timeout.connect(self._process_signal_queue)
        self.signal_timer.start(100)  # Check queue every 100ms

        # Tradier credentials
        self.api_key = API_KEYS['TRADIER_API_KEY']
        
        # WebSocket connection
        self.ws = None
        self.session_id = None
        self.subscribed_symbols = set()
        
        # Live data cache (for GUI)
        self.live_data = {}
        
        # Channel detector
        self.detector = ChannelDetector(logger)
        
        # Track previous data for calculations
        self.prev_closes = {}
        self.day_opens = {}
        self.day_highs = {}
        self.price_history = {}   
        # Cache for volume_avg to prevent repeated API calls
        self.volume_avg_cache = {}
        
        # Categorized stocks by channel
        self.channels = {
            'pregap': [],
            'hod': [],
            'runup': [],
            'rvsl': [],
            'bkgnews': []
        }
        
        # Cache management for API efficiency
        self.no_data_symbols = set()  # Symbols with no historical data
        self.prev_close_cache_time = {}  # {symbol: timestamp}
        self.cache_duration = 3600  # 1 hour
        
        # Cooldown for symbols that don't match any channel
        self.failed_categorizations = {}  # {symbol: timestamp}
        self.categorization_cooldown = 60  # Don't recheck for 60 seconds
    
    def _process_signal_queue(self):
        """Process queued signal emissions on the main GUI thread"""
        try:
            while not self.signal_queue.empty():
                channel, stock_data = self.signal_queue.get_nowait()
                
                # Now we're on the main thread, safe to emit signals
                if channel == 'pregap':
                    self.pregap_signal.emit(stock_data)
                    self.log.scanner(f"[TIER3-SIGNAL-EMIT] OK Emitted PREGAP signal for {stock_data.get('symbol')}")
                elif channel == 'hod':
                    self.hod_signal.emit(stock_data)
                    self.log.scanner(f"[TIER3-SIGNAL-EMIT] OK Emitted HOD signal for {stock_data.get('symbol')}")
                elif channel == 'runup':
                    self.runup_signal.emit(stock_data)
                    self.log.scanner(f"[TIER3-SIGNAL-EMIT] OK Emitted RUNUP signal for {stock_data.get('symbol')}")
                elif channel == 'rvsl':
                    self.reversal_signal.emit(stock_data)
                    self.log.scanner(f"[TIER3-SIGNAL-EMIT] OK Emitted REVERSAL signal for {stock_data.get('symbol')}")
                
                    #self.log.scanner(f"[TIER3-SIGNAL-EMIT] OK Emitted {channel.upper()} signal for {stock_data.get('symbol')}")
        
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error processing signal queue: {e}")
    
    def start(self):
        """Start Tradier WebSocket categorizer"""
        self.log.scanner("[TIER3-TRADIER] Starting Tradier categorizer (WebSocket)")
        self.stop_event.clear()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()
    
        # Start daily volume reset thread
        reset_thread = Thread(target=self._daily_reset_loop, daemon=True)
        reset_thread.start()

    def _daily_reset_loop(self):
        """Reset volume counters at 9:30 AM EST every day"""
        import pytz
        est = pytz.timezone('America/New_York')
    
        while not self.stop_event.is_set():
            try:
                now = datetime.now(est)
            
                # Check if it's 9:30 AM
                if now.hour == 9 and now.minute == 30:
                    self.log.scanner("[TIER3-TRADIER] Resetting daily volume counters")
                    for symbol in self.live_data:
                        self.live_data[symbol]['volume'] = 0
                
                    # Sleep 61 seconds to avoid running multiple times in same minute
                    time.sleep(61)
                else:
                    # Check every 30 seconds
                    time.sleep(30)
                
            except Exception as e:
                self.log.crash(f"[TIER3-TRADIER] Error in daily reset: {e}")
                time.sleep(60)

    def stop(self):
        """Stop the categorizer"""
        self.log.scanner("[TIER3-TRADIER] Stopping Tradier categorizer")
        self.stop_event.set()
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join(timeout=5)
            
    def _run_loop(self):
        """Main loop: connect to Tradier WebSocket and maintain subscriptions"""
        # Get session ID
        self._get_session_id()
        
        # Connect to WebSocket
        self._connect_websocket()
        
        while not self.stop_event.is_set():
            try:
                # Load alpaca_validated.json
                validated = self.fm.load_validated()
                
                # Load active_halts.json
                active_halts = self.fm.load_active_halts()
                
                # Load bkgnews.json
                bkgnews = self.fm.load_bkgnews()
                self.log.scanner(f"[TIER3-TRADIER] Loaded {len(bkgnews)} breaking news symbols: {list(bkgnews.keys())}")
                
                # Combine symbols to subscribe
                all_symbols = set()
                all_symbols.update([s['symbol'] for s in validated if 'symbol' in s])
                all_symbols.update(active_halts.keys())
                all_symbols.update([item['symbol'] for item in bkgnews.values() if 'symbol' in item])

                # Fetch previous closes for new symbols
                new_symbols = all_symbols - set(self.prev_closes.keys())
                if new_symbols:
                    self.log.scanner(f"[TIER3-TRADIER] Fetching prev_closes for {len(new_symbols)} new symbols")
                    self.fetch_prev_closes(list(new_symbols))
                
                # Update subscriptions
                self._update_subscriptions(all_symbols)
                
                # Wait 10 seconds
                time.sleep(30)
                
            except Exception as e:
                self.log.crash(f"[TIER3-TRADIER] Error in run loop: {e}")
                time.sleep(10)
                
    def _get_session_id(self):
        """Get Tradier WebSocket session ID"""
        try:
            import requests
            
            url = "https://api.tradier.com/v1/markets/events/session"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json"
            }
            
            response = requests.post(url, headers=headers)
            data = response.json()
            
            self.session_id = data['stream']['sessionid']
            self.log.scanner(f"[TIER3-TRADIER] Got session ID: {self.session_id}")
            
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error getting session ID: {e}")
            
    def _connect_websocket(self):
        """Connect to Tradier WebSocket"""
        try:
            import ssl
        
            ws_url = "wss://ws.tradier.com/v1/markets/events"
        
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
        
            # Run WebSocket in background thread with SSL bypass
            ws_thread = Thread(
                target=lambda: self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}),
                daemon=True
            )
            ws_thread.start()
        
            self.log.scanner("[TIER3-TRADIER] WebSocket connected")
        
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error connecting WebSocket: {e}")
            
    def _on_open(self, ws):
        """WebSocket opened"""
        self.log.scanner("[TIER3-TRADIER] WebSocket opened")
        
    def _on_message(self, ws, message):
        #self.log.scanner(f"[TIER3-TRADIER] Received message: {message[:200]}")
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            # Handle quote/trade data
            if 'type' in data:
                if data['type'] == 'quote':
                    self._handle_quote(data)
                elif data['type'] == 'trade':
                    self._handle_trade(data)
                    
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error handling message: {e}")
            
    def _on_error(self, ws, error):
        """WebSocket error"""
        self.log.crash(f"[TIER3-TRADIER] WebSocket error: {error}")
        
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket closed"""
        self.log.scanner(f"[TIER3-TRADIER] WebSocket closed: {close_msg}")
    
        # Auto-reconnect after 30 seconds
        if not self.stop_event.is_set():
            self.log.scanner("[TIER3-TRADIER] Reconnecting in 30 seconds...")
            time.sleep(30)
            self._get_session_id()
            self._connect_websocket()
        
    def _update_subscriptions(self, symbols: set):
        """
        Subscribe to new symbols in Tradier WebSocket in safe chunks (max 50 per batch).
        Filters out invalid symbols.
        """
        new_symbols = symbols - self.subscribed_symbols
        if new_symbols and self.ws and self.session_id:
            # Filter out invalid symbols for Tradier
            symbol_list = [
                s for s in new_symbols
                if s and s.isalpha() and 0 < len(s) <= 5
            ]
            max_per_batch = 50  # Tradier's per-request symbol limit

            for i in range(0, len(symbol_list), max_per_batch):
                batch = symbol_list[i:i+max_per_batch]
                self.log.scanner(f"[TIER3-TRADIER] Subscribing to batch: {batch}")
                subscribe_msg = {
                    "symbols": batch,
                    "sessionid": self.session_id,
                    "filter": ["quote", "trade"]
                }
                try:
                    self.ws.send(json.dumps(subscribe_msg))
                except Exception as e:
                    self.log.crash(f"[TIER3-TRADIER] Error subscribing batch: {e}")

            self.subscribed_symbols.update(symbol_list)
            
    def _handle_quote(self, data: dict):
        #self.log.scanner(f"[TIER3-TRADIER] Handling QUOTE: {data.get('symbol')}")
        """Handle real-time quote"""
        try:
            symbol = data.get('symbol')
            self.log.scanner(f"[TIER3-DEBUG] QUOTE RECEIVED: {symbol} - {data}")

            if not symbol:
                return
                
            # Update live data
            if symbol not in self.live_data:
                self.live_data[symbol] = {}
                
            self.live_data[symbol].update({
                'symbol': symbol,
                'bid': data.get('bid'),
                'ask': data.get('ask'),
                'bid_size': data.get('bidsz'),
                'ask_size': data.get('asksz'),
                'last_update': datetime.utcnow().isoformat()
            })
            
            # Detect channel and emit signal
            self._categorize_symbol(symbol)
            
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error handling quote: {e}")
            
    def _handle_trade(self, data: dict):
        """Handle real-time trade"""
        try:
            symbol = data.get('symbol')
            self.log.scanner(f"[TIER3-DEBUG] TRADE RECEIVED: {symbol} - {data}")

            if not symbol:
                return
    
            if symbol not in self.live_data:
                # Try to get starting volume from validated.json
                validated = self.fm.load_validated()
                validated_data = next((s for s in validated if s.get('symbol') == symbol), {})
                starting_volume = validated_data.get('volume', 0)
                
                self.live_data[symbol] = {
                    'volume': starting_volume  # Start with known volume, not 0
                }
                self.log.scanner(f"[TIER3-INIT] {symbol}: Initialized with volume={starting_volume:,}")

            # Convert price to float
            price = data.get('price')
            if price:
                price = float(price)
    
            # USE TRADIER'S CUMULATIVE VOLUME (cvol) - Already includes all trades today
            cumulative_volume = int(data.get('cvol', 0))
    
            self.live_data[symbol].update({
                'price': price,
                'volume': cumulative_volume,  # Use Tradier's cumulative volume
                'timestamp': datetime.utcnow().isoformat()
            })
        
            # Log volume milestones
            if cumulative_volume % 500000 < 10000:  # Log at 500k, 1M, 1.5M, etc
                self.log.scanner(f"[TIER3-TRADE] {symbol}: volume={cumulative_volume:,}, price={price}")

            # Detect channel and emit signal
            self.log.scanner(f"[TIER3-DEBUG] About to categorize: {symbol}")
            self._categorize_symbol(symbol)
            self.log.scanner(f"[TIER3-DEBUG] Finished categorizing: {symbol}")

        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error handling trade: {e}")
    
    def _enrich_stock_data(self, symbol: str, live_data: dict) -> dict:
        """Calculate all fields needed for channel detection"""
        try:
            validated = self.fm.load_validated()
            validated_data = next((s for s in validated if s.get('symbol') == symbol), {})
            enriched = {**validated_data, **live_data}

            self.log.scanner(f"[TIER3-ENRICH] {symbol}: live_data = {live_data}")

            # Get price from live_data (trades) or calculate from bid/ask (quotes)
            price = live_data.get('price', 0)
            if not price:
                # For QUOTE messages, calculate from current bid/ask
                bid = live_data.get('bid', 0)
                ask = live_data.get('ask', 0)
                price = (bid + ask) / 2 if bid and ask else 0
            
            enriched['price'] = price

            # ===== FIX: Get prev_close in priority order =====
            prev_close = 0
            
            # Priority 1: From validated.json (Tier2 already has it)
            if 'prev_close' in validated_data and validated_data.get('prev_close', 0) > 0:
                prev_close = float(validated_data['prev_close'])
                self.log.scanner(f"[TIER3-ENRICH] {symbol}: Using prev_close from validated.json = ${prev_close:.2f}")
            
            # Priority 2: From our cached dict
            elif symbol in self.prev_closes and self.prev_closes[symbol] > 0:
                prev_close = self.prev_closes[symbol]
                self.log.scanner(f"[TIER3-ENRICH] {symbol}: Using cached prev_close = ${prev_close:.2f}")
            
            # Priority 3: Fetch from Tradier NOW (synchronous fallback)
            else:
                self.log.scanner(f"[TIER3-ENRICH] {symbol}: NO prev_close - fetching NOW...")
                self.fetch_prev_closes([symbol])
                prev_close = self.prev_closes.get(symbol, 0)
                if prev_close > 0:
                    self.log.scanner(f"[TIER3-ENRICH] {symbol}: Fetched prev_close = ${prev_close:.2f}")
                else:
                    self.log.scanner(f"[TIER3-ENRICH] {symbol}: X FAILED to get prev_close")
            
            # Calculate gap_pct
            if prev_close > 0 and price > 0:
                gap_pct = ((price - prev_close) / prev_close) * 100
                enriched['gap_pct'] = gap_pct
                enriched['prev_close'] = prev_close
                self.log.scanner(f"[TIER3-ENRICH] {symbol}: gap_pct = ({price:.2f} - {prev_close:.2f}) / {prev_close:.2f} = {gap_pct:.2f}%")
            else:
                enriched['gap_pct'] = 0
                enriched['prev_close'] = 0
                self.log.scanner(f"[TIER3-ENRICH] {symbol}: X GAP CALC FAILED - price={price}, prev_close={prev_close}")

            # Track high of day
            current_high = self.day_highs.get(symbol, price)
            if price > current_high:
                self.day_highs[symbol] = price
                enriched['is_hod'] = True
            else:
                enriched['is_hod'] = False
            enriched['hod_price'] = self.day_highs.get(symbol, price)
            
            # Calculate rvol with fallback for missing volume_avg
            current_vol = float(live_data.get('volume', 0)) if live_data.get('volume') else 0
            avg_vol = enriched.get('volume_avg', 0)
            
            # If volume_avg is missing, fetch it once and cache
            avg_vol = enriched.get('volume_avg', 1000000)  # Use 1M as fallback if missing
            
            enriched['volume_avg'] = avg_vol
            enriched['rvol'] = current_vol / avg_vol if avg_vol > 0 else 0
            
            # DEBUG: Always log rvol calculation
            self.log.scanner(f"[TIER3-DEBUG] {symbol}: rvol = {current_vol:,.0f} / {avg_vol:,.0f} = {enriched['rvol']:.2f}")
            
            # Track price history for 5min/10min moves
            now = datetime.utcnow()
            if symbol not in self.price_history:
                self.price_history[symbol] = []
            self.price_history[symbol].append((now, price))
            
            # Keep only last 15 minutes of history
            cutoff = now.timestamp() - 900
            self.price_history[symbol] = [(ts, p) for ts, p in self.price_history[symbol] if ts.timestamp() > cutoff]
            
            # Calculate 5-minute price move
            five_min_ago = now.timestamp() - 300
            old_prices = [p for ts, p in self.price_history[symbol] if ts.timestamp() <= five_min_ago]
            if old_prices:
                old_price = old_prices[-1]
                enriched['move_5min'] = ((price - old_price) / old_price) * 100 if old_price > 0 else 0
            else:
                enriched['move_5min'] = 0
            
            # Calculate 10-minute price move
            ten_min_ago = now.timestamp() - 600
            old_prices_10 = [p for ts, p in self.price_history[symbol] if ts.timestamp() <= ten_min_ago]
            if old_prices_10:
                old_price = old_prices_10[-1]
                enriched['move_10min'] = ((price - old_price) / old_price) * 100 if old_price > 0 else 0
            else:
                enriched['move_10min'] = 0
            
            enriched['rvol_5min'] = enriched['rvol']
            enriched['float'] = enriched.get('float', 50000000)
            
            # Check for breaking news
            bkgnews = self.fm.load_bkgnews()
            enriched['has_breaking_news'] = symbol in bkgnews
            if enriched['has_breaking_news']:
                news_ts = bkgnews[symbol].get('timestamp', '')
                try:
                    news_time = datetime.fromisoformat(news_ts.replace('Z', '+00:00'))
                    age_hours = (datetime.now(news_time.tzinfo) - news_time).total_seconds() / 3600
                    enriched['news_age_hours'] = age_hours
                except:
                    enriched['news_age_hours'] = 999
            else:
                enriched['news_age_hours'] = 999
            
            return enriched
        except Exception as e:
            self.log.crash(f"[TIER3] Error enriching {symbol}: {e}")
            return live_data

    def _categorize_symbol(self, symbol: str):
        """Categorize symbol into appropriate channel and emit signal to GUI"""
        self.log.scanner(f"[TIER3-DEBUG] _categorize_symbol CALLED for {symbol}")
        
        # Check cooldown - skip if recently failed to categorize
        if symbol in self.failed_categorizations:
            time_since_fail = time.time() - self.failed_categorizations[symbol]
            if time_since_fail < self.categorization_cooldown:
                return
        
        try:
            live_data = self.live_data.get(symbol, {})
            
            # === ADDED DEBUG LOG ===
            price = live_data.get('price', 0)
            gap_pct = live_data.get('gap_pct', 0)
            volume = live_data.get('volume', 0)
            self.log.scanner(f"[CHANNEL-TEST] Raw live_data for {symbol}: price={price}, gap_pct={gap_pct:.2f}%, volume={volume}")
            # === END ADDED DEBUG ===

            # Enrich with calculated fields
            stock_data = self._enrich_stock_data(symbol, live_data)
            
            # ===== DEBUG: Log complete stock_data for first 5 symbols =====
            if not hasattr(self, '_debug_logged_symbols'):
                self._debug_logged_symbols = set()
            
            if symbol not in self._debug_logged_symbols and len(self._debug_logged_symbols) < 5:
                self.log.scanner(f"=" * 80)
                self.log.scanner(f"[TIER3-COMPLETE-DATA] Full stock_data for {symbol}:")
                for key, value in sorted(stock_data.items()):
                    self.log.scanner(f"  {key}: {value}")
                self.log.scanner(f"=" * 80)
                self._debug_logged_symbols.add(symbol)

            self.log.scanner(f"[TIER3-DEBUG] {symbol} enriched: price={stock_data.get('price')}, gap_pct={stock_data.get('gap_pct')}, volume={stock_data.get('volume')}")
            
            # DEBUG: Log enriched data for AES to see what detector receives
            if symbol == 'AES':
                self.log.scanner(f"[TIER3-DEBUG] AES enriched: price={stock_data.get('price')}, gap_pct={stock_data.get('gap_pct', 0):.2f}, rvol={stock_data.get('rvol', 0):.2f}, volume={stock_data.get('volume')}, volume_avg={stock_data.get('volume_avg')}, is_hod={stock_data.get('is_hod')}")

            # === ADDED DEBUG LOG ===
            self.log.scanner(f"[CHANNEL-TEST] {symbol} - Calling detect_channel with enriched data...")
            # === END ADDED DEBUG ===

            # Detect channel
            channel = self.detector.detect_channel(stock_data)

            # Add cooldown for non-matching symbols
            if not channel:
                self.failed_categorizations[symbol] = time.time()
            
            if channel:
                self.log.scanner(f"[TIER3-DETECT] OK {symbol} -> {channel.upper()}")
            else:
                # Log why detection failed for high-potential symbols
                gap = stock_data.get('gap_pct', 0)
                rvol = stock_data.get('rvol', 0)
                price = stock_data.get('price', 0)
                if abs(gap) > 3 or rvol > 1.3:
                    self.log.scanner(f"[TIER3-DETECT] X {symbol} NO MATCH - price=${price:.2f}, gap={gap:.2f}%, rvol={rvol:.2f}")
            
            # === ADDED DEBUG LOG ===
            self.log.scanner(f"[CHANNEL-TEST] ✓ {symbol} → {channel if channel else 'NO MATCH'}")
            # === END ADDED DEBUG ===
        
            if symbol == 'AES':
                self.log.scanner(f"[TIER3-DEBUG] AES detected channel: {channel}")

            if channel:
                # Add to channel if not already there
                if symbol not in self.channels[channel]:
                    self.channels[channel].append(symbol)
                    self.log.scanner(f"[TIER3-TRADIER] OK {symbol} -> {channel.upper()}")
            
            # Queue signal emission for main thread (THREAD-SAFE)
            if channel:
                self.log.scanner(f"[TIER3->GUI] Queuing {channel.upper()} signal for {symbol}")
                self.signal_queue.put((channel, stock_data))
                
        except Exception as e:
            self.log.crash(f"[TIER3-TRADIER] Error categorizing {symbol}: {e}")

    def get_channel_data(self, channel: str) -> list:
        """Get live data for a specific channel (for GUI)"""
        symbols = self.channels.get(channel, [])
        return [self.live_data.get(s, {}) for s in symbols]
    
    def fetch_prev_closes(self, symbols: list):
        """Fetch yesterday's closing prices from Tradier historical data"""
        import requests
        from datetime import datetime, timedelta
        
        if not symbols:
            return
        
        # Filter out blacklisted symbols and recently cached ones
        current_time = time.time()
        symbols_to_fetch = []
        
        for symbol in symbols:
            # Skip if blacklisted
            if symbol in self.no_data_symbols:
                continue
            
            # Skip if recently cached
            if symbol in self.prev_close_cache_time:
                age = current_time - self.prev_close_cache_time[symbol]
                if age < self.cache_duration:
                    continue
            
            symbols_to_fetch.append(symbol)
        
        if not symbols_to_fetch:
            self.log.scanner(f"[TIER3-CACHE] All symbols cached or blacklisted, skipping fetch")
            return
        
        self.log.scanner(f"[TIER3-TRADIER] Fetching prev_closes for {len(symbols_to_fetch)} symbols (filtered from {len(symbols)})")
        
        try:
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Process in batches of 50
            batch_size = 50
            for i in range(0, len(symbols_to_fetch), batch_size):
                batch = symbols_to_fetch[i:i + batch_size]
                self.log.scanner(f"[TIER3-BATCH] Processing batch {i//batch_size + 1}/{(len(symbols_to_fetch)-1)//batch_size + 1} ({len(batch)} symbols)")
                
                for symbol in batch:
                    url = f"https://api.tradier.com/v1/markets/history?symbol={symbol}&interval=daily&start={yesterday}&end={yesterday}"
                    headers = {
                        'Authorization': f'Bearer {self.api_key}',
                        'Accept': 'application/json'
                    }
                    
                    try:
                        response = requests.get(url, headers=headers, timeout=30)
                        response.raise_for_status()
                        data = response.json()
                        
                        history = data.get('history', {})
                        if history and 'day' in history:
                            day = history['day']
                            if isinstance(day, dict):
                                close = day.get('close')
                                if close:
                                    self.prev_closes[symbol] = float(close)
                                    self.prev_close_cache_time[symbol] = current_time
                                    self.log.scanner(f"[TIER3-FETCH] {symbol}: prev_close = {close}")
                                else:
                                    self.no_data_symbols.add(symbol)
                                    self.log.scanner(f"[TIER3-FETCH] {symbol}: NO CLOSE PRICE (blacklisted)")
                        else:
                            self.no_data_symbols.add(symbol)
                            self.log.scanner(f"[TIER3-FETCH] {symbol}: NO HISTORICAL DATA (blacklisted)")
                    
                    except Exception as e:
                        self.log.scanner(f"[TIER3-FETCH] Error fetching {symbol}: {e}")
                        continue
                
                # Rate limiting between batches
                if i + batch_size < len(symbols_to_fetch):
                    time.sleep(0.5)
                    
        except Exception as e:
            self.log.scanner(f"[TIER3-FETCH] Error fetching prev_closes: {e}")