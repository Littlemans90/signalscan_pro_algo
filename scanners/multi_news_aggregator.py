"""
SignalScan PRO - Multi-Provider News Aggregator
Combines GDELT, Alpaca News API, and yFinance for comprehensive news coverage
"""

import requests
from datetime import datetime, timedelta
import yfinance as yf
from core.file_manager import FileManager
from core.logger import Logger
from config.api_keys import API_KEYS

class MultiNewsAggregator:
    """Aggregates news from multiple providers on-demand"""
    
    def __init__(self, file_manager: FileManager, logger: Logger):
        self.fm = file_manager
        self.log = logger
        self.alpaca_api_key = API_KEYS.get('ALPACA_API_KEY')
        self.alpaca_secret = API_KEYS.get('ALPACA_SECRET_KEY')
    
    def fetch_news_for_symbols(self, symbols: list) -> dict:
        """Fetch news from all providers for given symbols"""
        all_news = {}
        
        # Fetch from each provider
        gdelt_news = self._fetch_gdelt(symbols)
        alpaca_news = self._fetch_alpaca(symbols)
        yfinance_news = self._fetch_yfinance(symbols)
        
        # Merge and deduplicate
        all_news.update(gdelt_news)
        all_news.update(alpaca_news)
        all_news.update(yfinance_news)
        
        self.log.news(f"[MULTI-NEWS] Aggregated {len(all_news)} articles from 3 providers")
        return all_news
    
    def _fetch_gdelt(self, symbols: list) -> dict:
        """Fetch from GDELT"""
        news = {}
        try:
            # Use existing GDELT logic from news_aggregator.py
            # Query GDELT for each symbol
            for symbol in symbols[:10]:  # Limit to avoid rate limits
                url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={symbol}&mode=artlist&maxrecords=5&format=json"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    articles = data.get('articles', [])
                    for article in articles:
                        news_id = f"gdelt_{symbol}_{article.get('seendate', '')}"
                        news[news_id] = {
                            'symbol': symbol,
                            'headline': article.get('title', 'No title'),
                            'summary': article.get('socialimage', 'No summary'),
                            'url': article.get('url', ''),
                            'timestamp': article.get('seendate', ''),
                            'provider': 'GDELT'
                        }
            self.log.news(f"[GDELT] Fetched {len([n for n in news.values() if n['provider'] == 'GDELT'])} articles")
        except Exception as e:
            self.log.news(f"[GDELT] Error: {e}")
        return news
    
    def _fetch_alpaca(self, symbols: list) -> dict:
        """Fetch from Alpaca News API"""
        news = {}
        try:
            headers = {
                'APCA-API-KEY-ID': self.alpaca_api_key,
                'APCA-API-SECRET-KEY': self.alpaca_secret
            }
            
            # Alpaca News endpoint
            symbols_str = ','.join(symbols[:50])  # Max 50 symbols per request
            url = f"https://data.alpaca.markets/v1beta1/news?symbols={symbols_str}&limit=50"
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                articles = data.get('news', [])
                for article in articles:
                    news_id = f"alpaca_{article.get('id', '')}"
                    news[news_id] = {
                        'symbol': ','.join(article.get('symbols', [])),
                        'headline': article.get('headline', 'No headline'),
                        'summary': article.get('summary', 'No summary'),
                        'url': article.get('url', ''),
                        'timestamp': article.get('created_at', ''),
                        'provider': 'Alpaca'
                    }
            self.log.news(f"[ALPACA] Fetched {len([n for n in news.values() if n['provider'] == 'Alpaca'])} articles")
        except Exception as e:
            self.log.news(f"[ALPACA] Error: {e}")
        return news
    
    def _fetch_yfinance(self, symbols: list) -> dict:
        """Fetch from yFinance"""
        news = {}
        try:
            for symbol in symbols[:20]:  # Limit to avoid slowdown
                ticker = yf.Ticker(symbol)
                articles = ticker.news
                for article in articles[:3]:  # Top 3 per symbol
                    news_id = f"yfinance_{symbol}_{article.get('uuid', '')}"
                    news[news_id] = {
                        'symbol': symbol,
                        'headline': article.get('title', 'No title'),
                        'summary': article.get('summary', 'No summary'),
                        'url': article.get('link', ''),
                        'timestamp': datetime.fromtimestamp(article.get('providerPublishTime', 0)).isoformat(),
                        'provider': 'yFinance'
                    }
            self.log.news(f"[YFINANCE] Fetched {len([n for n in news.values() if n['provider'] == 'yFinance'])} articles")
        except Exception as e:
            self.log.news(f"[YFINANCE] Error: {e}")
        return news
