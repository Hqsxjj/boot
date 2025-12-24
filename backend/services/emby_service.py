import requests
import time
import urllib3
from persistence.store import DataStore
from typing import Dict, Any, List, Optional
from utils.logger import TaskLogger, get_task_logger

# 使用应用日志器，确保日志写入文件
logger = get_task_logger()

# 禁用 SSL 警告（用于自签名证书）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class EmbyService:
    """Service for handling Emby server integration."""
    
    # 默认请求头（某些反代需要 User-Agent 才能正常响应）
    DEFAULT_HEADERS = {
        'User-Agent': 'Boot-Emby-Client/1.0',
        'Accept': 'application/json',
    }
    
    def __init__(self, store: DataStore):
        self.store = store
        self.timeout = 30  # 增加超时时间以支持跨网络反代
    
    def _get_config(self) -> Dict[str, Any]:
        """Get Emby configuration from store."""
        try:
            config = self.store.get_config()
            return config.get('emby', {})
        except Exception:
            return {}
    
    def _get_proxy_config(self) -> Dict[str, str]:
        """
        获取代理配置。
        优先级：
        1. 环境变量 (HTTP_PROXY, HTTPS_PROXY) - 用于 Docker 容器
        2. 配置文件中的代理设置
        返回 requests 库使用的 proxies 字典格式。
        """
        import os
        
        # 首先检查环境变量（Docker 容器场景）
        http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
        https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
        
        if http_proxy or https_proxy:
            proxies = {}
            if http_proxy:
                proxies['http'] = http_proxy
            if https_proxy:
                proxies['https'] = https_proxy
            return proxies
        
        # 然后检查配置文件中的代理设置
        try:
            config = self.store.get_config()
            proxy_config = config.get('proxy', {})
            
            if not proxy_config.get('enabled', False):
                return {}
            
            proxy_type = proxy_config.get('type', 'http').lower()
            host = proxy_config.get('host', '').strip()
            port = proxy_config.get('port', '').strip()
            username = proxy_config.get('username', '').strip()
            password = proxy_config.get('password', '').strip()
            
            if not host or not port:
                return {}
            
            # 构建代理 URL
            if username and password:
                proxy_url = f"{proxy_type}://{username}:{password}@{host}:{port}"
            else:
                proxy_url = f"{proxy_type}://{host}:{port}"
            
            return {
                'http': proxy_url,
                'https': proxy_url
            }
        except Exception:
            return {}
    
    def _should_verify_ssl(self, url: str) -> bool:
        """
        判断是否需要验证 SSL。
        对于 https 连接，返回 False 以跳过验证（支持自签名证书）。
        """
        return not url.startswith('https://')
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        统一的请求方法，自动处理 SSL 验证、代理和默认请求头。
        支持通过反代或代理访问 Emby 服务器。
        """
        # 对 https 连接跳过 SSL 验证（支持自签名证书和反代）
        if 'verify' not in kwargs:
            kwargs['verify'] = self._should_verify_ssl(url)
        
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
        
        # 应用代理配置（如果启用）
        if 'proxies' not in kwargs:
            proxies = self._get_proxy_config()
            if proxies:
                kwargs['proxies'] = proxies
        
        # 合并默认请求头（支持反代检测）
        headers = kwargs.get('headers', {})
        for key, value in self.DEFAULT_HEADERS.items():
            if key not in headers:
                headers[key] = value
        kwargs['headers'] = headers
        
        if method.upper() == 'GET':
            return requests.get(url, **kwargs)
        elif method.upper() == 'POST':
            return requests.post(url, **kwargs)
        else:
            return requests.request(method, url, **kwargs)
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Emby server."""
        config = self._get_config()
        server_url = config.get('serverUrl', '').strip()
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {
                'success': False,
                'latency': 0,
                'msg': '请先配置服务器地址和 API Key'
            }
        
        # 确保 URL 格式正确
        server_url = server_url.rstrip('/')
        
        try:
            start_time = time.time()
            
            # Test connection by making a simple API call
            response = self._make_request(
                'GET',
                f'{server_url}/emby/System/Info',
                params={'api_key': api_key}
            )
            
            latency = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                # 尝试解析响应确认是 Emby 服务器
                try:
                    data = response.json()
                    server_name = data.get('ServerName', 'Emby')
                    version = data.get('Version', '')
                    return {
                        'success': True,
                        'latency': latency,
                        'msg': f'已连接到 {server_name} {version} ({latency}ms)'
                    }
                except:
                    return {
                        'success': True,
                        'latency': latency,
                        'msg': f'连接成功 ({latency}ms)'
                    }
            elif response.status_code == 401:
                return {
                    'success': False,
                    'latency': latency,
                    'msg': 'API Key 无效或已过期'
                }
            elif response.status_code == 403:
                return {
                    'success': False,
                    'latency': latency,
                    'msg': '访问被拒绝，请检查反代配置或防火墙'
                }
            elif response.status_code == 404:
                return {
                    'success': False,
                    'latency': latency,
                    'msg': '地址无效，请检查 URL 是否正确'
                }
            elif response.status_code == 502:
                return {
                    'success': False,
                    'latency': latency,
                    'msg': '反代网关错误，上游 Emby 服务不可达'
                }
            elif response.status_code == 503:
                return {
                    'success': False,
                    'latency': latency,
                    'msg': 'Emby 服务暂时不可用'
                }
            elif response.status_code == 504:
                return {
                    'success': False,
                    'latency': latency,
                    'msg': '反代网关超时，请检查 Emby 服务器状态'
                }
            else:
                return {
                    'success': False,
                    'latency': latency,
                    'msg': f'连接失败: HTTP {response.status_code}'
                }
        except requests.Timeout:
            return {
                'success': False,
                'latency': 0,
                'msg': '连接超时 (30秒)，请检查网络或反代响应速度'
            }
        except requests.ConnectionError as e:
            error_msg = str(e).lower()
            # 提供更友好的错误信息
            if 'ssl' in error_msg or 'certificate' in error_msg:
                return {
                    'success': False,
                    'latency': 0,
                    'msg': 'SSL 证书验证失败'
                }
            elif 'name or service not known' in error_msg or 'getaddrinfo' in error_msg:
                return {
                    'success': False,
                    'latency': 0,
                    'msg': 'DNS 解析失败，请检查域名是否正确'
                }
            elif 'connection refused' in error_msg:
                return {
                    'success': False,
                    'latency': 0,
                    'msg': '连接被拒绝，目标端口未开放或服务未启动'
                }
            elif 'network is unreachable' in error_msg:
                return {
                    'success': False,
                    'latency': 0,
                    'msg': '网络不可达，请检查网络连接'
                }
            return {
                'success': False,
                'latency': 0,
                'msg': f'连接错误: {str(e)[:100]}'
            }
        except Exception as e:
            return {
                'success': False,
                'latency': 0,
                'msg': f'错误: {str(e)[:100]}'
            }
    
    def get_series_list(self) -> Dict[str, Any]:
        """
        获取 Emby 中所有电视剧列表（用于逐个扫描缺集）
        
        返回:
        {
            'success': True,
            'data': [
                {'id': 'xxx', 'name': '剧名', 'poster': 'poster_url', 'tmdbId': '123'}
            ]
        }
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {'success': False, 'data': [], 'error': 'Emby未配置'}
        
        logger.info(f"开始获取电视剧列表: {server_url}")
        
        try:
            series_response = self._make_request(
                'GET',
                f'{server_url}/emby/Items',
                params={
                    'api_key': api_key,
                    'IncludeItemTypes': 'Series',
                    'Recursive': 'true',
                    'Fields': 'ProviderIds',
                    'SortBy': 'SortName',
                    'SortOrder': 'Ascending'
                },
                timeout=30
            )
            
            if series_response.status_code != 200:
                return {'success': False, 'data': [], 'error': f'Emby请求失败: {series_response.status_code}'}
            
            series_list = series_response.json().get('Items', [])
            result = []
            
            for series in series_list:
                series_id = series.get('Id')
                series_name = series.get('Name', '未知')
                tmdb_id = series.get('ProviderIds', {}).get('Tmdb')
                poster_path = None
                
                if series.get('ImageTags', {}).get('Primary'):
                    poster_path = f"{server_url}/emby/Items/{series_id}/Images/Primary?api_key={api_key}&maxWidth=200"
                
                result.append({
                    'id': series_id,
                    'name': series_name,
                    'poster': poster_path,
                    'tmdbId': tmdb_id
                })
            
            logger.info(f"电视剧列表获取完成: 共 {len(result)} 部")
            return {'success': True, 'data': result}
        except Exception as e:
            logger.error(f"获取电视剧列表失败: {e}")
            return {'success': False, 'data': [], 'error': str(e)}
    
    _working_tmdb_domain = None
    TMDB_DOMAINS = [
        'api.tmdb.org',           # 无 "the" 的域名，国内可能可访问
        'api.themoviedb.org',     # 官方域名
        'tmdb.org',               # 简短域名
    ]

    def _fetch_tmdb_season_robust(self, series_tmdb_id, season_num, tmdb_api_key, tmdb_lang):
        """
        获取 TMDB 季度信息，支持多域名回退、代理配置和智能重试。
        """
        params = {'api_key': tmdb_api_key, 'language': tmdb_lang}
        proxies = self._get_proxy_config()
        
        # 获取用户配置的自定义域名
        full_config = self.store.get_config()
        user_tmdb_domain = full_config.get('tmdb', {}).get('domain', '').strip()
        
        # 准备待尝试的域名列表
        domains_to_try = []
        if self._working_tmdb_domain:
            domains_to_try.append(self._working_tmdb_domain)
            
        if user_tmdb_domain and user_tmdb_domain not in self.TMDB_DOMAINS and user_tmdb_domain != self._working_tmdb_domain:
            domains_to_try.append(user_tmdb_domain.rstrip('/'))
            
        for d in self.TMDB_DOMAINS:
            if d not in domains_to_try:
                domains_to_try.append(d)
        
        for domain in domains_to_try:
            if not domain:
                continue
                
            url = f'https://{domain}/3/tv/{series_tmdb_id}/season/{season_num}'
            
            # 尝试1: 代理请求 (如果配置了)
            if proxies:
                try:
                    resp = requests.get(url, params=params, proxies=proxies, timeout=15, verify=True)
                    if resp.status_code == 200:
                        self._working_tmdb_domain = domain
                        return resp.json()
                    elif resp.status_code == 401:
                        return None # API Key 无效
                except Exception:
                    pass
            
            # 尝试2: 直连请求
            try:
                resp = requests.get(url, params=params, timeout=8, verify=True)
                if resp.status_code == 200:
                    self._working_tmdb_domain = domain
                    return resp.json()
                elif resp.status_code == 401:
                    return None
            except requests.exceptions.SSLError:
                # SSL 错误尝试
                try:
                    resp = requests.get(url, params=params, timeout=8, verify=False)
                    if resp.status_code == 200:
                        self._working_tmdb_domain = domain
                        return resp.json()
                except Exception:
                    pass
            except Exception:
                continue
        
        return None

    def scan_missing_episodes(self) -> Dict[str, Any]:
        """
        扫描 Emby 中的电视剧缺集情况。
        使用 Emby 的 Virtual 状态判断缺集，无需 TMDB 对比。
        """
        from collections import defaultdict
        from datetime import datetime
        
        task_log = TaskLogger('Emby')
        task_log.start('扫描缺集')

        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            task_log.failure('Emby未配置')
            return {'success': False, 'data': [], 'error': 'Emby未配置'}

        try:
            # 一次性获取所有剧集
            task_log.info('正在获取所有剧集信息...')
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Items',
                params={
                    'api_key': api_key,
                    'Recursive': 'true',
                    'IncludeItemTypes': 'Episode',
                    'Fields': 'SeriesName,SeriesId,ParentIndexNumber,PremiereDate,LocationType',
                },
                timeout=60
            )
            
            if response.status_code != 200:
                task_log.failure(f'Emby请求失败: {response.status_code}')
                return {'success': False, 'data': [], 'error': f'Emby请求失败: {response.status_code}'}
            
            all_episodes = response.json().get('Items', [])
            task_log.info(f'获取到 {len(all_episodes)} 个剧集')
            
            now = datetime.now().isoformat()
            
            # 使用字典存储统计数据: stats[(剧名, 剧ID, 季)] = {owned, missing, upcoming, poster}
            stats = defaultdict(lambda: {"owned": 0, "missing": 0, "upcoming": 0, "series_id": None})
            
            for ep in all_episodes:
                series_name = ep.get('SeriesName', '未知剧集')
                series_id = ep.get('SeriesId')
                season_num = ep.get('ParentIndexNumber', 0)
                
                # 跳过特别篇 (第0季)
                if season_num == 0:
                    continue
                
                key = (series_name, series_id, season_num)
                
                is_virtual = ep.get('LocationType') == 'Virtual'
                premiere_date = ep.get('PremiereDate', '9999')
                
                # 确保 series_id 被记录
                if stats[key]["series_id"] is None:
                    stats[key]["series_id"] = series_id
                
                if not is_virtual:
                    stats[key]["owned"] += 1
                else:
                    if premiere_date < now:
                        stats[key]["missing"] += 1
                    else:
                        stats[key]["upcoming"] += 1
            
            # 格式化为前端需要的格式
            missing_data = []
            for (series_name, series_id, season_num), counts in stats.items():
                # 只添加有缺集的记录
                if counts["missing"] > 0:
                    # 获取海报
                    poster_path = None
                    if series_id:
                        poster_path = f"{server_url}/emby/Items/{series_id}/Images/Primary?api_key={api_key}&maxWidth=200"
                    
                    missing_data.append({
                        'id': f"{series_id}_{season_num}",
                        'name': series_name,
                        'season': season_num,
                        'totalEp': counts["owned"] + counts["missing"] + counts["upcoming"],
                        'localEp': counts["owned"],
                        'missingCount': counts["missing"],
                        'upcomingCount': counts["upcoming"],
                        'poster': poster_path
                    })
            
            # 按剧名和季数排序
            missing_data.sort(key=lambda x: (x['name'], x['season']))
            
            task_log.success(f'发现 {len(missing_data)} 个缺集季')
            return {'success': True, 'data': missing_data}
            
        except Exception as e:
            task_log.failure(str(e))
            logger.error(f"扫描缺集失败: {e}")
            return {'success': False, 'data': [], 'error': str(e)}

    def scan_single_series(self, series_id: str) -> Dict[str, Any]:
        """
        扫描单个电视剧的缺集情况。
        使用 Emby 的 Virtual 状态判断缺集。
        """
        from collections import defaultdict
        from datetime import datetime
        
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {'success': False, 'data': [], 'error': 'Emby未配置'}
        
        try:
            # 获取剧集基本信息（用于获取剧名和海报）
            series_response = self._make_request(
                'GET',
                f'{server_url}/emby/Items/{series_id}',
                params={'api_key': api_key},
                timeout=15
            )
            
            if series_response.status_code != 200:
                return {'success': False, 'data': [], 'error': '获取剧集信息失败'}
            
            series = series_response.json()
            series_name = series.get('Name', '未知')
            poster_path = None
            
            if series.get('ImageTags', {}).get('Primary'):
                poster_path = f"{server_url}/emby/Items/{series_id}/Images/Primary?api_key={api_key}&maxWidth=200"
            
            # 一次性获取该剧所有剧集
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Items',
                params={
                    'api_key': api_key,
                    'Recursive': 'true',
                    'IncludeItemTypes': 'Episode',
                    'ParentId': series_id,
                    'Fields': 'ParentIndexNumber,PremiereDate,LocationType',
                },
                timeout=30
            )
            
            if response.status_code != 200:
                return {'success': False, 'data': [], 'error': f'获取剧集信息失败: {response.status_code}'}
            
            all_episodes = response.json().get('Items', [])
            now = datetime.now().isoformat()
            
            # 统计各季数据
            stats = defaultdict(lambda: {"owned": 0, "missing": 0, "upcoming": 0})
            
            for ep in all_episodes:
                season_num = ep.get('ParentIndexNumber', 0)
                
                # 跳过特别篇 (第0季)
                if season_num == 0:
                    continue
                
                is_virtual = ep.get('LocationType') == 'Virtual'
                premiere_date = ep.get('PremiereDate', '9999')
                
                if not is_virtual:
                    stats[season_num]["owned"] += 1
                else:
                    if premiere_date < now:
                        stats[season_num]["missing"] += 1
                    else:
                        stats[season_num]["upcoming"] += 1
            
            # 格式化结果
            missing_data = []
            for season_num, counts in sorted(stats.items()):
                if counts["missing"] > 0:
                    missing_data.append({
                        'id': f"{series_id}_{season_num}",
                        'name': series_name,
                        'season': season_num,
                        'totalEp': counts["owned"] + counts["missing"] + counts["upcoming"],
                        'localEp': counts["owned"],
                        'missingCount': counts["missing"],
                        'upcomingCount': counts["upcoming"],
                        'poster': poster_path
                    })
            
            return {'success': True, 'data': missing_data}
        except Exception as e:
            logger.error(f"扫描失败 [{series_id}]: {e}")
            return {'success': False, 'data': [], 'error': str(e)}
    
    def refresh_library(self, library_id: str = None) -> Dict[str, Any]:
        """
        刷新 Emby 媒体库
        
        Args:
            library_id: 可选，指定要刷新的库ID，为空则刷新全部
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').strip()
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {
                'success': False,
                'error': 'Server URL and API Key are required'
            }
        
        try:
            if library_id:
                url = f'{server_url}/emby/Items/{library_id}/Refresh'
            else:
                url = f'{server_url}/emby/Library/Refresh'
            
            response = self._make_request(
                'POST',
                url,
                params={'api_key': api_key},
                timeout=self.timeout
            )
            
            if response.status_code in [200, 204]:
                return {
                    'success': True,
                    'msg': '媒体库刷新已开始'
                }
            else:
                return {
                    'success': False,
                    'error': f'刷新失败: HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_latest_items(self, limit: int = 10, item_type: str = None) -> Dict[str, Any]:
        """
        获取最新入库的项目
        
        Args:
            limit: 返回数量限制
            item_type: 项目类型 (Movie, Series, Episode, etc.)
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').strip()
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {
                'success': False,
                'data': [],
                'error': '请先配置服务器地址和 API Key'
            }
        
        try:
            params = {
                'api_key': api_key,
                'SortBy': 'DateCreated',
                'SortOrder': 'Descending',
                'Limit': limit,
                'Recursive': 'true',
                'Fields': 'Overview,Genres,Studios,People,PrimaryImageAspectRatio'
            }
            
            if item_type:
                params['IncludeItemTypes'] = item_type
            
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Items',
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                items = data.get('Items', [])
                
                # 处理每个项目，添加海报URL
                processed_items = []
                for item in items:
                    processed = {
                        'id': item.get('Id'),
                        'name': item.get('Name'),
                        'type': item.get('Type'),
                        'year': item.get('ProductionYear'),
                        'overview': item.get('Overview', ''),
                        'genres': item.get('Genres', []),
                        'date_created': item.get('DateCreated'),
                    }
                    
                    # 构建海报URL
                    if item.get('ImageTags', {}).get('Primary'):
                        processed['poster_url'] = (
                            f"{server_url}/emby/Items/{item['Id']}/Images/Primary"
                            f"?api_key={api_key}&maxHeight=400"
                        )
                    
                    processed_items.append(processed)
                
                return {
                    'success': True,
                    'data': processed_items
                }
            else:
                return {
                    'success': False,
                    'data': [],
                    'error': f'HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'success': False,
                'data': [],
                'error': str(e)
            }
    
    def get_item_details(self, item_id: str) -> Dict[str, Any]:
        """
        获取项目详细信息（海报、简介等）
        
        Args:
            item_id: Emby 项目ID
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').strip()
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {
                'success': False,
                'error': 'Server URL and API Key are required'
            }
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Items/{item_id}',
                params={
                    'api_key': api_key,
                    'Fields': 'Overview,Genres,Studios,People,PrimaryImageAspectRatio,ExternalUrls'
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                item = response.json()
                
                result = {
                    'id': item.get('Id'),
                    'name': item.get('Name'),
                    'original_title': item.get('OriginalTitle'),
                    'type': item.get('Type'),
                    'year': item.get('ProductionYear'),
                    'overview': item.get('Overview', ''),
                    'genres': item.get('Genres', []),
                    'studios': [s.get('Name') for s in item.get('Studios', [])],
                    'community_rating': item.get('CommunityRating'),
                    'official_rating': item.get('OfficialRating'),
                    'runtime_ticks': item.get('RunTimeTicks'),
                }
                
                # 海报URL
                if item.get('ImageTags', {}).get('Primary'):
                    result['poster_url'] = (
                        f"{server_url}/emby/Items/{item['Id']}/Images/Primary"
                        f"?api_key={api_key}&maxHeight=600"
                    )
                
                # 背景图URL
                if item.get('BackdropImageTags'):
                    result['backdrop_url'] = (
                        f"{server_url}/emby/Items/{item['Id']}/Images/Backdrop"
                        f"?api_key={api_key}&maxWidth=1280"
                    )
                
                return {
                    'success': True,
                    'data': result
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def format_notification_text(self, item: Dict[str, Any]) -> str:
        """
        格式化通知文本（用于Bot推送）
        
        Args:
            item: 项目信息字典
        """
        lines = []
        
        # 标题
        title = item.get('name', '未知')
        original = item.get('original_title')
        if original and original != title:
            lines.append(f"🎬 *{title}*\n_{original}_")
        else:
            lines.append(f"🎬 *{title}*")
        
        # 年份和类型
        meta = []
        if item.get('year'):
            meta.append(str(item['year']))
        if item.get('type'):
            type_map = {'Movie': '电影', 'Series': '剧集', 'Episode': '单集'}
            meta.append(type_map.get(item['type'], item['type']))
        if meta:
            lines.append(f"📅 {' | '.join(meta)}")
        
        # 评分
        if item.get('community_rating'):
            lines.append(f"⭐ 评分: {item['community_rating']:.1f}")
        
        # 类型标签
        if item.get('genres'):
            lines.append(f"🏷️ {' / '.join(item['genres'][:3])}")
        
        # 媒体信息（分辨率、编码等）
        if item.get('media_info'):
            mi = item['media_info']
            info_parts = []
            if mi.get('resolution'):
                info_parts.append(mi['resolution'])
            if mi.get('video_codec'):
                info_parts.append(mi['video_codec'])
            if mi.get('audio_codec'):
                info_parts.append(mi['audio_codec'])
            if info_parts:
                lines.append(f"📺 {' / '.join(info_parts)}")
            
            # 字幕信息
            if mi.get('subtitles'):
                lines.append(f"💬 字幕: {', '.join(mi['subtitles'][:3])}")
        
        # 简介
        overview = item.get('overview', '')
        if overview:
            if len(overview) > 300:
                overview = overview[:300] + '...'
            lines.append(f"\n📝 *简介:*\n{overview}")
        
        return '\n'.join(lines)
    
    def get_media_info(self, item_id: str) -> Dict[str, Any]:
        """
        获取媒体文件的技术信息（分辨率、编码、字幕等）
        
        Args:
            item_id: Emby 项目ID
            
        Returns:
            包含媒体流信息的字典
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').strip()
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {
                'success': False,
                'error': '需要配置服务器地址和 API Key'
            }
        
        try:
            # 获取项目的 MediaSources 信息
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Items/{item_id}',
                params={
                    'api_key': api_key,
                    'Fields': 'MediaSources,MediaStreams,Path'
                },
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}'
                }
            
            item = response.json()
            result = {
                'id': item_id,
                'name': item.get('Name'),
                'path': item.get('Path'),
                'container': None,
                'resolution': None,
                'video_codec': None,
                'audio_codec': None,
                'audio_channels': None,
                'bit_rate': None,
                'subtitles': [],
                'audio_languages': [],
            }
            
            # 解析 MediaSources
            media_sources = item.get('MediaSources', [])
            if media_sources:
                source = media_sources[0]
                result['container'] = source.get('Container', '').upper()
                result['bit_rate'] = source.get('Bitrate')
                
                # 解析 MediaStreams
                for stream in source.get('MediaStreams', []):
                    stream_type = stream.get('Type')
                    
                    if stream_type == 'Video':
                        # 视频流信息
                        width = stream.get('Width', 0)
                        height = stream.get('Height', 0)
                        
                        # 分辨率判断
                        if height >= 2160 or width >= 3840:
                            result['resolution'] = '4K'
                        elif height >= 1080 or width >= 1920:
                            result['resolution'] = '1080p'
                        elif height >= 720 or width >= 1280:
                            result['resolution'] = '720p'
                        elif height >= 480:
                            result['resolution'] = '480p'
                        else:
                            result['resolution'] = f'{width}x{height}'
                        
                        # 视频编码
                        codec = stream.get('Codec', '').upper()
                        if 'HEVC' in codec or 'H265' in codec:
                            result['video_codec'] = 'HEVC'
                        elif 'H264' in codec or 'AVC' in codec:
                            result['video_codec'] = 'H.264'
                        elif 'VP9' in codec:
                            result['video_codec'] = 'VP9'
                        elif 'AV1' in codec:
                            result['video_codec'] = 'AV1'
                        else:
                            result['video_codec'] = codec
                        
                        # HDR 信息
                        if stream.get('VideoRange') == 'HDR':
                            result['resolution'] += ' HDR'
                        if stream.get('VideoRangeType'):
                            hdr_type = stream.get('VideoRangeType')
                            if 'DolbyVision' in hdr_type:
                                result['resolution'] += ' DV'
                    
                    elif stream_type == 'Audio':
                        # 音频流信息
                        if not result['audio_codec']:
                            codec = stream.get('Codec', '').upper()
                            if 'TRUEHD' in codec:
                                result['audio_codec'] = 'TrueHD'
                            elif 'DTS' in codec:
                                if 'HD' in codec or 'MA' in codec:
                                    result['audio_codec'] = 'DTS-HD MA'
                                else:
                                    result['audio_codec'] = 'DTS'
                            elif 'EAC3' in codec or 'E-AC-3' in codec:
                                result['audio_codec'] = 'Atmos'
                            elif 'AC3' in codec:
                                result['audio_codec'] = 'AC3'
                            elif 'AAC' in codec:
                                result['audio_codec'] = 'AAC'
                            elif 'FLAC' in codec:
                                result['audio_codec'] = 'FLAC'
                            else:
                                result['audio_codec'] = codec
                            
                            result['audio_channels'] = stream.get('Channels')
                        
                        # 音频语言
                        lang = stream.get('Language') or stream.get('DisplayLanguage')
                        if lang and lang not in result['audio_languages']:
                            result['audio_languages'].append(lang)
                    
                    elif stream_type == 'Subtitle':
                        # 字幕信息
                        lang = stream.get('Language') or stream.get('DisplayLanguage') or stream.get('Title')
                        if lang:
                            # 标记内嵌/外挂字幕
                            if stream.get('IsExternal'):
                                lang += '(外挂)'
                            result['subtitles'].append(lang)
            
            return {
                'success': True,
                'data': result
            }
            
        except requests.Timeout:
            return {
                'success': False,
                'error': '请求超时'
            }
        except requests.ConnectionError:
            return {
                'success': False,
                'error': '连接失败'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def scan_and_notify(self, library_id: str = None) -> Dict[str, Any]:
        """
        扫描媒体库并获取新增项目，用于 Bot 通知
        
        Args:
            library_id: 可选，指定要扫描的库ID
            
        Returns:
            包含新增项目列表和媒体信息的字典
        """
        result = {
            'success': False,
            'scanned': False,
            'items': []
        }
        
        # 先刷新媒体库
        refresh_result = self.refresh_library(library_id)
        if refresh_result.get('success'):
            result['scanned'] = True
        
        # 等待一小段时间让 Emby 处理
        time.sleep(2)
        
        # 获取最新入库项目
        latest = self.get_latest_items(limit=5)
        if not latest.get('success'):
            result['error'] = latest.get('error', '获取最新项目失败')
            return result
        
        items_with_info = []
        for item in latest.get('data', []):
            # 获取详细信息
            details = self.get_item_details(item.get('id'))
            if details.get('success'):
                item_data = details['data']
                
                # 获取媒体技术信息
                media_info = self.get_media_info(item.get('id'))
                if media_info.get('success'):
                    item_data['media_info'] = media_info['data']
                
                items_with_info.append(item_data)
        
        result['success'] = True
        result['items'] = items_with_info
        return result

    # ==================== 从 EmbyNginxDK_ref 合并的方法 ====================

    def get_system_info(self) -> Dict[str, Any]:
        """
        获取 Emby 服务器系统信息
        
        Returns:
            包含服务器名称、版本、操作系统等信息
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {}
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/System/Info',
                params={'api_key': api_key}
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"获取系统信息失败: {e}")
        return {}

    def get_user_count(self) -> int:
        """获取用户数量"""
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return 0
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Users/Query',
                params={'api_key': api_key}
            )
            if response.status_code == 200:
                return response.json().get("TotalRecordCount", 0)
        except Exception:
            pass
        return 0

    def get_users(self) -> List[Dict[str, Any]]:
        """获取所有用户列表"""
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return []
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Users',
                params={'api_key': api_key}
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return []

    def get_admin_user(self) -> str:
        """获取管理员用户 ID"""
        users = self.get_users()
        for user in users:
            if user.get("Policy", {}).get("IsAdministrator"):
                return user.get("Id", "")
        return ""

    def get_libraries(self, user_id: str = None) -> List[Dict[str, Any]]:
        """
        获取媒体库列表
        
        Args:
            user_id: 可选，指定用户ID，为空则使用管理员
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return []
        
        if not user_id:
            user_id = self.get_admin_user()
        
        if not user_id:
            return []
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Users/{user_id}/Views',
                params={'api_key': api_key}
            )
            if response.status_code == 200:
                return response.json().get("Items", [])
        except Exception:
            pass
        return []

    def get_tv_episodes(self, series_id: str) -> List[Dict[str, Any]]:
        """获取电视剧的所有剧集"""
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not series_id or not server_url or not api_key:
            return []
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Shows/{series_id}/Episodes',
                params={'api_key': api_key, 'fields': 'DateCreated'}
            )
            if response.status_code == 200:
                return response.json().get("Items", [])
        except Exception:
            pass
        return []

    def get_medias_count(self) -> Dict[str, int]:
        """
        获取媒体数量统计
        
        Returns:
            {'movie': 数量, 'tv': 数量, 'episode': 数量}
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        default = {"movie": 0, "tv": 0, "episode": 0}
        
        if not server_url or not api_key:
            return default
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Items/Counts',
                params={'api_key': api_key}
            )
            if response.status_code == 200:
                result = response.json()
                return {
                    "movie": result.get("MovieCount", 0),
                    "tv": result.get("SeriesCount", 0),
                    "episode": result.get("EpisodeCount", 0)
                }
        except Exception:
            pass
        return default

    def get_media_play_report(self, report_type: str, user_id: str = "", days: int = 30) -> List[Dict[str, Any]]:
        """
        获取用户播放记录 (需要安装 Playback Reporting 插件)
        
        Args:
            report_type: MoviesReport | TvShowsReport
            user_id: 默认获取全部用户播放记录
            days: 默认获取最近30天内
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return []
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/user_usage_stats/{report_type}',
                params={'user_id': user_id, 'days': days, 'api_key': api_key}
            )
            if response.status_code == 200:
                result = response.json()
                if result:
                    result.sort(key=lambda x: x.get("time", 0), reverse=True)
                    # 格式化时间
                    formatted = []
                    for item in result:
                        seconds = item.get("time", 0)
                        hours = seconds // 3600
                        minutes = (seconds % 3600) // 60
                        remaining = seconds % 60
                        formatted.append({
                            "label": item.get("label", ""),
                            "time": f"{hours:02}:{minutes:02}:{remaining:02}",
                            "value": seconds
                        })
                    return formatted
        except Exception:
            pass
        return []

    def get_playing_sessions(self) -> List[Dict[str, Any]]:
        """获取当前正在播放的会话"""
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return []
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Sessions',
                params={
                    'IncludeAllSessionsIfAdmin': 'true',
                    'IsPlaying': 'true',
                    'api_key': api_key
                }
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return []

    def get_playing_media_ids(self) -> Dict[str, List[str]]:
        """
        获取正在播放的媒体ID列表
        
        Returns:
            {media_id: [device_id1, device_id2, ...]}
        """
        sessions = self.get_playing_sessions()
        result = {}
        for session in sessions:
            play_state = session.get("PlayState", {})
            media_id = play_state.get("MediaSourceId")
            device_id = session.get("DeviceId")
            if media_id:
                if media_id not in result:
                    result[media_id] = []
                if device_id:
                    result[media_id].append(device_id)
        return result

    def get_devices(self) -> List[Dict[str, Any]]:
        """获取设备列表"""
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return []
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Devices',
                params={
                    'IncludeItemTypes': 'Device',
                    'StartIndex': 0,
                    'Limit': 200,
                    'SortBy': 'DateLastActivity,SortName',
                    'SortOrder': 'Descending',
                    'api_key': api_key
                }
            )
            if response.status_code == 200:
                return response.json().get("Items", [])
        except Exception:
            pass
        return []

    def get_emby_playback_info(self, video_id: str, is_playback: str = "true") -> Dict[str, Any]:
        """
        获取视频播放信息 (用于获取直链等)
        
        Args:
            video_id: 视频 ID
            is_playback: 是否为播放请求
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {}
        
        import json as json_lib
        headers = {"Content-Type": "application/json;charset=utf-8"}
        
        try:
            media_source_id = f"mediasource_{video_id}" if video_id.isdigit() else video_id
            
            response = self._make_request(
                'POST',
                f'{server_url}/Items/{video_id}/PlaybackInfo',
                params={
                    'IsPlayback': is_playback,
                    'api_key': api_key,
                    'MediaSourceId': media_source_id
                },
                headers=headers,
                data=json_lib.dumps({})
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return {}

    def get_remote_image(self, item_id: str, image_type: str = "Backdrop") -> str:
        """
        获取项目的远程图片 URL (从 TMDB)
        
        Args:
            item_id: 项目 ID
            image_type: Backdrop | Primary | Logo 等
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return ""
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Items/{item_id}/RemoteImages',
                params={'api_key': api_key}
            )
            if response.status_code == 200:
                images = response.json().get("Images", [])
                for image in images:
                    if image.get("ProviderName") == "TheMovieDb" and image.get("Type") == image_type:
                        return image.get("Url", "")
        except Exception:
            pass
        return ""

    def upload_library_image(self, item_id: str, image_data: bytes, library_name: str = "") -> bool:
        """
        上传封面图到 Emby
        
        Args:
            item_id: 项目 ID
            image_data: 图片二进制数据
            library_name: 媒体库名称 (用于日志)
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key or not image_data:
            return False
        
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            response = self._make_request(
                'POST',
                f'{server_url}/Items/{item_id}/Images/Primary',
                params={'api_key': api_key},
                headers={"Content-Type": "image/jpeg"},
                data=image_data
            )
            if response.status_code in (200, 204):
                logger.info(f"上传 {library_name or item_id} 封面图成功")
                return True
            else:
                logger.warning(f"上传封面图失败: {response.status_code}")
        except Exception as e:
            logger.warning(f"上传封面图失败: {e}")
        return False

    def refresh_item(self, item_id: str) -> bool:
        """
        触发项目的刷新，通常用于上传新封面后强制清除缓存
        """
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return False
            
        try:
            # Emby 刷新 API
            url = f"{server_url}/Items/{item_id}/Refresh"
            params = {
                'api_key': api_key,
                'Recursive': 'true',
                'ImageRefreshMode': 'Full',
                'MetadataRefreshMode': 'Default',
                'ReplaceAllImages': 'false',
                'ReplaceAllMetadata': 'false'
            }
            response = self._make_request('POST', url, params=params)
            return response.status_code in (200, 204)
        except Exception as e:
            logger.warning(f"刷新项目失败: {e}")
        return False

    def get_library_folders(self) -> List[Dict[str, Any]]:
        """获取所有媒体库文件夹路径"""
        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return []
        
        try:
            response = self._make_request(
                'GET',
                f'{server_url}/emby/Library/SelectableMediaFolders',
                params={'api_key': api_key}
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return []

    def parse_webhook_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 Emby Webhook 消息
        
        Args:
            message: Webhook 原始消息
            
        Returns:
            {'title': str, 'description': str, 'picurl': str} 或 None
        """
        from datetime import datetime
        
        try:
            if "Item" not in message:
                return None
            
            event = message.get("Event", "")
            item = message["Item"]
            media_type = item.get("Type", "")
            
            event_message = {
                "title": "",
                "description": "",
                "picurl": ""
            }
            
            # 处理描述
            description = message.get("Description", "").replace("\u3000\u3000", "").replace("\r", "")
            overview = item.get("Overview", "").replace("\u3000\u3000", "").replace("\r", "")
            
            if description:
                description = f"剧情：{description[:100]}..." if len(description) > 100 else f"剧情：{description}"
            elif overview:
                description = f"剧情：{overview[:100]}..." if len(overview) > 100 else f"剧情：{overview}"
            
            year = f" ({item.get('ProductionYear')})" if 'ProductionYear' in item else ""
            
            if event.startswith("playback"):
                # 播放事件
                client_info = ""
                if "Session" in message:
                    session = message["Session"]
                    client_info = f"IP地址：{session.get('RemoteEndPoint', '')}\n客户端：{session.get('Client', '')} {session.get('ApplicationVersion', '')}\n"
                
                event_message["description"] = f"{description}\n{client_info}时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                event_message["title"] = message.get("Title", "")
                
                # 获取背景图
                pic_url = self.get_remote_image(item.get("Id", ""), "Backdrop")
                if not pic_url and media_type == "Episode":
                    pic_url = self.get_remote_image(item.get("SeriesId", ""), "Backdrop")
                event_message["picurl"] = pic_url
                
            elif event == "library.new":
                # 新入库事件
                event_message["description"] = f"{description}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                if media_type == "Series":
                    event_message["title"] = f"新入库剧集 {item.get('Name', '')}{year}"
                    event_message["picurl"] = self.get_remote_image(item.get("Id", ""), "Backdrop")
                elif media_type == "Episode":
                    event_message["title"] = f"新入库剧集 {item.get('SeriesName', '')} S{item.get('ParentIndexNumber', '')}E{item.get('IndexNumber', '')} {item.get('Name', '')}"
                    event_message["picurl"] = self.get_remote_image(item.get("Id", ""), "Primary") or self.get_remote_image(item.get("SeriesId", ""), "Backdrop")
                elif media_type == "Movie":
                    event_message["title"] = f"新入库电影 {item.get('Name', '')}{year}"
                    event_message["picurl"] = self.get_remote_image(item.get("Id", ""), "Backdrop")
                    
            elif event == "library.deleted":
                # 删除事件
                event_message["description"] = f"{description}\n时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                event_message["picurl"] = "https://cdn.pixabay.com/photo/2017/07/18/23/23/folder-2517423_1280.png"
                
                if media_type == "Folder":
                    return None
                elif media_type == "Movie":
                    event_message["title"] = f"删除电影 {item.get('Name', '')}{year}"
                elif media_type == "Episode":
                    event_message["title"] = f"删除剧集 {item.get('SeriesName', '')} S{item.get('ParentIndexNumber', '')}E{item.get('IndexNumber', '')} {item.get('Name', '')}"
                elif media_type == "Series":
                    event_message["title"] = f"删除剧集 {item.get('Name', '')}{year}"
                elif media_type == "Season":
                    event_message["title"] = f"删除剧集 {item.get('SeriesName', '')} S{item.get('IndexNumber', '')} {item.get('Name', '')}"
            
            return event_message
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"解析 Webhook 消息失败: {e}")
            return None
# 全局单例
_emby_service: Optional['EmbyService'] = None

def get_emby_service(store: DataStore = None) -> 'EmbyService':
    """获取 Emby 服务单例"""
    global _emby_service
    if _emby_service is None and store is not None:
        _emby_service = EmbyService(store)
    return _emby_service
