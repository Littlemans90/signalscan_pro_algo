"""
SignalScan PRO - News Keywords
Shared keywords for both Breaking News (≤2 hrs) and General News (2-72 hrs)
Only difference is article age
"""

# Shared News Keywords (used for both breaking and general news)
NEWS_KEYWORDS = [
    # Bankruptcy & Financial Distress
    'files chapter 11', 'files chapter 7', 'files for bankruptcy', 
    'bankruptcy protection', 'receivership filed',
    
    # Cybersecurity
    'material cybersecurity incident', 'major data breach', 'ransomware attack',
    
    # Delisting & Suspension
    'notice of delisting', 'delisting determination', 'trading suspended', 
    'listing standards deficiency',
    
    # Accounting Issues
    'restates financials', 'accounting restatement', 'material weakness disclosed', 
    'non-reliance on financials',
    
    # Executive Departures
    'ceo resigns', 'cfo resigns', 'ceo terminated', 'cfo terminated', 
    'ceo steps down', 'interim ceo appointed', 'ceo ousted',
    
    # Deal Terminations
    'terminates merger agreement', 'terminates acquisition agreement', 
    'merger terminated', 'deal terminated', 'breaks merger',
    
    # Guidance Changes
    'withdraws guidance', 'guidance withdrawn', 'suspends guidance', 
    'slashes outlook', 'cuts outlook',
    
    # Debt Issues
    'covenant breach', 'loan default', 'debt default', 'missed payment',
    
    # Auditor Issues
    'auditor resigns', 'dismisses auditor', 'auditor terminated',
    
    # Dividend Changes
    'suspends dividend', 'cuts dividend', 'dividend suspended', 'eliminates dividend',
    
    # Trading Halts
    'trading halted', 'halt pending news', 'volatility halt',
    
    # Regulatory & Legal
    'sec charges', 'sec investigation', 'fda rejection', 'doj investigation', 
    'subpoena received',
    
    # FDA Approvals (Positive)
    'fda approves', 'fda approval for', 'receives fda approval', 
    'breakthrough therapy designation', 'fast track designation',
    
    # Earnings Beats (Positive)
    'beats earnings estimates', 'crushes earnings', 'blows past earnings', 
    'raises full year guidance',
    
    # Contract Wins (Positive)
    'wins contract worth', 'awarded contract valued', 'secures major contract', 
    'receives purchase order',
    
    # Analyst Upgrades (Positive)
    'upgrades to buy', 'raises price target', 'strong buy rating',
    
    # Buyouts & Acquisitions (Positive)
    'receives buyout offer', 'takeover bid at', 'acquisition offer of', 
    'agrees to be acquired', 'to be acquired for', 'buyout valued at', 
    'acquisition at premium',
    
    # Merger Agreements (Positive)
    'merger agreement signed', 'definitive merger agreement', 'announces acquisition of',
    
    # Capital Returns (Positive)
    'special dividend of', 'initiates dividend', 'announces buyback program', 
    'authorizes buyback of',
    
    # Partnerships (Positive)
    'strategic partnership with', 'joint venture with',
    
    # Clinical Trials (Positive)
    'successful trial results', 'positive phase',
    
    # Revenue Records (Positive)
    'record revenue', 'record quarterly revenue',
    
    # Notable Investors (Positive)
    'warren buffett buys',
    
    # Credit Ratings (Positive)
    'credit rating upgraded', 'rating upgrade by',
    
    # Patent & Legal Wins (Positive)
    'wins patent lawsuit', 'patent granted for',
    
    # Debt Free (Positive)
    'debt free',
    
    # Bitcoin & Crypto (High Volatility)
    'bitcoin surges', 'bitcoin rallies', 'bitcoin hits new high', 'bitcoin crashes',
    
    # Mining Operations (Crypto)
    'expands mining operations', 'increases hash rate', 'purchases mining equipment',
    
    # Bitcoin Purchases (Crypto)
    'purchases bitcoin', 'adds bitcoin to balance sheet', 'acquires bitcoin', 
    'buys bitcoin worth',
    
    # Bitcoin Regulation (Crypto)
    'bitcoin etf approval', 'spot bitcoin etf', 'sec approves bitcoin', 
    'bitcoin legal tender',
    
    # Financing
    'private placement', 'private placement financing', 'announces private placement',
    
    # Partnerships & Trials
    'executes loi', 'signs loi', 'letter of intent', 'strategic partnership',
    
    # Biotech & AI
    'crispr', 'molecule ai', 'ai breakthrough', 'clinical trial', 
    'orphan drug designation', 'phase 1 trial', 'research collaboration', 
    'technology licensing'
]

# Negative Keywords (filter out spam)
EXCLUDE_KEYWORDS = [
    'advertisement', 'sponsored', 'press release wire',
    'paid promotion', 'disclaimer', 'affiliate link'
]


def matches_news_keywords(headline: str) -> bool:
    """
    Check if headline contains ANY news keyword.
    Used for BOTH breaking news (≤2 hrs) and general news (2-72 hrs).
    Age is checked separately.
    """
    headline_lower = headline.lower()
    return any(keyword in headline_lower for keyword in NEWS_KEYWORDS)


def should_exclude(headline: str) -> bool:
    """Check if headline should be excluded (spam filter)"""
    headline_lower = headline.lower()
    return any(keyword in headline_lower for keyword in EXCLUDE_KEYWORDS)


def categorize_news_by_age(headline: str, age_hours: float) -> str:
    """
    Categorize news based on age and keyword match.
    
    Returns:
        'breaking' - ≤0.5 hours old + keyword match
        'general' - 0.5-48 hours old + keyword match
        'ignore' - Outside age range or no keyword match
    """
    # Check keyword match first
    if not matches_news_keywords(headline):
        return 'ignore'
    
    # Check if excluded
    if should_exclude(headline):
        return 'ignore'
    
    # Categorize by age
    if age_hours <= 0.5:
        return 'breaking'
    elif 0.5 < age_hours <= 48:
        return 'general'
    else:
        return 'ignore'  # Too old
