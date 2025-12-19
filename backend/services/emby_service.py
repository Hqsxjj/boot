import requests
import time
import urllib3
from persistence.store import DataStore
from typing import Dict, Any, List
from utils.logger import TaskLogger

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
    
    def scan_missing_episodes(self) -> Dict[str, Any]:
        """
        扫描 Emby 中的电视剧缺集情况，与 TMDB 数据比对。
        
        返回格式:
        [
            {
                'id': series_id,
                'name': 剧名,
                'season': 季号,
                'totalEp': TMDB总集数,
                'localEp': Emby已有集数,
                'missing': 缺失集号字符串,
                'poster': 海报URL
            }
        ]
        """
        task_log = TaskLogger('Emby')
        task_log.start('扫描缺集')

        config = self._get_config()
        server_url = config.get('serverUrl', '').rstrip('/')
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            task_log.failure('Emby未配置')
            return {'success': False, 'data': [], 'error': 'Emby未配置'}
        
        # 获取 TMDB 配置
        full_config = self.store.get_config()
        tmdb_api_key = full_config.get('tmdb', {}).get('apiKey', '').strip()
        tmdb_lang = full_config.get('tmdb', {}).get('language', 'zh-CN')
        tmdb_domain = full_config.get('tmdb', {}).get('domain', 'api.themoviedb.org').rstrip('/')
        
        missing_data = []
        
        # 定义内部重试函数
        def _fetch_tmdb_season(series_tmdb_id, season_num):
            url = f'https://{tmdb_domain}/3/tv/{series_tmdb_id}/season/{season_num}'
            params = {'api_key': tmdb_api_key, 'language': tmdb_lang}
            
            # 1. 尝试使用代理 (如果配置了)
            proxies = self._get_proxy_config()
            if proxies:
                try:
                    # task_log.info(f"正在通过代理连接 TMDB...")
                    resp = requests.get(url, params=params, proxies=proxies, timeout=15)
                    if resp.status_code == 200:
                        return resp.json()
                except Exception as e:
                    # task_log.warning(f"代理连接失败: {e}，尝试直连...")
                    pass
            
            # 2. 尝试直连 (如果代理失败或未配置)
            try:
                # task_log.info(f"正在直连 TMDB...")
                resp = requests.get(url, params=params, timeout=10) # 直连超时短一点
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                pass
                
            return None
        
        try:
            # 1. 获取 Emby 中所有电视剧
            series_response = self._make_request(
                'GET',
                f'{server_url}/emby/Items',
                params={
                    'api_key': api_key,
                    'IncludeItemTypes': 'Series',
                    'Recursive': 'true',
                    'Fields': 'ProviderIds,Overview',
                    'SortBy': 'SortName',
                    'SortOrder': 'Ascending'
                },
                timeout=30
            )
            
            if series_response.status_code != 200:
                return {'success': False, 'data': [], 'error': f'Emby请求失败: {series_response.status_code}'}
            
            series_list = series_response.json().get('Items', [])
            
            for series in series_list:
                series_id = series.get('Id')
                series_name = series.get('Name', '未知')
                tmdb_id = series.get('ProviderIds', {}).get('Tmdb')
                poster_path = None
                
                # 获取 Emby 海报
                if series.get('ImageTags', {}).get('Primary'):
                    poster_path = f"{server_url}/emby/Items/{series_id}/Images/Primary?api_key={api_key}&maxWidth=200"
                
                # 2. 获取该剧的所有季
                seasons_response = self._make_request(
                    'GET',
                    f'{server_url}/emby/Shows/{series_id}/Seasons',
                    params={'api_key': api_key, 'Fields': 'ProviderIds'},
                    timeout=15
                )
                
                if seasons_response.status_code != 200:
                    continue
                    
                seasons = seasons_response.json().get('Items', [])
                
                for season in seasons:
                    season_id = season.get('Id')
                    season_number = season.get('IndexNumber', 0)
                    
                    # 跳过特辑季 (Season 0)
                    if season_number == 0:
                        continue
                    
                    # 3. 获取该季的所有集
                    episodes_response = self._make_request(
                        'GET',
                        f'{server_url}/emby/Shows/{series_id}/Episodes',
                        params={
                            'api_key': api_key,
                            'SeasonId': season_id,
                            'Fields': 'ProviderIds'
                        },
                        timeout=15
                    )
                    
                    if episodes_response.status_code != 200:
                        continue
                    
                    emby_episodes = episodes_response.json().get('Items', [])
                    local_episode_numbers = set()
                    for ep in emby_episodes:
                        ep_num = ep.get('IndexNumber')
                        if ep_num:
                            local_episode_numbers.add(ep_num)
                    
                    local_ep_count = len(local_episode_numbers)
                    
                    # 4. 查询 TMDB 获取该季总集数
                    total_ep_count = local_ep_count  # 默认值
                    missing_episodes = []
                    
                    if tmdb_api_key and tmdb_id:
                        tmdb_data = _fetch_tmdb_season(tmdb_id, season_number)
                        
                        if tmdb_data:
                            tmdb_episodes = tmdb_data.get('episodes', [])
                            total_ep_count = len(tmdb_episodes)
                            
                            # 计算缺失集数
                            all_ep_numbers = set(ep.get('episode_number') for ep in tmdb_episodes if ep.get('episode_number'))
                            missing_episodes = sorted(all_ep_numbers - local_episode_numbers)
                            
                            # 使用 TMDB 海报 (如果 Emby 没有)
                            if not poster_path and tmdb_data.get('poster_path'):
                                poster_path = f"https://image.tmdb.org/t/p/w200{tmdb_data['poster_path']}"
                        else:
                            # 失败，记录日志但不中断（静默失败）
                            # task_log.warning(f"无法获取 {series_name} S{season_number} 的 TMDB 数据")
                            pass
                    
                    # 只添加有缺集的记录
                    if missing_episodes:
                        missing_data.append({
                            'id': f"{series_id}_{season_number}",
                            'name': series_name,
                            'season': season_number,
                            'totalEp': total_ep_count,
                            'localEp': local_ep_count,
                            'missing': ', '.join(f'E{ep:02d}' for ep in missing_episodes),
                            'poster': poster_path
                        })
            
            
            task_log.success(f'发现 {len(missing_data)} 个缺集系列')
            return {
                'success': True,
                'data': missing_data
            }
        except requests.Timeout:
            task_log.failure('Emby连接超时')
            return {'success': False, 'data': [], 'error': 'Emby连接超时'}
        except requests.ConnectionError:
            task_log.failure('Emby连接失败')
            return {'success': False, 'data': [], 'error': 'Emby连接失败'}
        except Exception as e:
            task_log.failure(str(e))
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

