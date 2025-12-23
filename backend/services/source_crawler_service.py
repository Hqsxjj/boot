"""
来源爬虫服务 - 爬取用户添加的 TG 频道和网站中的云盘资源链接
使用数据库存储替代 JSON 文件
"""
import re
import logging
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 云盘链接正则表达式
CLOUD_LINK_PATTERNS = {
    '115': [
        r'https?://(?:115|115cdn)\.com/s/([a-z0-9]+)',
        r'115\.com/s/([a-z0-9]+)',
    ],
    '123': [
        r'https?://(?:123pan\.(?:com|cn)|123684\.com)/s/([a-zA-Z0-9-]+)',
        r'(?:123pan\.(?:com|cn)|123684\.com)/s/([a-zA-Z0-9-]+)',
    ]
}

# 提取码正则表达式
PASSWORD_PATTERNS = [
    r'提取码[：:]\s*([a-zA-Z0-9]+)',
    r'密码[：:]\s*([a-zA-Z0-9]+)',
    r'码[：:]\s*([a-zA-Z0-9]+)',
    r'pwd[=:]\s*([a-zA-Z0-9]+)',
    r'password[=:]\s*([a-zA-Z0-9]+)',
]


class SourceCrawlerService:
    """爬取用户添加的来源中的云盘资源链接"""
    
    def __init__(self, session_factory=None):
        """
        初始化爬虫服务
        
        Args:
            session_factory: SQLAlchemy session factory for appdata.db
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.session_factory = session_factory
        self._db_source_store = None
        
        if session_factory:
            from persistence.db_source_store import DbSourceStore
            self._db_source_store = DbSourceStore(session_factory)
        
        logger.info('SourceCrawlerService initialized')
    
    def _get_sources(self) -> List[Dict]:
        """获取来源列表"""
        if self._db_source_store:
            return self._db_source_store.get_sources()
        return []
    
    def extract_cloud_links(self, text: str, source_name: str = '') -> List[Dict]:
        """从文本中提取云盘链接和提取码"""
        results = []
        
        for cloud_type, patterns in CLOUD_LINK_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    full_url = match.group(0)
                    share_code = match.group(1)
                    
                    # 补全 URL
                    if not full_url.startswith('http'):
                        full_url = f'https://{full_url}'
                    
                    # 查找提取码
                    password = ''
                    link_pos = text.find(match.group(0))
                    context = text[max(0, link_pos - 100):min(len(text), link_pos + 200)]
                    
                    for pwd_pattern in PASSWORD_PATTERNS:
                        pwd_match = re.search(pwd_pattern, context, re.IGNORECASE)
                        if pwd_match:
                            password = pwd_match.group(1)
                            break
                    
                    # 提取标题
                    title = self._extract_title_near_link(text, link_pos)
                    
                    # 检查是否已存在
                    exists = any(r.get('url') == full_url for r in results)
                    if not exists:
                        results.append({
                            'cloud_type': cloud_type,
                            'url': full_url,
                            'share_code': share_code,
                            'access_code': password,
                            'title': title or f'{source_name} 资源',
                            'source_name': source_name
                        })
        
        return results
    
    def _extract_title_near_link(self, text: str, link_pos: int) -> str:
        """尝试从链接附近提取标题"""
        before_text = text[:link_pos]
        lines = before_text.split('\n')
        
        for i in range(len(lines) - 1, max(-1, len(lines) - 5), -1):
            line = lines[i].strip()
            if len(line) > 3 and not any(p in line for p in ['http', '://', '密码', '提取码']):
                title = re.sub(r'[【】\[\]《》<>]', '', line)[:50]
                if title:
                    return title
        
        return ''
    
    def crawl_telegram_channel(self, url: str, name: str = '') -> Dict[str, Any]:
        """爬取 Telegram 公开频道"""
        try:
            if url.startswith('@'):
                channel_name = url[1:]
            elif 't.me/' in url:
                channel_name = url.split('t.me/')[-1].split('/')[0].split('?')[0]
                if channel_name.startswith('s/'):
                    channel_name = channel_name[2:]
            else:
                return {'success': False, 'error': '无效的 TG 链接格式'}
            
            web_url = f'https://t.me/s/{channel_name}'
            logger.info(f"爬取 TG 频道: {web_url}")
            
            response = self.session.get(web_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            messages = soup.find_all('div', class_='tgme_widget_message_text')
            all_text = '\n'.join([msg.get_text() for msg in messages])
            
            resources = self.extract_cloud_links(all_text, name or f'@{channel_name}')
            
            logger.info(f"从 @{channel_name} 提取到 {len(resources)} 个资源链接")
            
            return {
                'success': True,
                'channel': channel_name,
                'resources': resources,
                'message_count': len(messages)
            }
            
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'TG 频道访问超时'}
        except Exception as e:
            logger.error(f"爬取 TG 频道失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def crawl_website(self, url: str, name: str = '') -> Dict[str, Any]:
        """爬取网站中的云盘链接"""
        try:
            logger.info(f"爬取网站: {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()
            
            text = soup.get_text(separator='\n')
            
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                text += f'\n{href}'
            
            resources = self.extract_cloud_links(text, name or url)
            
            logger.info(f"从 {url} 提取到 {len(resources)} 个资源链接")
            
            return {
                'success': True,
                'url': url,
                'resources': resources
            }
            
        except requests.exceptions.Timeout:
            return {'success': False, 'error': '网站访问超时'}
        except Exception as e:
            logger.error(f"爬取网站失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def crawl_source(self, source: Dict) -> Dict[str, Any]:
        """爬取单个来源"""
        if source.get('type') == 'telegram':
            result = self.crawl_telegram_channel(source['url'], source.get('name', ''))
        else:
            result = self.crawl_website(source['url'], source.get('name', ''))
        
        # 保存到数据库
        if result.get('success') and self._db_source_store:
            source_id = source.get('id')
            resources = result.get('resources', [])
            
            # 批量保存
            for r in resources:
                r['source_id'] = source_id
            
            self._db_source_store.add_crawled_resources_batch(source_id, resources)
            self._db_source_store.update_last_crawl(source_id)
        
        return result
    
    def crawl_all_enabled_sources(self) -> Dict[str, Any]:
        """爬取所有启用的来源"""
        sources = self._get_sources()
        enabled_sources = [s for s in sources if s.get('enabled', True)]
        
        if not enabled_sources:
            return {
                'success': True,
                'message': '没有启用的来源',
                'total_resources': 0
            }
        
        total_resources = 0
        results = []
        
        for source in enabled_sources:
            result = self.crawl_source(source)
            count = len(result.get('resources', []))
            total_resources += count
            
            results.append({
                'source_id': source.get('id'),
                'source_name': source.get('name'),
                'success': result.get('success'),
                'count': count,
                'error': result.get('error')
            })
        
        logger.info(f"爬取完成: {total_resources} 个资源")
        
        return {
            'success': True,
            'total_resources': total_resources,
            'source_results': results,
            'last_crawl': datetime.now().isoformat()
        }
    
    def get_crawled_resources(self, keyword: str = None) -> Dict[str, Any]:
        """获取爬取的资源"""
        if self._db_source_store:
            if keyword:
                resources = self._db_source_store.search_crawled(keyword)
            else:
                resources = self._db_source_store.get_crawled_resources()
            
            return {
                'success': True,
                'data': resources,
                'total': len(resources)
            }
        
        return {'success': True, 'data': [], 'total': 0}
    
    def search_in_crawled(self, keyword: str) -> List[Dict]:
        """在爬取的资源中搜索"""
        if self._db_source_store:
            resources = self._db_source_store.search_crawled(keyword)
        else:
            resources = []
        
        # 转换为前端期望的格式
        formatted = []
        for r in resources:
            formatted.append({
                'cloud_type': r.get('cloud_type', 'unknown'),
                'title': r.get('title', '未知资源'),
                'share_link': r.get('url', ''),
                'share_code': r.get('access_code', ''),
                'source': r.get('source_name', '用户来源'),
                'poster_url': 'https://via.placeholder.com/300x450?text=' + r.get('cloud_type', '?'),
                'id': str(r.get('id', ''))[-8:],
                'year': 2024,
                'type': 'movie',
                'quality': '未知',
                'from_user_source': True
            })
        
        return formatted


# 全局单例
_crawler_service = None
_session_factory = None


def init_crawler_service(session_factory) -> SourceCrawlerService:
    """初始化爬虫服务"""
    global _crawler_service, _session_factory
    _session_factory = session_factory
    _crawler_service = SourceCrawlerService(session_factory)
    return _crawler_service


def get_crawler_service() -> SourceCrawlerService:
    """获取或创建爬虫服务单例"""
    global _crawler_service, _session_factory
    if _crawler_service is None:
        _crawler_service = SourceCrawlerService(_session_factory)
    return _crawler_service
