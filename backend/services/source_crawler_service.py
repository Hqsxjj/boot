"""
来源爬虫服务 - 爬取用户添加的 TG 频道和网站中的云盘资源链接
"""
import os
import re
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 爬取结果存储文件
CRAWLED_DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'crawled_resources.json')

# 来源配置文件
SOURCES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'sources.json')

# 云盘链接正则表达式
CLOUD_LINK_PATTERNS = {
    '115': [
        r'https?://(?:115|115cdn)\.com/s/([a-z0-9]+)',  # 115.com/s/xxx
        r'115\.com/s/([a-z0-9]+)',  # 不带 https
    ],
    '123': [
        r'https?://(?:123pan\.(?:com|cn)|123684\.com)/s/([a-zA-Z0-9-]+)',  # 123pan.com/s/xxx
        r'(?:123pan\.(?:com|cn)|123684\.com)/s/([a-zA-Z0-9-]+)',  # 不带 https
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
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        """确保数据目录存在"""
        data_dir = os.path.dirname(CRAWLED_DATA_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
    
    def _load_sources(self) -> List[Dict]:
        """加载来源配置"""
        if os.path.exists(SOURCES_FILE):
            try:
                with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载来源文件失败: {e}")
        return []
    
    def _load_crawled_data(self) -> Dict:
        """加载已爬取的数据"""
        if os.path.exists(CRAWLED_DATA_FILE):
            try:
                with open(CRAWLED_DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载爬取数据失败: {e}")
        return {'resources': [], 'last_crawl': None}
    
    def _save_crawled_data(self, data: Dict):
        """保存爬取的数据"""
        try:
            with open(CRAWLED_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存爬取数据失败: {e}")
    
    def extract_cloud_links(self, text: str, source_name: str = '') -> List[Dict]:
        """从文本中提取云盘链接和提取码"""
        results = []
        
        # 按段落分割，便于匹配提取码
        paragraphs = text.split('\n')
        
        for cloud_type, patterns in CLOUD_LINK_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    full_url = match.group(0)
                    share_code = match.group(1)
                    
                    # 补全 URL
                    if not full_url.startswith('http'):
                        if cloud_type == '115':
                            full_url = f'https://{full_url}'
                        else:
                            full_url = f'https://{full_url}'
                    
                    # 查找提取码（在链接附近的文本中）
                    password = ''
                    # 查找链接所在位置前后的文本
                    link_pos = text.find(match.group(0))
                    context = text[max(0, link_pos - 100):min(len(text), link_pos + 200)]
                    
                    for pwd_pattern in PASSWORD_PATTERNS:
                        pwd_match = re.search(pwd_pattern, context, re.IGNORECASE)
                        if pwd_match:
                            password = pwd_match.group(1)
                            break
                    
                    # 尝试从链接标题中提取名称
                    title = self._extract_title_near_link(text, link_pos)
                    
                    # 检查是否已存在
                    exists = any(r['share_link'] == full_url for r in results)
                    if not exists:
                        results.append({
                            'cloud_type': cloud_type,
                            'share_link': full_url,
                            'share_code': share_code,
                            'password': password,
                            'title': title or f'{source_name} 资源',
                            'source': source_name
                        })
        
        return results
    
    def _extract_title_near_link(self, text: str, link_pos: int) -> str:
        """尝试从链接附近提取标题"""
        # 向前查找可能的标题（通常在链接前一行）
        before_text = text[:link_pos]
        lines = before_text.split('\n')
        
        for i in range(len(lines) - 1, max(-1, len(lines) - 5), -1):
            line = lines[i].strip()
            # 跳过空行和太短的行
            if len(line) > 3 and not any(p in line for p in ['http', '://', '密码', '提取码']):
                # 清理标题
                title = re.sub(r'[【】\[\]《》<>]', '', line)[:50]
                if title:
                    return title
        
        return ''
    
    def crawl_telegram_channel(self, url: str, name: str = '') -> Dict[str, Any]:
        """爬取 Telegram 公开频道（通过 t.me/s/ 网页端）"""
        try:
            # 转换链接格式
            if url.startswith('@'):
                channel_name = url[1:]
            elif 't.me/' in url:
                channel_name = url.split('t.me/')[-1].split('/')[0].split('?')[0]
                # 移除 s/ 前缀如果有
                if channel_name.startswith('s/'):
                    channel_name = channel_name[2:]
            else:
                return {'success': False, 'error': '无效的 TG 链接格式'}
            
            # 使用 t.me/s/xxx 网页端访问公开频道
            web_url = f'https://t.me/s/{channel_name}'
            logger.info(f"爬取 TG 频道: {web_url}")
            
            response = self.session.get(web_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 提取消息内容
            messages = soup.find_all('div', class_='tgme_widget_message_text')
            all_text = '\n'.join([msg.get_text() for msg in messages])
            
            # 提取链接
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
            
            # 移除脚本和样式
            for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()
            
            # 提取所有文本
            text = soup.get_text(separator='\n')
            
            # 同时检查所有链接的 href
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href', '')
                text += f'\n{href}'
            
            # 提取云盘链接
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
            return self.crawl_telegram_channel(source['url'], source.get('name', ''))
        else:
            return self.crawl_website(source['url'], source.get('name', ''))
    
    def crawl_all_enabled_sources(self) -> Dict[str, Any]:
        """爬取所有启用的来源"""
        sources = self._load_sources()
        enabled_sources = [s for s in sources if s.get('enabled', True)]
        
        if not enabled_sources:
            return {
                'success': True,
                'message': '没有启用的来源',
                'total_resources': 0
            }
        
        all_resources = []
        results = []
        
        for source in enabled_sources:
            result = self.crawl_source(source)
            results.append({
                'source_id': source.get('id'),
                'source_name': source.get('name'),
                'success': result.get('success'),
                'count': len(result.get('resources', [])),
                'error': result.get('error')
            })
            
            if result.get('success'):
                for resource in result.get('resources', []):
                    resource['source_id'] = source.get('id')
                    resource['crawled_at'] = datetime.now().isoformat()
                    all_resources.append(resource)
        
        # 去重
        unique_resources = []
        seen_links = set()
        for r in all_resources:
            if r['share_link'] not in seen_links:
                seen_links.add(r['share_link'])
                unique_resources.append(r)
        
        # 保存结果
        crawled_data = {
            'resources': unique_resources,
            'last_crawl': datetime.now().isoformat(),
            'source_results': results
        }
        self._save_crawled_data(crawled_data)
        
        logger.info(f"爬取完成: {len(unique_resources)} 个唯一资源")
        
        return {
            'success': True,
            'total_resources': len(unique_resources),
            'source_results': results,
            'last_crawl': crawled_data['last_crawl']
        }
    
    def get_crawled_resources(self, keyword: str = None) -> Dict[str, Any]:
        """获取爬取的资源（可按关键词过滤）"""
        data = self._load_crawled_data()
        resources = data.get('resources', [])
        
        if keyword:
            keyword_lower = keyword.lower()
            resources = [
                r for r in resources 
                if keyword_lower in r.get('title', '').lower() 
                or keyword_lower in r.get('source', '').lower()
            ]
        
        return {
            'success': True,
            'data': resources,
            'total': len(resources),
            'last_crawl': data.get('last_crawl')
        }
    
    def search_in_crawled(self, keyword: str) -> List[Dict]:
        """在爬取的资源中搜索"""
        result = self.get_crawled_resources(keyword)
        resources = result.get('data', [])
        
        # 转换为前端期望的格式
        formatted = []
        for r in resources:
            formatted.append({
                'cloud_type': r.get('cloud_type', 'unknown'),
                'title': r.get('title', '未知资源'),
                'share_link': r.get('share_link', ''),
                'share_code': r.get('password', ''),
                'source': r.get('source', '用户来源'),
                'poster_url': 'https://via.placeholder.com/300x450?text=' + r.get('cloud_type', '?'),
                'id': str(hash(r.get('share_link', '')))[-8:],
                'year': 2024,
                'type': 'movie',
                'quality': '未知',
                'from_user_source': True
            })
        
        return formatted


# 全局单例
_crawler_service = None


def get_crawler_service() -> SourceCrawlerService:
    """获取或创建爬虫服务单例"""
    global _crawler_service
    if _crawler_service is None:
        _crawler_service = SourceCrawlerService()
    return _crawler_service
