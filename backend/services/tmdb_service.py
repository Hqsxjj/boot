
import requests
import logging
import random
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

TMDB_API_URL = "https://api.themoviedb.org/3"

class TmdbService:
    def __init__(self, secret_store=None, config_store=None):
        self.secret_store = secret_store
        self.config_store = config_store
        # 简单的内存缓存
        self._cache_url = None
        self._cache_time = None
        # 搜索结果缓存
        self._search_cache = {}
        self._search_cache_time = {}

    def get_api_key(self, config=None) -> Optional[str]:
        """获取 TMDB API Key"""
        if config:
            return config.get('tmdb', {}).get('apiKey')
        if self.config_store:
            cfg = self.config_store.get_config()
            return cfg.get('tmdb', {}).get('apiKey')
        return None

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
                r'https://media\.themoviedb\.org/t/p/(?:w1920_and_h800_multi_faces|original)[^"\')\\s]+',
                r'https://image\.tmdb\.org/t/p/(?:w1920_and_h800_multi_faces|original)[^"\')\\s]+'
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

    def get_trending_week(self, config: dict = None, limit: int = 12) -> Dict[str, Any]:
        """
        获取近一周热门电影和电视剧
        
        Args:
            config: 配置字典
            limit: 返回数量限制
            
        Returns:
            热门资源列表
        """
        api_key = self.get_api_key(config)
        if not api_key:
            return {'success': False, 'error': 'TMDB API Key 未配置', 'data': []}
        
        try:
            # 获取本周热门（电影+电视剧混合）
            url = f"{TMDB_API_URL}/trending/all/week"
            params = {
                'api_key': api_key,
                'language': 'zh-CN'
            }
            
            resp = requests.get(url, params=params, timeout=15)
            
            if resp.status_code == 200:
                data = resp.json()
                results = data.get('results', [])
                
                # 格式化结果
                formatted = []
                for item in results[:limit]:
                    media_type = item.get('media_type', 'movie')
                    
                    # 获取标题和年份
                    if media_type == 'movie':
                        title = item.get('title', '')
                        original_title = item.get('original_title', '')
                        release_date = item.get('release_date', '')
                    else:
                        title = item.get('name', '')
                        original_title = item.get('original_name', '')
                        release_date = item.get('first_air_date', '')
                    
                    year = release_date[:4] if release_date else None
                    
                    # 只包含有海报的项目
                    if not item.get('poster_path'):
                        continue
                    
                    formatted.append({
                        'id': str(item.get('id')),
                        'title': title,
                        'original_title': original_title,
                        'year': int(year) if year else 2024,
                        'type': media_type,
                        'quality': '4K' if item.get('vote_average', 0) >= 7.5 else '1080P',
                        'poster_url': f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}",
                        'backdrop_url': f"https://image.tmdb.org/t/p/original{item.get('backdrop_path')}" if item.get('backdrop_path') else None,
                        'rating': round(item.get('vote_average', 0), 1),
                        'description': item.get('overview', '')[:200] if item.get('overview') else '',
                        'share_links': [
                            {
                                'source': 'Telegram 资源群',
                                'link': None,  # 需要真实数据源
                                'code': None
                            },
                            {
                                'source': '网络搜索',
                                'link': None,
                                'code': None
                            }
                        ]
                    })
                
                return {
                    'success': True,
                    'data': formatted,
                    'source': 'tmdb'
                }
            else:
                logger.error(f"TMDB trending API returned {resp.status_code}")
                return {'success': False, 'error': f'TMDB API 返回 {resp.status_code}', 'data': []}
                
        except Exception as e:
            logger.error(f"TMDB get trending failed: {e}")
            return {'success': False, 'error': str(e), 'data': []}

    # ==================== TMDB 搜索和详情 API ====================
    
    def search_movie(self, title: str, year: Optional[str] = None, config: dict = None) -> Dict[str, Any]:
        """
        搜索电影
        
        Args:
            title: 电影标题
            year: 上映年份（可选）
            config: 配置字典
            
        Returns:
            搜索结果字典
        """
        api_key = self.get_api_key(config)
        if not api_key:
            return {'success': False, 'error': 'TMDB API Key 未配置'}
        
        try:
            params = {
                'api_key': api_key,
                'query': title,
                'language': 'zh-CN',
                'include_adult': 'false'
            }
            if year:
                params['year'] = year
            
            url = f"{TMDB_API_URL}/search/movie"
            resp = requests.get(url, params=params, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                results = data.get('results', [])
                
                # 格式化结果
                formatted = []
                for item in results[:10]:  # 最多返回10个
                    formatted.append({
                        'id': item.get('id'),
                        'title': item.get('title'),
                        'original_title': item.get('original_title'),
                        'year': item.get('release_date', '')[:4] if item.get('release_date') else None,
                        'overview': item.get('overview'),
                        'poster_path': f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else None,
                        'vote_average': item.get('vote_average'),
                    })
                
                return {
                    'success': True,
                    'data': {
                        'results': formatted,
                        'total_results': data.get('total_results', 0)
                    }
                }
            else:
                return {'success': False, 'error': f'TMDB API 返回 {resp.status_code}'}
                
        except Exception as e:
            logger.error(f"TMDB search movie failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def search_tv(self, title: str, year: Optional[str] = None, config: dict = None) -> Dict[str, Any]:
        """
        搜索电视剧
        
        Args:
            title: 剧集标题
            year: 首播年份（可选）
            config: 配置字典
            
        Returns:
            搜索结果字典
        """
        api_key = self.get_api_key(config)
        if not api_key:
            return {'success': False, 'error': 'TMDB API Key 未配置'}
        
        try:
            params = {
                'api_key': api_key,
                'query': title,
                'language': 'zh-CN',
                'include_adult': 'false'
            }
            if year:
                params['first_air_date_year'] = year
            
            url = f"{TMDB_API_URL}/search/tv"
            resp = requests.get(url, params=params, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                results = data.get('results', [])
                
                # 格式化结果
                formatted = []
                for item in results[:10]:
                    formatted.append({
                        'id': item.get('id'),
                        'title': item.get('name'),
                        'original_title': item.get('original_name'),
                        'year': item.get('first_air_date', '')[:4] if item.get('first_air_date') else None,
                        'overview': item.get('overview'),
                        'poster_path': f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}" if item.get('poster_path') else None,
                        'vote_average': item.get('vote_average'),
                    })
                
                return {
                    'success': True,
                    'data': {
                        'results': formatted,
                        'total_results': data.get('total_results', 0)
                    }
                }
            else:
                return {'success': False, 'error': f'TMDB API 返回 {resp.status_code}'}
                
        except Exception as e:
            logger.error(f"TMDB search TV failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_movie_details(self, tmdb_id: int, config: dict = None) -> Dict[str, Any]:
        """
        获取电影详情
        
        Args:
            tmdb_id: TMDB 电影 ID
            config: 配置字典
            
        Returns:
            电影详情字典
        """
        api_key = self.get_api_key(config)
        if not api_key:
            return {'success': False, 'error': 'TMDB API Key 未配置'}
        
        try:
            url = f"{TMDB_API_URL}/movie/{tmdb_id}"
            params = {
                'api_key': api_key,
                'language': 'zh-CN',
                'append_to_response': 'credits,release_dates'
            }
            resp = requests.get(url, params=params, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                
                return {
                    'success': True,
                    'data': {
                        'id': data.get('id'),
                        'title': data.get('title'),
                        'original_title': data.get('original_title'),
                        'year': data.get('release_date', '')[:4] if data.get('release_date') else None,
                        'release_date': data.get('release_date'),
                        'overview': data.get('overview'),
                        'poster_path': f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else None,
                        'backdrop_path': f"https://image.tmdb.org/t/p/original{data.get('backdrop_path')}" if data.get('backdrop_path') else None,
                        'vote_average': data.get('vote_average'),
                        'runtime': data.get('runtime'),
                        'genres': [g.get('name') for g in data.get('genres', [])],
                        'imdb_id': data.get('imdb_id'),
                    }
                }
            elif resp.status_code == 404:
                return {'success': False, 'error': '电影未找到'}
            else:
                return {'success': False, 'error': f'TMDB API 返回 {resp.status_code}'}
                
        except Exception as e:
            logger.error(f"TMDB get movie details failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_tv_details(self, tmdb_id: int, config: dict = None) -> Dict[str, Any]:
        """
        获取电视剧详情
        
        Args:
            tmdb_id: TMDB 电视剧 ID
            config: 配置字典
            
        Returns:
            电视剧详情字典
        """
        api_key = self.get_api_key(config)
        if not api_key:
            return {'success': False, 'error': 'TMDB API Key 未配置'}
        
        try:
            url = f"{TMDB_API_URL}/tv/{tmdb_id}"
            params = {
                'api_key': api_key,
                'language': 'zh-CN',
                'append_to_response': 'credits,external_ids'
            }
            resp = requests.get(url, params=params, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                
                return {
                    'success': True,
                    'data': {
                        'id': data.get('id'),
                        'title': data.get('name'),
                        'original_title': data.get('original_name'),
                        'year': data.get('first_air_date', '')[:4] if data.get('first_air_date') else None,
                        'first_air_date': data.get('first_air_date'),
                        'overview': data.get('overview'),
                        'poster_path': f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else None,
                        'backdrop_path': f"https://image.tmdb.org/t/p/original{data.get('backdrop_path')}" if data.get('backdrop_path') else None,
                        'vote_average': data.get('vote_average'),
                        'number_of_seasons': data.get('number_of_seasons'),
                        'number_of_episodes': data.get('number_of_episodes'),
                        'genres': [g.get('name') for g in data.get('genres', [])],
                        'status': data.get('status'),
                    }
                }
            elif resp.status_code == 404:
                return {'success': False, 'error': '电视剧未找到'}
            else:
                return {'success': False, 'error': f'TMDB API 返回 {resp.status_code}'}
                
        except Exception as e:
            logger.error(f"TMDB get TV details failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def search(self, title: str, media_type: str = 'auto', year: Optional[str] = None, config: dict = None) -> Dict[str, Any]:
        """
        智能搜索（自动判断类型或指定类型）
        
        Args:
            title: 标题
            media_type: 'movie', 'tv', 或 'auto'
            year: 年份
            config: 配置
            
        Returns:
            搜索结果
        """
        if media_type == 'movie':
            return self.search_movie(title, year, config)
        elif media_type == 'tv':
            return self.search_tv(title, year, config)
        else:
            # 同时搜索电影和电视剧
            movie_result = self.search_movie(title, year, config)
            tv_result = self.search_tv(title, year, config)
            
            combined = []
            if movie_result.get('success'):
                for item in movie_result['data']['results']:
                    item['media_type'] = 'movie'
                    combined.append(item)
            
            if tv_result.get('success'):
                for item in tv_result['data']['results']:
                    item['media_type'] = 'tv'
                    combined.append(item)
            
            # 按评分排序
            combined.sort(key=lambda x: x.get('vote_average', 0), reverse=True)
            
            return {
                'success': True,
                'data': {
                    'results': combined[:15],  # 最多15个
                    'total_results': len(combined)
                }
            }
