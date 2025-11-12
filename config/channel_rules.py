"""
SignalScan PRO - Channel Detection Rules
5 Channels: PreGap, HOD, RunUP, Rvsl, BKG-News
"""

CHANNEL_RULES = {
    'pregap': {
        'name': 'PreGap (Top Gapper)',
        'price_min': 1.00,
        'price_max': 15.00,
        'gap_pct_min': 10.0,
        'rvol_min': 2.0,
        'float_max': 100_000_000,
        'volume_avg_min': 500_000,
        'time_start': '04:00',  # 4:00 AM ET
        'time_end': '09:30',    # 9:30 AM ET
        'market_session': 'premarket'
    },
    
    'hod': {
        'name': 'HOD (High of Day)',
        'price_min': 1.00,
        'price_max': 15.00,
        'must_be_hod': True,
        'rvol_5min_min': 5.0,
        'float_max': 100_000_000,
        'float_low_alert': 20_000_000,  # "Low Float" alert
        'gap_pct_min': 10.0,
        'market_session': 'regular'
    },
    
    'runup': {
        'name': 'RunUP',
        'price_min': 1.00,
        'price_max': 15.00,
        'rvol_5min_min': 5.0,
        'float_max': 10_000_000,  # Some say 20M
        'float_max_alt': 20_000_000,
        'gap_pct_min': 10.0,
        'timeframe': '5min',
        'quick_move_5min': 5.0,   # Up 5% in last 5 min
        'quick_move_10min': 10.0,  # OR up 10% in last 10 min
        'alert_sound': 'morse_code.wav',
        'market_session': 'regular'
    },
    
    'rvsl': {
        'name': 'Rvsl (Reversal)',
        'price_max': 15.00,
        'rvol_min': 8.0,
        'gap_pct_min': 8.0,  # Absolute value (±8%)
        'allow_negative_gap': True,
        'market_session': 'regular'
    },
    
    'bkgnews': {
        'name': 'BKG-News (Breaking News)',
        'news_age_max_hours': 2,
        'requires_keywords': True,
        'alert_sound': 'succession.wav',
        'button_color': 'blue',
        'flash_until_acknowledged': True
    }
}

# Market Sessions (ET)
MARKET_SESSIONS = {
    'premarket': {'start': '04:00', 'end': '09:30'},
    'regular': {'start': '09:30', 'end': '16:00'},
    'afterhours': {'start': '16:00', 'end': '20:00'}
}
