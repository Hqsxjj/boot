"""
资源搜索 API - 利用 AI 搜索 TG 和全网 115 网盘分享链接
"""
import logging
import requests
import json
import re
from flask import Blueprint, request, jsonify
from middleware.auth import require_auth
from persistence.store import DataStore

logger = logging.getLogger(__name__)

resource_search_bp = Blueprint('resource_search', __name__, url_prefix='/api/resource-search')

# Global instances
_store = None
_tmdb_service = None

# 热门资源缓存
_trending_cache = None
_trending_cache_time = None


def init_resource_search_blueprint(store: DataStore, tmdb_service=None):
    """Initialize resource search blueprint with required services."""
    global _store, _tmdb_service
    _store = store
    _tmdb_service = tmdb_service
    return resource_search_bp


def _get_tmdb_service():
    """Lazy load TMDB service if not passed during init."""
    global _tmdb_service
    if _tmdb_service:
        return _tmdb_service
    
    # Try to create TmdbService
    try:
        from services.tmdb_service import TmdbService
        _tmdb_service = TmdbService(config_store=_store)
        return _tmdb_service
    except Exception as e:
        logger.warning(f"Failed to create TmdbService: {e}")
        return None


def _get_ai_config():
    """Get AI configuration from store."""
    if not _store:
        return None
    config = _store.get_config()
    ai_config = config.get('organize', {}).get('ai', {})
    return ai_config if ai_config.get('enabled') and ai_config.get('apiKey') else None


def _call_ai_search(query: str, ai_config: dict) -> list:
    """
    Call AI API to search for 115 share links.
    Returns list of resource objects.
    """
    if not ai_config:
        return []
    
    provider = ai_config.get('provider', 'openai')
    base_url = ai_config.get('baseUrl', 'https://api.openai.com/v1')
    api_key = ai_config.get('apiKey', '')
    model = ai_config.get('model', 'gpt-4')
    
    if not api_key:
        logger.warning("AI API key not configured")
        return []
    
    # Construct the search prompt
    system_prompt = """你是一个专业的影视资源搜索助手。用户会给你一个电影或电视剧的名称，你需要：
1. 搜索并返回可能存在的 115 网盘分享链接
2. 返回资源的详细信息，包括标题、年份、类型、清晰度等

请以 JSON 数组格式返回结果，每个结果包含：
- title: 资源标题
- year: 年份
- type: "movie" 或 "tv"
- quality: 清晰度 (如 "4K", "1080P", "720P")
- size: 文件大小估计
- source: 来源 (如 "Telegram", "网络论坛")
- share_link: 115 分享链接 (如果没有真实链接，返回 null)
- share_code: 提取码 (如果有)
- poster_url: TMDB 海报链接 (如果能找到)
- description: 简短描述

注意：如果找不到资源，返回空数组 []。只返回 JSON，不要有其他文字。"""

    user_prompt = f"请搜索以下影视资源的 115 网盘分享链接：{query}"
    
    try:
        # Build request based on provider
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        # Normalize base URL and construct endpoint
        base_url = base_url.rstrip('/')
        endpoint = f"{base_url}/chat/completions"
        
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 2000
        }
        
        response = requests.post(endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '[]')
        
        # Parse JSON from response
        # Try to extract JSON array from the response
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            resources = json.loads(json_match.group())
            return resources
        else:
            return []
            
    except requests.exceptions.RequestException as e:
        logger.error(f"AI API request failed: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in AI search: {e}")
        return []


def _get_trending_from_tmdb() -> list:
    """
    从 TMDB 获取近一周热门资源。
    """
    global _trending_cache, _trending_cache_time
    from datetime import datetime, timedelta
    
    # 检查缓存 (30分钟有效)
    if _trending_cache and _trending_cache_time:
        if datetime.now() - _trending_cache_time < timedelta(minutes=30):
            logger.info("Returning cached trending resources")
            return _trending_cache
    
    tmdb = _get_tmdb_service()
    if not tmdb:
        logger.warning("TMDB service not available")
        return _get_fallback_trending()
    
    # 获取配置
    config = _store.get_config() if _store else {}
    
    # 调用 TMDB API
    result = tmdb.get_trending_week(config=config, limit=12)
    
    if result.get('success') and result.get('data'):
        _trending_cache = result['data']
        _trending_cache_time = datetime.now()
        logger.info(f"Fetched {len(result['data'])} trending resources from TMDB")
        return result['data']
    else:
        error = result.get('error', 'Unknown error')
        logger.warning(f"TMDB trending failed: {error}, using fallback")
        return _get_fallback_trending()


def _get_fallback_trending() -> list:
    """
    备用热门资源列表（当 TMDB 不可用时）
    """
    return [
        {
            "id": "1",
            "title": "沙丘2",
            "original_title": "Dune: Part Two",
            "year": 2024,
            "type": "movie",
            "quality": "4K HDR",
            "poster_url": "https://image.tmdb.org/t/p/w500/8b8R8l88Qje9dn9OE8PY05Nxl1X.jpg",
            "backdrop_url": "https://image.tmdb.org/t/p/original/xOMo8BRK7PfcJv9JCnx7s5hj0PX.jpg",
            "rating": 8.5,
            "description": "保罗·厄崔迪与弗曼人联合对抗哈克南家族的史诗续集",
            "share_links": [
                {"source": "Telegram 资源群", "link": None, "code": None}
            ]
        },
        {
            "id": "2",
            "title": "奥本海默",
            "original_title": "Oppenheimer",
            "year": 2023,
            "type": "movie",
            "quality": "4K IMAX",
            "poster_url": "https://image.tmdb.org/t/p/w500/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg",
            "backdrop_url": "https://image.tmdb.org/t/p/original/fm6KqXpk3M2HVveHwCrBSSBaO0V.jpg",
            "rating": 8.4,
            "description": "诺兰执导的原子弹之父传记片",
            "share_links": [
                {"source": "Telegram", "link": None, "code": None}
            ]
        },
        {
            "id": "3",
            "title": "三体",
            "original_title": "3 Body Problem",
            "year": 2024,
            "type": "tv",
            "quality": "4K HDR",
            "poster_url": "https://image.tmdb.org/t/p/w500/tXFBQ0U5u8GpOwLbJjR5T7sVUqQ.jpg",
            "backdrop_url": "https://image.tmdb.org/t/p/original/bSHfBKSWHYDyTt7bR4nH0h2YnCH.jpg",
            "rating": 7.8,
            "description": "Netflix 版三体，刘慈欣科幻巨作改编",
            "share_links": [
                {"source": "科幻资源群", "link": None, "code": None}
            ]
        },
        {
            "id": "4",
            "title": "周处除三害",
            "original_title": "The Pig, the Snake and the Pigeon",
            "year": 2023,
            "type": "movie",
            "quality": "1080P",
            "poster_url": "https://image.tmdb.org/t/p/w500/qS1dGSHUkPJkZfxSJkHRfH5s1qe.jpg",
            "backdrop_url": "https://image.tmdb.org/t/p/original/2KGxQFV9Wp1MshPBf8BuqWVL7v.jpg",
            "rating": 7.4,
            "description": "阮经天主演的台湾犯罪动作片",
            "share_links": [
                {"source": "电影资源站", "link": None, "code": None}
            ]
        }
    ]


@resource_search_bp.route('/search', methods=['POST'])
@require_auth
def search_resources():
    """
    Search for 115 share links using AI.
    
    Request body:
    {
        "query": "电影/电视剧名称"
    }
    """
    try:
        data = request.get_json() or {}
        query = data.get('query', '').strip()
        
        if not query:
            return jsonify({
                'success': False,
                'error': '请输入搜索关键词'
            }), 400
        
        ai_config = _get_ai_config()
        
        if not ai_config:
            # Fall back to mock search results if AI not configured
            logger.info("AI not configured, using mock search results")
            mock_results = [
                {
                    "title": query,
                    "year": 2024,
                    "type": "movie",
                    "quality": "4K",
                    "source": "搜索结果",
                    "share_link": None,
                    "poster_url": "https://image.tmdb.org/t/p/w500/placeholder.jpg",
                    "description": f"正在搜索 '{query}' 的资源，请配置 AI 以获取真实搜索结果"
                }
            ]
            return jsonify({
                'success': True,
                'data': mock_results,
                'ai_enabled': False,
                'message': 'AI 未配置，显示示例结果。请在网盘整理页面配置 AI 设置。'
            })
        
        # Perform AI search
        results = _call_ai_search(query, ai_config)
        
        return jsonify({
            'success': True,
            'data': results,
            'ai_enabled': True
        })
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return jsonify({
            'success': False,
            'error': f'搜索失败: {str(e)}'
        }), 500


@resource_search_bp.route('/trending', methods=['GET'])
@require_auth
def get_trending():
    """Get trending/hot resources from TMDB (近一周热门)."""
    try:
        resources = _get_trending_from_tmdb()
        
        # 判断是否从 TMDB 获取
        is_from_tmdb = bool(_trending_cache)
        
        return jsonify({
            'success': True,
            'data': resources,
            'source': 'tmdb' if is_from_tmdb else 'fallback'
        })
    except Exception as e:
        logger.error(f"Failed to get trending: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'data': _get_fallback_trending()
        }), 500


@resource_search_bp.route('/resource/<resource_id>', methods=['GET'])
@require_auth
def get_resource_detail(resource_id: str):
    """Get detailed information and share links for a specific resource."""
    try:
        # Find the resource in trending
        resources = _get_trending_from_tmdb()
        resource = next((r for r in resources if r['id'] == resource_id), None)
        
        if not resource:
            return jsonify({
                'success': False,
                'error': '资源不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': resource
        })
    except Exception as e:
        logger.error(f"Failed to get resource detail: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

