"""
网盘搜索服务 - 调用 pan.jivon.de API 搜索多平台网盘资源
"""
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 网盘搜索 API 配置
DEFAULT_PANSOU_API_BASE = "https://pan.jivon.de"
PANSOU_API_KEY = "pansou_api_url"  # SecretStore 中存储的 key

# 支持的网盘类型
SUPPORTED_CLOUD_TYPES = ['115', '123', 'aliyun', 'baidu', 'quark', 'magnet', 'ed2k']


def get_pansou_api_url(secret_store=None) -> str:
    """从配置中获取 Pansou API URL，如果未配置则返回默认值。"""
    try:
        if secret_store:
            url = secret_store.get_secret(PANSOU_API_KEY)
            if url and url.strip():
                return url.strip().rstrip('/')
    except Exception as e:
        logger.warning(f"读取 Pansou API URL 配置失败: {e}")
    return DEFAULT_PANSOU_API_BASE


class PanSearchService:
    """Service for searching cloud drive resources via pan.jivon.de API."""
    
    def __init__(self, secret_store=None, api_base: str = None, timeout: int = 30):
        """
        Initialize PanSearchService.
        
        Args:
            secret_store: Optional SecretStore instance to read config
            api_base: Optional custom API base URL (if not provided, reads from config)
            timeout: Request timeout in seconds
        """
        if api_base:
            self.api_base = api_base.rstrip('/')
        else:
            self.api_base = get_pansou_api_url(secret_store)
        self.timeout = timeout
    
    def search(self, keyword: str, cloud_types: List[str] = None, 
               result_format: str = 'merge') -> Dict[str, Any]:
        """
        Search for cloud drive resources.
        
        Args:
            keyword: Search keyword
            cloud_types: Optional list of cloud types to filter (e.g., ['115', '123'])
            result_format: 'merge' for grouped results, 'all' for flat list
        
        Returns:
            Dict with success flag and search results
        """
        if not keyword or not keyword.strip():
            return {
                'success': False,
                'error': '请输入搜索关键词'
            }
        
        try:
            # 构建请求参数
            params = {
                'kw': keyword.strip(),
                'res': result_format
            }
            
            # 添加网盘类型筛选
            if cloud_types:
                valid_types = [t for t in cloud_types if t in SUPPORTED_CLOUD_TYPES]
                if valid_types:
                    params['cloud_types'] = ','.join(valid_types)
            
            # 发送请求
            url = f"{self.api_base}/api/search"
            logger.info(f"网盘搜索请求: {url}, 关键词: {keyword}")
            
            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('code') == 0:
                raw_data = data.get('data', {})
                
                # 处理 merge 格式的响应
                if result_format == 'merge':
                    merged = raw_data.get('merged_by_type', {})
                    results = self._transform_merged_results(merged)
                else:
                    results = raw_data.get('results', [])
                
                # 整合用户来源爬取的资源
                try:
                    from services.source_crawler_service import get_crawler_service
                    crawler = get_crawler_service()
                    crawled = crawler.search_in_crawled(keyword)
                    if crawled:
                        logger.info(f"从用户来源中找到 {len(crawled)} 个匹配资源")
                        # 将爬取的资源添加到结果开头（优先显示）
                        results = crawled + results
                except Exception as e:
                    logger.warning(f"整合爬取资源失败: {e}")
                
                total = len(results)
                
                logger.info(f"网盘搜索成功: 共 {total} 个结果")
                return {
                    'success': True,
                    'data': results,
                    'total': total,
                    'source': 'pansou'
                }
            else:
                error_msg = data.get('message', '搜索失败')
                logger.warning(f"网盘搜索 API 返回错误: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except requests.exceptions.Timeout:
            logger.error("网盘搜索请求超时")
            return {
                'success': False,
                'error': '搜索请求超时，请稍后重试'
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"网盘搜索连接失败: {e}")
            return {
                'success': False,
                'error': '无法连接到搜索服务'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"网盘搜索请求失败: {e}")
            return {
                'success': False,
                'error': f'请求失败: {str(e)}'
            }
        except Exception as e:
            logger.error(f"网盘搜索发生异常: {e}")
            return {
                'success': False,
                'error': f'搜索异常: {str(e)}'
            }
    
    def _transform_merged_results(self, merged: Dict[str, List]) -> List[Dict[str, Any]]:
        """
        Transform merged_by_type response to unified result list.
        
        Args:
            merged: Dict with cloud type as key and results list as value
        
        Returns:
            Unified list of results with cloud_type field added
        """
        results = []
        
        for cloud_type, items in merged.items():
            if not isinstance(items, list):
                continue
                
            for item in items:
                images = item.get('images', [])
                # 使用第一张图片作为海报，如果没有则使用默认占位图
                poster_url = images[0] if images else 'https://via.placeholder.com/300x450?text=No+Poster'
                
                result = {
                    'cloud_type': cloud_type,
                    'title': item.get('note', ''),
                    'url': item.get('url', ''),
                    'password': item.get('password', ''),
                    'datetime': item.get('datetime', ''),
                    'source': item.get('source', ''),
                    'images': images,
                    'poster_url': poster_url,
                    # 添加前端期望的其他字段
                    'id': str(hash(item.get('url', '') + item.get('note', '')))[-8:],
                    'year': 2024,  # 默认年份
                    'type': 'movie',  # 默认类型
                    'quality': '未知',
                    'share_link': item.get('url', ''),
                    'share_code': item.get('password', '')
                }
                results.append(result)
        
        return results
    
    def search_115(self, keyword: str) -> Dict[str, Any]:
        """Search only 115 cloud resources."""
        return self.search(keyword, cloud_types=['115'])
    
    def search_123(self, keyword: str) -> Dict[str, Any]:
        """Search only 123 cloud resources."""
        return self.search(keyword, cloud_types=['123'])
    
    def search_all_clouds(self, keyword: str) -> Dict[str, Any]:
        """Search all supported cloud types."""
        return self.search(keyword, cloud_types=SUPPORTED_CLOUD_TYPES)


# 全局单例
_pan_search_service = None


def get_pan_search_service(secret_store=None) -> PanSearchService:
    """Get or create PanSearchService singleton."""
    global _pan_search_service
    if _pan_search_service is None:
        _pan_search_service = PanSearchService(secret_store=secret_store)
    return _pan_search_service
