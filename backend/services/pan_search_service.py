"""
网盘搜索服务 - 调用 pan.jivon.de API 搜索多平台网盘资源
"""
import logging
import requests
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 网盘搜索 API 配置
PANSOU_API_BASE = "https://pan.jivon.de"

# 支持的网盘类型
SUPPORTED_CLOUD_TYPES = ['115', '123', 'aliyun', 'baidu', 'quark', 'magnet', 'ed2k']


class PanSearchService:
    """Service for searching cloud drive resources via pan.jivon.de API."""
    
    def __init__(self, api_base: str = None, timeout: int = 30):
        """
        Initialize PanSearchService.
        
        Args:
            api_base: Optional custom API base URL
            timeout: Request timeout in seconds
        """
        self.api_base = (api_base or PANSOU_API_BASE).rstrip('/')
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
                
                total = raw_data.get('total', len(results))
                
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
                result = {
                    'cloud_type': cloud_type,
                    'title': item.get('note', ''),
                    'url': item.get('url', ''),
                    'password': item.get('password', ''),
                    'datetime': item.get('datetime', ''),
                    'source': item.get('source', ''),
                    'images': item.get('images', [])
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


def get_pan_search_service() -> PanSearchService:
    """Get or create PanSearchService singleton."""
    global _pan_search_service
    if _pan_search_service is None:
        _pan_search_service = PanSearchService()
    return _pan_search_service
