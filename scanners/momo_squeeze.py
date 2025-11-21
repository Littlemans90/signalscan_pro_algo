"""
SignalScan PRO - MOMO Squeeze Strategy
TTM Squeeze with adaptive parameters and intensity scoring
Detects volatility compression before explosive breakouts
"""

import time
import math
from collections import defaultdict, deque
from datetime import datetime
from threading import Thread, Event
from queue import Queue
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from core.file_manager import FileManager
from core.logger import Logger


class MomoSqueeze(QObject):
    """
    MOMO Squeeze Scanner - TTM Squeeze Optimized
    Detects volatility compression (coiling) and breakout signals
    """
    
    # PyQt5 signal for GUI updates
    squeezesignal = pyqtSignal(dict)
    
    def __init__(self, filemanager: FileManager, logger: Logger, tier3=None):
        super().__init__()  # Initialize QObject
        self.fm = filemanager
        self.log = logger
        self.tier3 = tier3
        
        # Price history for BB/KC calculations
        self.price_history = defaultdict(lambda: deque(maxlen=50))
        self.high_history = defaultdict(lambda: deque(maxlen=50))
        self.low_history = defaultdict(lambda: deque(maxlen=50))
        self.close_history = defaultdict(lambda: deque(maxlen=50))
        
        # Squeeze state tracking
        self.squeeze_state = defaultdict(lambda: {
            'status': 'IDLE',  # IDLE, COILING, FIRED
            'bars_coiling': 0,
            'last_fire': 0
        })
        
        # Last calculation timestamp
        self.last_calc = defaultdict(float)
        
        # Scan interval
        self.scan_interval = 5  # seconds
        
        # Threading
        self.stop_event = Event()
        self.thread = None

        # Thread-safe queue for signal emissions
        self.signal_queue = Queue()
        
        # Timer to process queued signals on main thread
        self.signal_timer = QTimer()
        self.signal_timer.timeout.connect(self._process_signal_queue)
        self.signal_timer.start(100)  # Check queue every 100ms

    def _process_signal_queue(self):
        """Process queued signal emissions on the main GUI thread"""
        try:
            while not self.signal_queue.empty():
                squeeze_data = self.signal_queue.get_nowait()
                self.squeezesignal.emit(squeeze_data)
                
        except Exception as e:
            self.log.crash(f"[MOMO-SQUEEZE] Error processing signal queue: {e}")
    
    def start(self):
        """Start MOMO Squeeze scanner"""
        self.log.scanner("MOMO-SQUEEZE Starting Squeeze scanner")
        self.stop_event.clear()
        
        self.thread = Thread(target=self.run_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop MOMO Squeeze scanner"""
        self.log.scanner("MOMO-SQUEEZE Stopping Squeeze scanner")
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=5)
    
    def run_loop(self):
        """Main scanning loop"""
        while not self.stop_event.is_set():
            try:
                self.scan_squeeze()
                self.stop_event.wait(self.scan_interval)
            except Exception as e:
                self.log.crash(f"MOMO-SQUEEZE Error in run loop: {e}")
                self.stop_event.wait(10)
    
    def scan_squeeze(self):
        """Scan all active symbols for Squeeze signals"""
        try:
            if not self.tier3:
                return
            
            # Get all live data from Tier3
            livedata = getattr(self.tier3, 'livedata', {})
            
            if not livedata:
                return
            
            for symbol, data in livedata.items():
                self.update_symbol_squeeze(symbol, data)
        except Exception as e:
            self.log.crash(f"MOMO-SQUEEZE Error scanning: {e}")
    
    def update_symbol_squeeze(self, symbol: str, livedata: dict):
        """Calculate and emit Squeeze data for a symbol"""
        try:
            # Extract OHLC data
            price = livedata.get("price", 0)
            high = livedata.get("high", price)
            low = livedata.get("low", price)
            close = price
            
            if price <= 0:
                return
            
            # Update price history
            self.price_history[symbol].append(price)
            self.high_history[symbol].append(high)
            self.low_history[symbol].append(low)
            self.close_history[symbol].append(close)
            
            # Need at least 26 bars for MACD-based calculations
            if len(self.price_history[symbol]) < 26:
                return
            
            # Throttle: only recalculate every scan_interval seconds
            now = time.time()
            if now - self.last_calc[symbol] < self.scan_interval:
                return
            
            self.last_calc[symbol] = now
            
            # Calculate ATR for adaptive parameters
            atr = self._calculate_atr(symbol)
            atr_pct = (atr / price * 100) if price > 0 else 0
            
            # Determine adaptive parameters based on volatility
            bb_mult, kc_mult, length = self._get_adaptive_params(atr_pct)
            
            # Calculate Bollinger Bands
            bb_upper, bb_lower, bb_mid = self._calculate_bollinger_bands(
                symbol, length, bb_mult
            )
            
            # Calculate Keltner Channels
            kc_upper, kc_lower, kc_mid = self._calculate_keltner_channels(
                symbol, length, kc_mult, atr
            )
            
            # Detect squeeze
            squeeze_on = (bb_upper < kc_upper) and (bb_lower > kc_lower)
            
            # Calculate squeeze intensity
            intensity = self._calculate_intensity(
                bb_upper, bb_lower, kc_upper, kc_lower, atr
            )
            
            # Calculate momentum histogram
            histogram = self._calculate_momentum_histogram(symbol, length)
            
            # Update squeeze state
            previous_status = self.squeeze_state[symbol]['status']
            
            if squeeze_on:
                self.squeeze_state[symbol]['status'] = 'COILING'
                self.squeeze_state[symbol]['bars_coiling'] += 1
            else:
                # Check if just fired
                if previous_status == 'COILING':
                    self.squeeze_state[symbol]['status'] = 'FIRED'
                    self.squeeze_state[symbol]['last_fire'] = now
                    self.squeeze_state[symbol]['bars_coiling'] = 0
                elif self.squeeze_state[symbol]['status'] == 'FIRED':
                    # Stay FIRED for 3 bars (~15 seconds)
                    if now - self.squeeze_state[symbol]['last_fire'] > 15:
                        self.squeeze_state[symbol]['status'] = 'IDLE'
                else:
                    self.squeeze_state[symbol]['status'] = 'IDLE'
            
            status = self.squeeze_state[symbol]['status']
            bars_coiling = self.squeeze_state[symbol]['bars_coiling']
            
            # Determine histogram trend
            hist_trend = "bullish" if histogram > 0 else "bearish" if histogram < 0 else "neutral"
            
            # Determine setup signal
            setup = self._get_squeeze_setup(status, histogram, intensity)
            
            # Prepare GUI data
            squeezedata = {
                "symbol": symbol,
                "price": price,
                "status": status,
                "bars_coiling": bars_coiling,
                "intensity": round(intensity, 2),
                "histogram": round(histogram, 4),
                "hist_trend": hist_trend,
                "bb_width": round(bb_upper - bb_lower, 4),
                "kc_width": round(kc_upper - kc_lower, 4),
                "setup": setup,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Filter: only emit if COILING with intensity > 0.4 OR just FIRED
            if (status == 'COILING' and intensity >= 0.4) or status == 'FIRED':
                self.log.scanner(f"MOMO-SQUEEZE {symbol} | Status:{status} | Intensity:{intensity:.2f} | Hist:{histogram:.3f} | Setup:{setup}")
                self.signal_queue.put(squeezedata)
        
        except Exception as e:
            self.log.crash(f"MOMO-SQUEEZE Error updating {symbol}: {e}")
    
    def _calculate_atr(self, symbol: str, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            highs = list(self.high_history[symbol])
            lows = list(self.low_history[symbol])
            closes = list(self.close_history[symbol])
            
            if len(closes) < period + 1:
                return 0.0
            
            true_ranges = []
            for i in range(1, len(closes)):
                h = highs[i]
                l = lows[i]
                c_prev = closes[i-1]
                
                tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
                true_ranges.append(tr)
            
            # Average of last 'period' TRs
            atr = sum(true_ranges[-period:]) / period if len(true_ranges) >= period else 0
            
            return atr
        except Exception as e:
            self.log.crash(f"MOMO-SQUEEZE Error calculating ATR: {e}")
            return 0.0
    
    def _get_adaptive_params(self, atr_pct: float) -> tuple:
        """
        Get adaptive BB/KC parameters based on volatility
        Returns: (bb_mult, kc_mult, length)
        """
        # Low volatility (ATR < 2%)
        if atr_pct < 2.0:
            return (1.5, 1.0, 15)
        # High volatility (ATR > 5%)
        elif atr_pct > 5.0:
            return (2.5, 2.0, 25)
        # Normal volatility
        else:
            return (2.0, 1.5, 20)
    
    def _calculate_bollinger_bands(self, symbol: str, length: int, mult: float) -> tuple:
        """
        Calculate Bollinger Bands
        Returns: (upper, lower, middle)
        """
        try:
            prices = list(self.close_history[symbol])
            
            if len(prices) < length:
                return (0, 0, 0)
            
            # SMA (middle band)
            sma = sum(prices[-length:]) / length
            
            # Standard deviation
            variance = sum((p - sma) ** 2 for p in prices[-length:]) / length
            std_dev = math.sqrt(variance)
            
            # Upper/Lower bands
            upper = sma + (mult * std_dev)
            lower = sma - (mult * std_dev)
            
            return (upper, lower, sma)
        except Exception as e:
            self.log.crash(f"MOMO-SQUEEZE Error calculating BB: {e}")
            return (0, 0, 0)
    
    def _calculate_keltner_channels(self, symbol: str, length: int, mult: float, atr: float) -> tuple:
        """
        Calculate Keltner Channels
        Returns: (upper, lower, middle)
        """
        try:
            prices = list(self.close_history[symbol])
            
            if len(prices) < length:
                return (0, 0, 0)
            
            # SMA (middle line)
            sma = sum(prices[-length:]) / length
            
            # Upper/Lower channels
            upper = sma + (mult * atr)
            lower = sma - (mult * atr)
            
            return (upper, lower, sma)
        except Exception as e:
            self.log.crash(f"MOMO-SQUEEZE Error calculating KC: {e}")
            return (0, 0, 0)
    
    def _calculate_intensity(self, bb_upper: float, bb_lower: float, 
                           kc_upper: float, kc_lower: float, atr: float) -> float:
        """
        Calculate squeeze intensity score (0.0 to 1.0+)
        Higher = tighter compression = more explosive potential
        """
        try:
            if atr <= 0:
                return 0.0
            
            bb_width = bb_upper - bb_lower
            kc_width = kc_upper - kc_lower
            
            if kc_width <= 0:
                return 0.0
            
            # How much KC exceeds BB (normalized by ATR)
            compression = (kc_width - bb_width) / atr
            
            # Scale to 0-1+ range
            intensity = max(0, compression)
            
            return intensity
        except Exception as e:
            self.log.crash(f"MOMO-SQUEEZE Error calculating intensity: {e}")
            return 0.0
    
    def _calculate_momentum_histogram(self, symbol: str, length: int) -> float:
        """
        Calculate momentum histogram (enhanced with EMA)
        Positive = bullish, Negative = bearish
        """
        try:
            prices = list(self.close_history[symbol])
            
            if len(prices) < 26:
                return 0.0
            
            # Calculate EMAs for MACD-style momentum
            ema_12 = self._ema(prices, 12)
            ema_26 = self._ema(prices, 26)
            
            # Momentum = fast EMA - slow EMA
            momentum = ema_12 - ema_26
            
            return momentum
        except Exception as e:
            self.log.crash(f"MOMO-SQUEEZE Error calculating histogram: {e}")
            return 0.0
    
    def _ema(self, data: list, period: int) -> float:
        """Calculate Exponential Moving Average"""
        try:
            if len(data) < period:
                return sum(data) / len(data) if data else 0
            
            multiplier = 2 / (period + 1)
            ema = sum(data[:period]) / period  # Start with SMA
            
            for price in data[period:]:
                ema = (price * multiplier) + (ema * (1 - multiplier))
            
            return ema
        except:
            return 0.0
    
    def _get_squeeze_setup(self, status: str, histogram: float, intensity: float) -> str:
        """
        Determine trade setup signal
        Returns: "LONG", "SHORT", "WATCH", "WAIT"
        """
        try:
            # Just fired with bullish momentum
            if status == 'FIRED' and histogram > 0:
                return "LONG"
            
            # Just fired with bearish momentum
            elif status == 'FIRED' and histogram < 0:
                return "SHORT"
            
            # Coiling with high intensity - prepare for breakout
            elif status == 'COILING' and intensity >= 0.6:
                if histogram > 0:
                    return "WATCH LONG"
                elif histogram < 0:
                    return "WATCH SHORT"
                else:
                    return "WATCH"
            
            # Coiling with moderate intensity
            elif status == 'COILING':
                return "WAIT"
            
            else:
                return "IDLE"
        except Exception as e:
            self.log.crash(f"MOMO-SQUEEZE Error getting setup: {e}")
            return "IDLE"
