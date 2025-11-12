"""
SignalScan PRO - Tier 2: Alpaca Validator
Validates prefilter list via Alpaca WebSocket (real-time)
Confirms data and fills missing fields
Output: validated.json
"""

import json
import time
from threading import Thread, Event
from datetime import datetime, timedelta
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.historical import StockHistoricalDataClient
from core.file_manager import FileManager
from core.logger import Logger
from config.api_keys import API_KEYS



class AlpacaValidator:
    def __init__(self, file_manager: FileManager, logger: Logger):
        self.fm = file_manager
        self.log = logger
        self.stop_event = Event()
        self.thread = None
        
        # Alpaca credentials
        self.api_key = API_KEYS['ALPACA_API_KEY']
        self.api_secret = API_KEYS['ALPACA_SECRET_KEY']
        
        # WebSocket connection
        self.stream = None
        self.subscribed_symbols = set()
        
        # Validated data cache
        self.validated_data = {}
        
        # Historical data client (for missing fields)
        self.hist_client = StockHistoricalDataClient(self.api_key, self.api_secret)
        
    def start(self):
        """Start Alpaca WebSocket validator"""
        self.log.scanner("[TIER2-ALPACA] Starting Alpaca validator (WebSocket)")
        self.stop_event.clear()
        self.thread = Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """Stop the validator"""
        self.log.scanner("[TIER2-ALPACA] Stopping Alpaca validator")
        self.stop_event.set()
        if self.stream:
            self.stream.close()
        if self.thread:
            self.thread.join(timeout=5)
            
    def _run_loop(self):
        """Main loop: monitor prefilter.json and subscribe to symbols"""
        while not self.stop_event.is_set():
            try:
                # Load prefilter.json
                prefilter_data = self.fm.load_prefilter()
            
                # Extract symbols (support both old list format and new dict format)
                if prefilter_data:
                    if isinstance(prefilter_data[0], dict):
                        # New format: [{'symbol': 'AAPL', 'volume_avg': 5000000}]
                        symbols = [item['symbol'] for item in prefilter_data]
                        # Store volume_avg in validated_data
                        for item in prefilter_data:
                            symbol = item['symbol']
                            if symbol not in self.validated_data:
                                self.validated_data[symbol] = {}
                            self.validated_data[symbol]['volume_avg'] = item.get('volume_avg', 0)
                    else:
                        # Old format: ['AAPL', 'MSFT']
                        symbols = prefilter_data
                else:
                    symbols = []
            
                if symbols and not self.stream:
                    # Initialize WebSocket with symbols
                    self._init_websocket(symbols)
                elif symbols:
                    # Update subscriptions for new symbols
                    self._update_subscriptions(symbols)
            
                # Save validated data every 10 seconds
                self._save_validated_data()
            
                # Wait 10 seconds before next check
                time.sleep(10)
            
            except Exception as e:
                self.log.crash(f"[TIER2-ALPACA] Error in run loop: {e}")
                time.sleep(10)
                
    def _init_websocket(self, symbols: list):
        """Initialize Alpaca WebSocket connection"""
        try:
            self.log.scanner(f"[TIER2-ALPACA] Initializing WebSocket for {len(symbols)} symbols...")
            
            self.stream = StockDataStream(self.api_key, self.api_secret)
            
            # Define quote handler
            async def quote_handler(data):
                await self._handle_quote(data)
            
            # Define trade handler
            async def trade_handler(data):
                await self._handle_trade(data)
            
            # Subscribe to quotes and trades
            self.stream.subscribe_quotes(quote_handler, *symbols)
            self.stream.subscribe_trades(trade_handler, *symbols)
            
            # Mark as subscribed
            self.subscribed_symbols.update(symbols)
            
            # Fetch missing data for all symbols
            for symbol in symbols:
                self._fetch_missing_data(symbol)
            
            # Start stream in background thread
            stream_thread = Thread(target=self.stream.run, daemon=True)
            stream_thread.start()
            
            self.log.scanner(f"[TIER2-ALPACA] OK WebSocket connected, subscribed to {len(symbols)} symbols")
            
        except Exception as e:
            self.log.crash(f"[TIER2-ALPACA] Error initializing WebSocket: {e}")
            
    def _update_subscriptions(self, symbols: list):
        """Subscribe to new symbols from prefilter"""
        new_symbols = set(symbols) - self.subscribed_symbols
        
        if new_symbols:
            self.log.scanner(f"[TIER2-ALPACA] Adding {len(new_symbols)} new symbols")
            
            try:
                # Define handlers
                async def quote_handler(data):
                    await self._handle_quote(data)
                
                async def trade_handler(data):
                    await self._handle_trade(data)
                
                # Subscribe to new symbols
                self.stream.subscribe_quotes(quote_handler, *new_symbols)
                self.stream.subscribe_trades(trade_handler, *new_symbols)
                
                # Fetch missing data
                for symbol in new_symbols:
                    self._fetch_missing_data(symbol)
                    self.subscribed_symbols.add(symbol)
                    
                self.log.scanner(f"[TIER2-ALPACA] OK Added {len(new_symbols)} symbols")
                
            except Exception as e:
                self.log.crash(f"[TIER2-ALPACA] Error updating subscriptions: {e}")
                    
    async def _handle_quote(self, quote):
        """Handle real-time quote update"""
        try:
            symbol = quote.symbol
            
            # Update validated data
            if symbol not in self.validated_data:
                self.validated_data[symbol] = {}
                
            self.validated_data[symbol].update({
                'symbol': symbol,
                'bid': float(quote.bid_price) if quote.bid_price else 0,
                'ask': float(quote.ask_price) if quote.ask_price else 0,
                'bid_size': quote.bid_size if quote.bid_size else 0,
                'ask_size': quote.ask_size if quote.ask_size else 0,
                'last_update': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            self.log.crash(f"[TIER2-ALPACA] Error handling quote: {e}")
            
    async def _handle_trade(self, trade):
        """Handle real-time trade update"""
        try:
            symbol = trade.symbol
            
            if symbol not in self.validated_data:
                self.validated_data[symbol] = {}
                
            self.validated_data[symbol].update({
                'price': float(trade.price),
                'volume': trade.size,
                'timestamp': trade.timestamp.isoformat()
            })
            
        except Exception as e:
            self.log.crash(f"[TIER2-ALPACA] Error handling trade: {e}")
            
    def _fetch_missing_data(self, symbol: str):
        """Fetch missing data fields using REST API"""
        try:
            import requests
            
            # Get latest quote from Alpaca
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quote = self.hist_client.get_stock_latest_quote(request)
            
            if symbol in quote:
                q = quote[symbol]
                
                if symbol not in self.validated_data:
                    self.validated_data[symbol] = {}
                    
                self.validated_data[symbol].update({
                    'symbol': symbol,
                    'bid': float(q.bid_price) if q.bid_price else 0,
                    'ask': float(q.ask_price) if q.ask_price else 0,
                    'bid_size': q.bid_size if q.bid_size else 0,
                    'ask_size': q.ask_size if q.ask_size else 0
                })
        
            # Fetch prev_close from Tradier REST API
            headers = {
                'Authorization': f'Bearer {API_KEYS["TRADIER_API_KEY"]}',
                'Accept': 'application/json'
            }
            
            response = requests.get(
                f'https://api.tradier.com/v1/markets/quotes?symbols={symbol}',
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'quotes' in data and 'quote' in data['quotes']:
                    quote_data = data['quotes']['quote']
                    if isinstance(quote_data, dict):
                        prev_close = float(quote_data.get('prevclose', 0))
                        if prev_close > 0:
                            self.validated_data[symbol]['prev_close'] = prev_close
                            self.log.scanner(f"[TIER2-TRADIER] {symbol}: prev_close = {prev_close}")
    
        except Exception as e:
            self.log.crash(f"[TIER2-ALPACA] Error fetching data for {symbol}: {e}")

            
    def _save_validated_data(self):
        """Save validated data to validated.json"""
        try:
            # Convert to list
            validated_list = list(self.validated_data.values())
            
            # Save to file
            if validated_list:
                self.fm.save_validated(validated_list)
                self.log.scanner(f"[TIER2-ALPACA] OK Saved {len(validated_list)} validated symbols")
                
        except Exception as e:
            self.log.crash(f"[TIER2-ALPACA] Error saving validated data: {e}")