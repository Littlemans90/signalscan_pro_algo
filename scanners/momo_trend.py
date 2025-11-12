"""
SignalScan PRO - MOMO Trend Strategy
Adaptive Kalman Filter with auto-model selection
Detects sustained directional trends with confidence bands
"""

import time
import math
from collections import defaultdict, deque
from datetime import datetime
from threading import Thread, Event
from PyQt5.QtCore import QObject, pyqtSignal
import numpy as np

from core.file_manager import FileManager
from core.logger import Logger


class MomoTrend(QObject):
    """
    MOMO Trend Scanner - Adaptive Kalman Filter
    Tracks trends with multiple model selection and confidence scoring
    """
    
    # PyQt5 signal for GUI updates
    trendsignal = pyqtSignal(dict)
    
    def __init__(self, filemanager: FileManager, logger: Logger, tier3=None):
        super().__init__()  # Initialize QObject
        self.fm = filemanager
        self.log = logger
        self.tier3 = tier3
        
        # Price/volume history for Kalman calculations
        self.price_history = defaultdict(lambda: deque(maxlen=100))
        self.volume_history = defaultdict(lambda: deque(maxlen=100))
        self.high_history = defaultdict(lambda: deque(maxlen=100))
        self.low_history = defaultdict(lambda: deque(maxlen=100))
        
        # Kalman filter state for each symbol
        self.kalman_state = defaultdict(lambda: {
            'mu': 0,           # Trend estimate
            'beta': 0,         # Slope/drift
            'P': 1.0,          # Covariance (uncertainty)
            'model': 'Standard'  # Active model
        })
        
        # Last calculation timestamp
        self.last_calc = defaultdict(float)
        
        # Scan interval
        self.scan_interval = 5  # seconds
        
        # Threading
        self.stop_event = Event()
        self.thread = None
    
    def start(self):
        """Start MOMO Trend scanner"""
        self.log.scanner("MOMO-TREND Starting Trend scanner")
        self.stop_event.clear()
        
        self.thread = Thread(target=self.run_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop MOMO Trend scanner"""
        self.log.scanner("MOMO-TREND Stopping Trend scanner")
        self.stop_event.set()
        
        if self.thread:
            self.thread.join(timeout=5)
    
    def run_loop(self):
        """Main scanning loop"""
        while not self.stop_event.is_set():
            try:
                self.scan_trend()
                self.stop_event.wait(self.scan_interval)
            except Exception as e:
                self.log.crash(f"MOMO-TREND Error in run loop: {e}")
                self.stop_event.wait(10)
    
    def scan_trend(self):
        """Scan all active symbols for Trend signals"""
        try:
            if not self.tier3:
                return
            
            # Get all live data from Tier3
            livedata = getattr(self.tier3, 'livedata', {})
            
            if not livedata:
                return
            
            for symbol, data in livedata.items():
                self.update_symbol_trend(symbol, data)
        except Exception as e:
            self.log.crash(f"MOMO-TREND Error scanning: {e}")
    
    def update_symbol_trend(self, symbol: str, livedata: dict):
        """Calculate and emit Trend data for a symbol"""
        try:
            # Extract OHLC data
            price = livedata.get("price", 0)
            volume = livedata.get("volume", 0)
            high = livedata.get("high", price)
            low = livedata.get("low", price)
            
            if price <= 0:
                return
            
            # Update price/volume history
            self.price_history[symbol].append(price)
            self.volume_history[symbol].append(volume)
            self.high_history[symbol].append(high)
            self.low_history[symbol].append(low)
            
            # Need at least 20 bars for trend detection
            if len(self.price_history[symbol]) < 20:
                return
            
            # Throttle: only recalculate every scan_interval seconds
            now = time.time()
            if now - self.last_calc[symbol] < self.scan_interval:
                return
            
            self.last_calc[symbol] = now
            
            # Calculate ATR for normalization
            atr = self._calculate_atr(symbol)
            
            # Auto-select Kalman model based on market conditions
            model = self._select_model(symbol, price, atr)
            self.kalman_state[symbol]['model'] = model
            
            # Update Kalman filter
            self._update_kalman_filter(symbol, price, volume, atr, model)
            
            # Get trend estimate and uncertainty
            mu = self.kalman_state[symbol]['mu']
            P = self.kalman_state[symbol]['P']
            
            # Calculate trend strength
            trend_strength = self._calculate_trend_strength(symbol, mu, atr)
            
            # Calculate confidence bands
            upper_band = mu + (2 * math.sqrt(P))
            lower_band = mu - (2 * math.sqrt(P))
            
            # Determine confidence level
            confidence = self._get_confidence_level(price, mu, P)
            
            # Determine trend direction
            direction = self._get_trend_direction(trend_strength)
            
            # Determine trading signal
            signal = self._get_trend_signal(trend_strength, confidence, direction)
            
            # Prepare GUI data
            trenddata = {
                "symbol": symbol,
                "price": price,
                "trend_mu": round(mu, 2),
                "trend_strength": round(trend_strength, 2),
                "model": model,
                "confidence": confidence,
                "upper_band": round(upper_band, 2),
                "lower_band": round(lower_band, 2),
                "direction": direction,
                "signal": signal,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Filter: only emit if trend_strength >= 1.5 or <= -1.5 AND confidence High/Med
            if abs(trend_strength) >= 1.5 and confidence in ['High', 'Med']:
                self.log.scanner(f"MOMO-TREND {symbol} | Strength:{trend_strength:.2f} | Model:{model} | Conf:{confidence} | Signal:{signal}")
                self.trendsignal.emit(trenddata)
        
        except Exception as e:
            self.log.crash(f"MOMO-TREND Error updating {symbol}: {e}")
    
    def _calculate_atr(self, symbol: str, period: int = 14) -> float:
        """Calculate Average True Range"""
        try:
            highs = list(self.high_history[symbol])
            lows = list(self.low_history[symbol])
            prices = list(self.price_history[symbol])
            
            if len(prices) < period + 1:
                return 0.0
            
            true_ranges = []
            for i in range(1, len(prices)):
                h = highs[i]
                l = lows[i]
                c_prev = prices[i-1]
                
                tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
                true_ranges.append(tr)
            
            atr = sum(true_ranges[-period:]) / period if len(true_ranges) >= period else 0
            
            return atr
        except Exception as e:
            self.log.crash(f"MOMO-TREND Error calculating ATR: {e}")
            return 0.0
    
    def _select_model(self, symbol: str, price: float, atr: float) -> str:
        """
        Auto-select Kalman model based on market conditions
        Returns: 'Standard', 'Vol-Adj', or 'Parkinson'
        """
        try:
            volumes = list(self.volume_history[symbol])
            highs = list(self.high_history[symbol])
            lows = list(self.low_history[symbol])
            
            if len(volumes) < 20:
                return 'Standard'
            
            # Calculate average volume
            avg_vol = sum(volumes[-20:]) / 20
            current_vol = volumes[-1]
            vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
            
            # Calculate high-low range percentage
            hl_range = (highs[-1] - lows[-1]) / price if price > 0 else 0
            
            # Model selection logic
            # Low volatility, narrow range
            if hl_range < 0.02:
                return 'Standard'
            
            # High volume trending
            elif vol_ratio > 1.5:
                return 'Vol-Adj'
            
            # High volatility, wide range
            else:
                return 'Parkinson'
        
        except Exception as e:
            self.log.crash(f"MOMO-TREND Error selecting model: {e}")
            return 'Standard'
    
    def _update_kalman_filter(self, symbol: str, price: float, volume: float, 
                             atr: float, model: str):
        """
        Update Kalman filter with new observation
        Implements adaptive process noise based on model
        """
        try:
            state = self.kalman_state[symbol]
            
            # Get previous estimates
            mu_prev = state['mu']
            beta_prev = state['beta']
            P_prev = state['P']
            
            # Initialize if first run
            if mu_prev == 0:
                state['mu'] = price
                state['P'] = 1.0
                return
            
            # Calculate adaptive process noise based on model
            if model == 'Standard':
                process_noise = 0.001
            
            elif model == 'Vol-Adj':
                volumes = list(self.volume_history[symbol])
                avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else 1
                vol_ratio = volume / avg_vol if avg_vol > 0 else 1.0
                process_noise = 0.001 * (1 + 0.3 * vol_ratio)
            
            elif model == 'Parkinson':
                # Use high-low range for noise
                hl_range = atr / price if price > 0 else 0.001
                process_noise = 0.001 * (1 + hl_range * 10)
            
            else:
                process_noise = 0.001
            
            # Prediction step
            mu_pred = mu_prev + beta_prev
            P_pred = P_prev + process_noise
            
            # Observation noise (measurement uncertainty)
            obs_noise = 0.01
            
            # Kalman gain
            K = P_pred / (P_pred + obs_noise)
            
            # Update step
            innovation = price - mu_pred
            mu_new = mu_pred + K * innovation
            P_new = (1 - K) * P_pred
            
            # Update slope estimate (simple)
            beta_new = mu_new - mu_prev
            
            # Store updated state
            state['mu'] = mu_new
            state['beta'] = beta_new
            state['P'] = P_new
        
        except Exception as e:
            self.log.crash(f"MOMO-TREND Error updating Kalman: {e}")
    
    def _calculate_trend_strength(self, symbol: str, mu: float, atr: float) -> float:
        """
        Calculate trend strength in ATR units
        Returns: -3.0 to +3.0 (positive = uptrend, negative = downtrend)
        """
        try:
            prices = list(self.price_history[symbol])
            
            if len(prices) < 20 or atr <= 0:
                return 0.0
            
            # Get mu from 20 bars ago (approximate)
            lookback = 20
            mu_past = prices[-lookback] if len(prices) >= lookback else prices[0]
            
            # Trend strength = (current_mu - past_mu) / ATR
            trend_strength = (mu - mu_past) / atr
            
            # Cap at -3 to +3
            trend_strength = max(-3, min(3, trend_strength))
            
            return trend_strength
        
        except Exception as e:
            self.log.crash(f"MOMO-TREND Error calculating strength: {e}")
            return 0.0
    
    def _get_confidence_level(self, price: float, mu: float, P: float) -> str:
        """
        Determine confidence level based on Kalman uncertainty
        Returns: 'High', 'Med', 'Low'
        """
        try:
            # Distance from trend in standard deviations
            std = math.sqrt(P)
            distance = abs(price - mu) / std if std > 0 else 0
            
            if distance < 1.0:
                return 'High'
            elif distance < 2.0:
                return 'Med'
            else:
                return 'Low'
        
        except Exception as e:
            self.log.crash(f"MOMO-TREND Error getting confidence: {e}")
            return 'Med'
    
    def _get_trend_direction(self, trend_strength: float) -> str:
        """
        Get trend direction indicator
        Returns: '⬆️ UP', '⬇️ DOWN', '➡️ FLAT'
        """
        if trend_strength >= 1.0:
            return '⬆️ UP'
        elif trend_strength <= -1.0:
            return '⬇️ DOWN'
        else:
            return '➡️ FLAT'
    
    def _get_trend_signal(self, trend_strength: float, confidence: str, direction: str) -> str:
        """
        Determine trading signal
        Returns: 'ENTER LONG', 'HOLD LONG', 'EXIT LONG', 'ENTER SHORT', 'HOLD SHORT', 'WAIT'
        """
        try:
            # Strong uptrend with high confidence
            if trend_strength >= 2.0 and confidence == 'High':
                return 'HOLD LONG'
            
            # Uptrend just established
            elif trend_strength >= 1.5 and confidence in ['High', 'Med']:
                return 'ENTER LONG'
            
            # Weak uptrend - consider exit
            elif 0.5 <= trend_strength < 1.5:
                return 'EXIT LONG'
            
            # Strong downtrend with high confidence
            elif trend_strength <= -2.0 and confidence == 'High':
                return 'HOLD SHORT'
            
            # Downtrend just established
            elif trend_strength <= -1.5 and confidence in ['High', 'Med']:
                return 'ENTER SHORT'
            
            # Weak downtrend - consider exit
            elif -1.5 < trend_strength <= -0.5:
                return 'EXIT SHORT'
            
            # No clear trend
            else:
                return 'WAIT'
        
        except Exception as e:
            self.log.crash(f"MOMO-TREND Error getting signal: {e}")
            return 'WAIT'
