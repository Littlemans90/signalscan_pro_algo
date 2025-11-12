# config/settings.py

"""
SignalScan PRO - Channel Configuration & Rules
Defines all detection thresholds and categorization logic
"""

class ChannelSettings:
    """
    Channel detection rules and thresholds
    Based on blueprint specifications
    """
    
    # ========== PREGAP CHANNEL ==========
    PREGAP = {
        'name': 'PreGap',
        'display_name': 'PreGap (Top Gapper)',
        'enabled': True,
        
        # Price range
        'price_min': 2.00,
        'price_max': 20.00,
        
        # Volume requirements
        'volume_min': 100000,  # 100K minimum
        
        # % Change thresholds
        'change_min': 10.0,  # 10% minimum gain
        
        # Top gainer ranking
        'top_n': 20,  # Show top 20 gainers
        
        # Alert settings
        'sound_file': 'pregap_alert.wav',
        'alert_once': True,  # Alert once per symbol per day
    }
    
    # ========== HOD CHANNEL ==========
    HOD = {
        'name': 'HOD',
        'display_name': 'HOD (High of Day)',
        'enabled': True,
        
        # Price range
        'price_min': 1.00,
        'price_max': 15.00,
        
        # Volume requirements
        'volume_min': 50000,  # 50K minimum
        
        # Breakout requirements
        'new_high_window': 5,  # Check if price is HOD in last 5 minutes
        
        # Alert settings
        'sound_file': 'hod_alert.wav',
        'alert_cooldown': 300,  # 5 minutes between alerts for same symbol
    }
    
    # ========== BREAKING NEWS CHANNEL ==========
    BREAKING_NEWS = {
        'name': 'BreakingNews',
        'display_name': 'Breaking News',
        'enabled': True,
        
        # Time window for "breaking" news
        'max_age_hours': 2,  # News must be ≤2 hours old
        
        # Price requirements (no max - can be any price)
        'price_min': 0.01,  # Penny stocks allowed
        'price_max': None,   # No upper limit
        
        # Volume spike detection
        'volume_spike_multiplier': 2.0,  # 2x average volume
        
        # News keywords (high priority)
        'priority_keywords': [
            'FDA approval', 'clinical trial', 'merger', 'acquisition',
            'buyout', 'earnings beat', 'upgraded', 'partnership',
            'contract win', 'breakthrough', 'halted', 'resumed'
        ],
        
        # Alert settings
        'sound_file': 'news_alert.wav',
        'alert_once': True,  # Alert once per news item
    }
    
    # ========== HALT CHANNEL ==========
    HALT = {
        'name': 'Halt',
        'display_name': 'Trading Halt',
        'enabled': True,
        
        # Halt detection
        'check_interval': 60,  # Check for halts every 60 seconds
        
        # Resume detection
        'resume_alert': True,
        'resume_monitor_duration': 300,  # Monitor for 5 minutes after resume
        
        # Alert settings
        'halt_sound_file': 'halt_alert.wav',
        'resume_sound_file': 'resume_alert.wav',
    }
    
    # ========== NEWS FILTER CHANNEL ==========
    NEWS_FILTER = {
        'name': 'NewsFilter',
        'display_name': 'News (No Breaking)',
        'enabled': True,
        
        # Any news older than breaking news threshold
        'min_age_hours': 2,  # News older than 2 hours
        'max_age_hours': 72,  # But within last 3 days
        
        # Price requirements
        'price_min': 1.00,
        'price_max': 50.00,
        
        # Volume requirements
        'volume_min': 100000,
        
        # Alert settings
        'sound_file': 'news_filter_alert.wav',
        'alert_once': True,
    }
    
    # ========== GLOBAL SETTINGS ==========
    GLOBAL = {
        # Market hours (ET)
        'market_open': '09:30',
        'market_close': '16:00',
        'premarket_start': '04:00',
        'afterhours_end': '20:00',
        
        # Scan intervals
        'prefilter_interval': 60,  # Tier 1 scan every 60 seconds
        'validation_interval': 5,   # Tier 2/3 update every 5 seconds
        
        # Daily reset
        'reset_time': '00:00',  # Midnight ET
        
        # UI refresh
        'ui_refresh_rate': 1,  # Update display every 1 second
        
        # Debug mode
        'debug': True,
        'verbose_logging': True,
    }
    
    # ========== API RATE LIMITS ==========
    RATE_LIMITS = {
        # yFinance (Tier 1)
        'yfinance_batch_size': 100,  # Fetch 100 symbols at once
        'yfinance_delay': 1,  # 1 second between batches
        
        # Alpaca (Tier 2 + News)
        'alpaca_ws_reconnect_delay': 5,
        'alpaca_news_max_items': 50,
        
        # Tradier (Tier 3)
        'tradier_ws_reconnect_delay': 5,
        'tradier_quotes_batch_size': 50,
        
        # News APIs (backup providers)
        'polygon_calls_per_minute': 5,
        'fmp_calls_per_minute': 250,
        'newsapi_calls_per_day': 100,
    }
    
    # ========== UNIVERSE SETTINGS ==========
    UNIVERSE = {
        # Starting universe (can be customized)
        'default_symbols': [
            # Major indices for reference
            'SPY', 'QQQ', 'IWM',
            
            # High-volume tickers (always monitor)
            'AAPL', 'TSLA', 'AMD', 'NVDA', 'AMZN', 'MSFT',
            
            # Will auto-expand based on:
            # - Top gainers from yFinance
            # - Trending tickers from Alpaca news
            # - Halt resumptions
        ],
        
        # Auto-expand universe
        'auto_expand': True,
        'max_symbols': 500,  # Monitor up to 500 symbols
        
        # Filters
        'exclude_otc': True,  # Exclude OTC stocks
        'exclude_crypto': True,  # Exclude crypto
        'min_price': 0.10,  # Exclude sub-$0.10 stocks
    }

# Export for main.py compatibility
SETTINGS = {
    'channels': [
        {'id': 'pregap', 'name': 'PreGap (Top Gapper)'},
        {'id': 'hod', 'name': 'HOD (High of Day)'},
        {'id': 'breaking_news', 'name': 'Breaking News'},
        {'id': 'halt', 'name': 'Trading Halt'},
        {'id': 'news', 'name': 'News (No Breaking)'}
    ]
}