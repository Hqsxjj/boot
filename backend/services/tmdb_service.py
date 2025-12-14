
import requests
import logging
import random
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

TMDB_API_URL = "https://api.themoviedb.org/3"

class TmdbService:
    def __init__(self, secret_store=None):
        self.secret_store = secret_store
        # 简单的内存缓存
        self._cache_url = None
        self._cache_time = None

    def get_api_key(self, config):
        return config.get('tmdb', {}).get('apiKey')

    def get_trending_wallpaper(self, config):
        # Check cache (1 hour)
        if self._cache_url and self._cache_time:
            if datetime.now() - self._cache_time < timedelta(hours=1):
                return self._cache_url

        url = self._fetch_new_wallpaper(config)
        if url:
            self._cache_url = url
            self._cache_time = datetime.now()
        
        return url

    def _fetch_new_wallpaper(self, config):
        api_key = self.get_api_key(config)
        
        # 1. Try API if key exists
        if api_key:
            try:
                logger.info("Fetching TMDB wallpaper via API...")
                url = f"{TMDB_API_URL}/trending/all/week?api_key={api_key}&language=zh-CN"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get('results', [])
                    # Filter only items with backdrop
                    candidates = [item for item in results if item.get('backdrop_path')]
                    if candidates:
                        # Pick one from top 5
                        item = random.choice(candidates[:5])
                        backdrop = item.get('backdrop_path')
                        return f"https://image.tmdb.org/t/p/original{backdrop}"
            except Exception as e:
                logger.error(f"TMDB API failed: {e}")

        # 2. Scrape Fallback
        return self._scrape_homepage()

    def _scrape_homepage(self):
        try:
            logger.info("Scraping TMDB homepage for wallpaper...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
            }
            resp = requests.get("https://www.themoviedb.org/", headers=headers, timeout=10)
            
            # Regex for new media domain (media.themoviedb.org)
            # Example: https://media.themoviedb.org/t/p/w1920_and_h800_multi_faces/xyz.jpg
            patterns = [
                r'https://media\.themoviedb\.org/t/p/(?:w1920_and_h800_multi_faces|original)[^"\')\s]+',
                r'https://image\.tmdb\.org/t/p/(?:w1920_and_h800_multi_faces|original)[^"\')\s]+'
            ]
            
            for p in patterns:
                matches = re.findall(p, resp.text)
                if matches:
                    # Return a random one if multiple found, or just the first
                    return matches[0]
            
            logger.warning("No wallpaper found via scraping.")

        except Exception as e:
            logger.error(f"Scrape failed: {e}")
        
        return None
