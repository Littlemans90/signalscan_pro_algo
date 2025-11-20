"""
SignalScan PRO - Channel Detector
Applies channel rules to determine which channel a stock belongs to
Channels: PreGap, HOD, RunUP, Rvsl, BKG-News
"""

from datetime import datetime, time
from config.channel_rules import CHANNEL_RULES, MARKET_SESSIONS
from core.logger import Logger


class ChannelDetector:
    def __init__(self, logger: Logger):
        self.log = logger
        self.rules = CHANNEL_RULES
        
    def detect_channel(self, stock_data: dict) -> str:
        """
        Detect which channel a stock belongs to.
        Returns channel name or None if no match.
        """
        # Check each channel in priority order
        
        # 1. BKG-News (highest priority - breaking news)
        if self._check_bkgnews(stock_data):
            return 'bkgnews'
            
        # 2. PreGap (pre-market only)
        if self._check_pregap(stock_data):
            return 'pregap'
            
        # 3. RunUP (fast movers)
        if self._check_runup(stock_data):
            return 'runup'
            
        # 4. HOD (high of day breakout)
        if self._check_hod(stock_data):
            return 'hod'
            
        # 5. Rvsl (reversal)
        if self._check_rvsl(stock_data):
            return 'rvsl'
            
        return None
        
    def _check_pregap(self, data: dict) -> bool:
        """Check PreGap channel rules"""
        rules = self.rules['pregap']
        
        # Check if in pre-market session
        if not self._is_premarket():
            return False
            
        price = data.get('price', 0)
        gap_pct = data.get('gap_pct', 0)
        rvol = data.get('rvol', 0)
        float_shares = data.get('float', 0)
        volume_avg = data.get('volume_avg', 0)
        
        return (
            rules['price_min'] <= price <= rules['price_max'] and
            gap_pct >= rules['gap_pct_min'] and
            rvol >= rules['rvol_min'] and
            float_shares <= rules['float_max'] and
            volume_avg >= rules['volume_avg_min']
        )
        
    def _check_hod(self, data: dict) -> bool:
        """Check HOD channel rules"""
        rules = self.rules['hod']
        
        # Check if in regular session
        if not self._is_regular_hours():
            return False
            
        price = data.get('price', 0)
        is_hod = data.get('is_hod', False)
        rvol_5min = data.get('rvol_5min', 0)
        float_shares = data.get('float', 0)
        gap_pct = data.get('gap_pct', 0)
        
        return (
            rules['price_min'] <= price <= rules['price_max'] and
            is_hod and
            rvol_5min >= rules['rvol_5min_min'] and
            float_shares <= rules['float_max'] and
            gap_pct >= rules['gap_pct_min']
        )

    #def _check_hod(self, data: dict) -> bool:
        """Check HOD channel rules - ULTRA MINIMAL FOR TESTING"""
        price = data.get('price', 0)
        gap_pct = data.get('gap_pct', 0)
        
        # Accept anything with price > $1 and gap > 5%
        return price >= 1.0 and gap_pct >= 5.0
  
    def _check_runup(self, data: dict) -> bool:
        """Check RunUP channel rules"""
        rules = self.rules['runup']
        
        # Check if in regular session
        if not self._is_regular_hours():
            return False
            
        price = data.get('price', 0)
        rvol_5min = data.get('rvol_5min', 0)
        float_shares = data.get('float', 0)
        gap_pct = data.get('gap_pct', 0)
        move_5min = data.get('move_5min', 0)
        move_10min = data.get('move_10min', 0)
        
        return (
            rules['price_min'] <= price <= rules['price_max'] and
            rvol_5min >= rules['rvol_5min_min'] and
            float_shares <= rules['float_max'] and
            gap_pct >= rules['gap_pct_min'] and
            (move_5min >= rules['quick_move_5min'] or move_10min >= rules['quick_move_10min'])
        )
        
    def _check_rvsl(self, data: dict) -> bool:
        """Check Rvsl channel rules"""
        rules = self.rules['rvsl']
        
        # Check if in regular session
        if not self._is_regular_hours():
            return False
            
        price = data.get('price', 0)
        rvol = data.get('rvol', 0)
        gap_pct = abs(data.get('gap_pct', 0))  # Absolute value
        
        return (
            price <= rules['price_max'] and
            rvol >= rules['rvol_min'] and
            gap_pct >= rules['gap_pct_min']
        )
        
    def _check_bkgnews(self, data: dict) -> bool:
        """Check BKG-News channel rules"""
        rules = self.rules['bkgnews']
        
        has_breaking_news = data.get('has_breaking_news', False)
        news_age = data.get('news_age_hours', 999)
        
        return (
            has_breaking_news and
            news_age <= rules['news_age_max_hours']
        )
        
    def _is_premarket(self) -> bool:
        """Check if current time is in pre-market session"""
        now = datetime.now().time()
        session = MARKET_SESSIONS['premarket']
        start = datetime.strptime(session['start'], '%H:%M').time()
        end = datetime.strptime(session['end'], '%H:%M').time()
        return start <= now < end
        
    def _is_regular_hours(self) -> bool:
        """Check if current time is in regular trading hours"""
        now = datetime.now().time()
        session = MARKET_SESSIONS['regular']
        start = datetime.strptime(session['start'], '%H:%M').time()
        end = datetime.strptime(session['end'], '%H:%M').time()
        return start <= now < end

