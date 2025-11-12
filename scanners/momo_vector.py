"""
SignalScan PRO - MOMO Vector Strategy
Multi-timeframe VWAP momentum detection with volume quality filtering
Outputs: V-Score (-10 to +10), MTF alignment, volume quality, VWAP distance
"""

import time
import math
from collections import defaultdict, deque
from datetime import datetime
from threading import Thread, Event
from PyQt5.QtCore import QObject, pyqtSignal

from core.file_manager import FileManager
from core.logger import Logger


class MomoVector(QObject):
    """
    MOMO Vector Scanner - Multi-timeframe VWAP momentum
    Detects explosive moves with institutional volume backing
    """
    
    # PyQt5 signal for GUI updates
    vectorsignal = pyqtSignal(dict)
    
    def __init__(self, filemanager: FileManager, logger: Logger, tier3=None):
        super().__init__()  # Initialize QObject
        self.fm = filemanager
        self.log = logger
        self.tier3 = tier3
        
        # Price/volume history for VWAP calculations
        # {symbol: {'1min': deque([...]), '5min': deque([...]), '15min': deque([...])}}
        self.price_history = defaultdict(lambda: {
            '1min': deque(maxlen=20),
            '5min': deque(maxlen=50),
            '15min': deque(maxlen=100)
        })
        self.volume_history = defaultdict(lambda: {
            '1min': deque(maxlen=20),
            '5min': deque(maxlen=50),
            '15min': deque(maxlen=100)
        })
        
        # VWAP tracking
        self.vwap_data = defaultdict(lambda: {
            '1min': {'sum_pv': 0, 'sum_v': 0, 'vwap': 0},
            '5min': {'sum_pv': 0, 'sum_v': 0, 'vwap': 0},
            '15min': {'sum_pv': 0, 'sum_v': 0, 'vwap': 0}
        })
        
        # Timeframe counters (track bar boundaries)
        self.bar_counters = defaultdict(lambda: {
            '1min': 0,
            '5min': 0,
            '15min': 0
        })
        
        # Last calculation timestamp
        self.last_calc = defaultdict(float)
        
        # Scan interval
        self.scan_interval = 5  # seconds
        
        # Threading
        self.stop_event = Event()
        self.thread = None
    
    def start(self):
        """Start MOMO Vector scanner"""
        self.log.scanner("MOMO-VECTOR Starting Vector scanner")
        self.stop_event.clear()
        
        self.thread = Thread(target=self.run_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop MOMO Vector scanner"""
        self.log.scanner("MOMO-VECTOR Stopping Vector scanner")
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=5)
    
    def run_loop(self):
        """Main scanning loop"""
        while not self.stop_event.is_set():
            try:
                self.scan_vector()
                self.stop_event.wait(self.scan_interval)
            except Exception as e:
                self.log.crash(f"MOMO-VECTOR Error in run loop: {e}")
                self.stop_event.wait(10)
    
    def scan_vector(self):
        """Scan all active symbols for Vector signals"""
        try:
            if not self.tier3:
                return
            
            # Get all live data from Tier3
            livedata = getattr(self.tier3, 'livedata', {})
            
            if not livedata:
                return
            
            for symbol, data in livedata.items():
                self.update_symbol_vector(symbol, data)
        except Exception as e:
            self.log.crash(f"MOMO-VECTOR Error scanning: {e}")
    
    def update_symbol_vector(self, symbol: str, livedata: dict):
        """Calculate and emit Vector data for a symbol"""
        try:
            # Extract price/volume
            price = livedata.get("price", 0)
            volume = livedata.get("volume", 0)
            
            if price <= 0:
                return
            
            # Update price/volume history for all timeframes
            now = time.time()
            
            # 1-min bars (update every ~60 seconds)
            if now - self.bar_counters[symbol]['1min'] >= 60:
                self.price_history[symbol]['1min'].append(price)
                self.volume_history[symbol]['1min'].append(volume)
                self.bar_counters[symbol]['1min'] = now
            
            # 5-min bars (update every ~300 seconds)
            if now - self.bar_counters[symbol]['5min'] >= 300:
                self.price_history[symbol]['5min'].append(price)
                self.volume_history[symbol]['5min'].append(volume)
                self.bar_counters[symbol]['5min'] = now
            
            # 15-min bars (update every ~900 seconds)
            if now - self.bar_counters[symbol]['15min'] >= 900:
                self.price_history[symbol]['15min'].append(price)
                self.volume_history[symbol]['15min'].append(volume)
                self.bar_counters[symbol]['15min'] = now
            
            # Always update VWAP with current data (cumulative)
            for tf in ['1min', '5min', '15min']:
                pv = price * volume
                self.vwap_data[symbol][tf]['sum_pv'] += pv
                self.vwap_data[symbol][tf]['sum_v'] += volume
                
                if self.vwap_data[symbol][tf]['sum_v'] > 0:
                    self.vwap_data[symbol][tf]['vwap'] = (
                        self.vwap_data[symbol][tf]['sum_pv'] / 
                        self.vwap_data[symbol][tf]['sum_v']
                    )
            
            # Only calculate if we have enough data
            if len(self.price_history[symbol]['1min']) < 5:
                return
            
            # Throttle: only recalculate every scan_interval seconds
            if now - self.last_calc[symbol] < self.scan_interval:
                return
            
            self.last_calc[symbol] = now
            
            # Calculate Vector scores for each timeframe
            v_1min = self._calculate_vector_score(symbol, '1min')
            v_5min = self._calculate_vector_score(symbol, '5min')
            v_15min = self._calculate_vector_score(symbol, '15min')
            
            # Multi-timeframe weighted composite
            # Weights: 1min=50%, 5min=30%, 15min=20%
            v_score = (v_1min * 0.5) + (v_5min * 0.3) + (v_15min * 0.2)
            
            # Calculate volume quality
            vol_quality = self._calculate_volume_quality(symbol, livedata)
            
            # Calculate VWAP distance (in ATR units)
            vwap_dist = self._calculate_vwap_distance(symbol, price)
            
            # Determine MTF alignment
            mtf_alignment = self._get_mtf_alignment(v_1min, v_5min, v_15min)
            
            # Determine signal
            signal = self._get_vector_signal(v_score, vol_quality, vwap_dist)
            
            # Prepare GUI data
            vectordata = {
                "symbol": symbol,
                "price": price,
                "v_score": round(v_score, 2),
                "v_1min": round(v_1min, 2),
                "v_5min": round(v_5min, 2),
                "v_15min": round(v_15min, 2),
                "mtf_alignment": mtf_alignment,
                "vol_quality": round(vol_quality, 2),
                "vwap_dist": round(vwap_dist, 2),
                "vwap": round(self.vwap_data[symbol]['1min']['vwap'], 2),
                "signal": signal,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Filter: only emit if V-Score >= 4.0 or <= -4.0 AND vol_quality > 1.2
            if (abs(v_score) >= 4.0 and vol_quality >= 1.2):
                self.log.scanner(f"MOMO-VECTOR {symbol} | V-Score:{v_score:.1f} | MTF:{mtf_alignment} | VQ:{vol_quality:.2f} | Signal:{signal}")
                self.vectorsignal.emit(vectordata)
        
        except Exception as e:
            self.log.crash(f"MOMO-VECTOR Error updating {symbol}: {e}")
    
    def _calculate_vector_score(self, symbol: str, timeframe: str) -> float:
        """
        Calculate Vector score for a specific timeframe
        Returns: -10 to +10 scale
        """
        try:
            prices = list(self.price_history[symbol][timeframe])
            volumes = list(self.volume_history[symbol][timeframe])
            
            if len(prices) < 3:
                return 0.0
            
            # Calculate VWAP slope
            vwap_current = self.vwap_data[symbol][timeframe]['vwap']
            
            # Get VWAP from n bars ago (use 1/3 of history)
            lookback = max(1, len(prices) // 3)
            
            # Approximate past VWAP (simplified)
            past_sum_pv = sum(p * v for p, v in zip(prices[:lookback], volumes[:lookback]))
            past_sum_v = sum(volumes[:lookback])
            vwap_past = past_sum_pv / past_sum_v if past_sum_v > 0 else vwap_current
            
            # Calculate slope
            delta_vwap = vwap_current - vwap_past
            delta_t = lookback  # bars
            
            if delta_t == 0:
                return 0.0
            
            slope = delta_vwap / delta_t
            
            # Convert to angle using arctan, normalize to -10 to +10
            angle_rad = math.atan(slope * 100)  # Scale for visibility
            vector_score = (angle_rad / (math.pi / 2)) * 10
            
            # Cap at -10 to +10
            vector_score = max(-10, min(10, vector_score))
            
            return vector_score
        except Exception as e:
            self.log.crash(f"MOMO-VECTOR Error calculating vector score: {e}")
            return 0.0
    
    def _calculate_volume_quality(self, symbol: str, livedata: dict) -> float:
        """
        Calculate volume quality: (CurrentVol / AvgVol) * (1 - Spread/Price)
        Returns: 0.0 to 3.0+ scale
        """
        try:
            current_vol = livedata.get("volume", 0)
            avg_vol = livedata.get("volumeavg", 1)
            
            price = livedata.get("price", 0)
            bid = livedata.get("bid", 0)
            ask = livedata.get("ask", 0)
            
            if avg_vol <= 0 or price <= 0:
                return 0.0
            
            vol_ratio = current_vol / avg_vol
            
            # Calculate spread quality
            spread = abs(ask - bid) if (ask > 0 and bid > 0) else 0
            spread_pct = spread / price if price > 0 else 0
            spread_quality = 1 - spread_pct
            
            # Volume quality = vol_ratio * spread_quality
            vol_quality = vol_ratio * max(0, spread_quality)
            
            return vol_quality
        except Exception as e:
            self.log.crash(f"MOMO-VECTOR Error calculating volume quality: {e}")
            return 0.0
    
    def _calculate_vwap_distance(self, symbol: str, price: float) -> float:
        """
        Calculate distance from VWAP in ATR units
        Returns: -3.0 to +3.0 (positive = above VWAP, negative = below)
        """
        try:
            vwap = self.vwap_data[symbol]['1min']['vwap']
            
            if vwap <= 0:
                return 0.0
            
            # Get price history for ATR calculation
            prices = list(self.price_history[symbol]['1min'])
            
            if len(prices) < 14:
                # Simple percentage distance
                return (price - vwap) / vwap * 100
            
            # Calculate ATR (simplified)
            ranges = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
            atr = sum(ranges[-14:]) / 14 if len(ranges) >= 14 else sum(ranges) / len(ranges)
            
            if atr <= 0:
                return 0.0
            
            # Distance in ATR units
            distance = (price - vwap) / atr
            
            return distance
        except Exception as e:
            self.log.crash(f"MOMO-VECTOR Error calculating VWAP distance: {e}")
            return 0.0
    
    def _get_mtf_alignment(self, v_1min: float, v_5min: float, v_15min: float) -> str:
        """
        Get multi-timeframe alignment indicator
        Returns: "⬆️⬆️⬆️", "⬆️⬆️➡️", "⬇️⬇️⬇️", etc.
        """
        def get_arrow(score):
            if score >= 2.0:
                return "⬆️"
            elif score <= -2.0:
                return "⬇️"
            else:
                return "➡️"
        
        return f"{get_arrow(v_1min)}{get_arrow(v_5min)}{get_arrow(v_15min)}"
    
    def _get_vector_signal(self, v_score: float, vol_quality: float, vwap_dist: float) -> str:
        """
        Determine trading signal
        Returns: "STRONG BUY", "BUY", "STRONG SELL", "SELL", "WATCH"
        """
        try:
            # Strong buy: High vector + high volume + near VWAP
            if v_score >= 6.0 and vol_quality >= 2.0 and vwap_dist < 2.0:
                return "STRONG BUY"
            
            # Buy: Positive vector + decent volume
            elif v_score >= 4.0 and vol_quality >= 1.2:
                return "BUY"
            
            # Strong sell: High negative vector + high volume
            elif v_score <= -6.0 and vol_quality >= 2.0 and vwap_dist > -2.0:
                return "STRONG SELL"
            
            # Sell: Negative vector + decent volume
            elif v_score <= -4.0 and vol_quality >= 1.2:
                return "SELL"
            
            # Watch: Moderate signal
            else:
                return "WATCH"
        except Exception as e:
            self.log.crash(f"MOMO-VECTOR Error getting signal: {e}")
            return "WATCH"
