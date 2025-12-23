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
from services.pan_search_service import get_pan_search_service

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
        logger.warning(f"创建 TmdbService 失败: {e}")
        return None


def _get_ai_config():
    """Get AI configuration from store."""
    if not _store:
        return None
    config = _store.get_config()
    ai_config = config.get('organize', {}).get('ai', {})
    return ai_config if ai_config.get('enabled') and ai_config.get('apiKey') else None


def _call_ai_search(query: str, ai_config: dict) -> dict:
    """
    Call AI API to search for 115 share links.
    Returns dict with success status and results or error.
    """
    if not ai_config:
        return {'success': False, 'error': 'AI 配置为空', 'data': []}
    
    provider = ai_config.get('provider', 'openai')
    base_url = ai_config.get('baseUrl', 'https://api.openai.com/v1')
    api_key = ai_config.get('apiKey', '')
    model = ai_config.get('model', 'gpt-4')
    
    if not api_key:
        logger.warning("未配置 AI API Key")
        return {'success': False, 'error': '未配置 AI API Key', 'data': []}
    
    if not base_url:
        logger.warning("未配置 AI Base URL")
        return {'success': False, 'error': '未配置 AI Base URL', 'data': []}
    
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
        
        logger.info(f"AI 搜索请求: provider={provider}, model={model}, endpoint={endpoint}")
        
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 2000
        }
        
        response = requests.post(endpoint, headers=headers, json=payload, timeout=60)
        
        # 检查响应状态
        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else '无响应内容'
            logger.error(f"AI API 返回错误: HTTP {response.status_code}, {error_detail}")
            return {
                'success': False, 
                'error': f'AI API 返回 HTTP {response.status_code}: {error_detail[:200]}',
                'data': []
            }
        
        result = response.json()
        
        # 检查是否有错误响应
        if 'error' in result:
            error_msg = result['error'].get('message', str(result['error']))
            logger.error(f"AI API 返回错误: {error_msg}")
            return {'success': False, 'error': f'AI API 错误: {error_msg}', 'data': []}
        
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '[]')
        
        # Parse JSON from response
        # Try to extract JSON array from the response
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            resources = json.loads(json_match.group())
            logger.info(f"AI 搜索成功，返回 {len(resources)} 个结果")
            return {'success': True, 'data': resources}
        else:
            logger.warning(f"AI 响应无法解析为 JSON: {content[:200]}")
            return {'success': True, 'data': [], 'message': '未找到匹配资源'}
            
    except requests.exceptions.Timeout:
        logger.error("AI API 请求超时")
        return {'success': False, 'error': 'AI API 请求超时 (60秒)，请检查网络或尝试其他服务商', 'data': []}
    except requests.exceptions.ConnectionError as e:
        error_str = str(e)
        logger.error(f"AI API 连接失败: {error_str}")
        if 'NameResolutionError' in error_str or 'getaddrinfo' in error_str:
            return {'success': False, 'error': f'无法解析域名，请检查 Base URL 是否正确: {base_url}', 'data': []}
        elif 'Connection refused' in error_str:
            return {'success': False, 'error': f'连接被拒绝，请检查 Base URL 是否正确: {base_url}', 'data': []}
        else:
            return {'success': False, 'error': f'网络连接错误: {error_str[:200]}', 'data': []}
    except requests.exceptions.RequestException as e:
        logger.error(f"AI API 请求失败: {e}")
        return {'success': False, 'error': f'请求失败: {str(e)[:200]}', 'data': []}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        return {'success': False, 'error': f'AI 响应解析失败: {str(e)}', 'data': []}
    except Exception as e:
        logger.error(f"Unexpected error in AI search: {e}")
        return {'success': False, 'error': f'未知错误: {str(e)[:200]}', 'data': []}


def _get_trending_from_tmdb() -> list:
    """
    从 TMDB 获取近一周热门资源。
    """
    global _trending_cache, _trending_cache_time
    from datetime import datetime, timedelta
    
    # 检查缓存 (30分钟有效)
    if _trending_cache and _trending_cache_time:
        if datetime.now() - _trending_cache_time < timedelta(minutes=30):
            logger.info("返回缓存的热门资源")
            return _trending_cache
    
    tmdb = _get_tmdb_service()
    if not tmdb:
        logger.warning("TMDB 服务不可用")
        return _get_fallback_trending()
    
    # 获取配置
    config = _store.get_config() if _store else {}
    
    # 调用 TMDB API
    result = tmdb.get_trending_week(config=config, limit=12)
    
    if result.get('success') and result.get('data'):
        _trending_cache = result['data']
        _trending_cache_time = datetime.now()
        logger.info(f"从 TMDB 获取了 {len(result['data'])} 个热门资源")
        return result['data']
    else:
        error = result.get('error', '未知错误')
        logger.warning(f"TMDB 热门资源获取失败: {error}，使用备用列表")
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
    Search for cloud drive share links.
    
    搜索策略：
    1. 如果用户配置了盘搜 API URL，则使用盘搜 API
    2. 如果配置了 AI，则使用 AI 搜索
    3. 如果添加了频道来源，则搜索来源中的资源
    4. 三者都有则全部搜索，分区返回结果
    
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
        
        # 分区结果
        pansou_results = []
        ai_results = []
        source_results = []
        
        # 记录错误信息
        errors = []
        
        # 1. 检查是否配置了盘搜 API URL
        pansou_enabled = False
        try:
            from app import get_db_session
            from services.secret_store import SecretStore
            from services.pan_search_service import PANSOU_API_KEY
            
            store = SecretStore(get_db_session)
            pansou_url = store.get_secret(PANSOU_API_KEY)
            
            if pansou_url and pansou_url.strip():
                pansou_enabled = True
                try:
                    pan_service = get_pan_search_service()
                    pan_result = pan_service.search(query, cloud_types=['115', '123'])
                    
                    if pan_result.get('success') and pan_result.get('data'):
                        pansou_results = pan_result.get('data', [])
                        # 标记来源
                        for r in pansou_results:
                            r['_source_type'] = 'pansou'
                        logger.info(f"盘搜 API 搜索成功，返回 {len(pansou_results)} 个结果")
                except Exception as e:
                    logger.warning(f"盘搜 API 搜索失败: {e}")
                    errors.append(f"盘搜服务: {str(e)}")
        except Exception as e:
            logger.warning(f"检查盘搜配置失败: {e}")
        
        # 2. 检查并使用 AI 搜索
        ai_enabled = False
        ai_config = _get_ai_config()
        if ai_config:
            ai_enabled = True
            try:
                ai_result = _call_ai_search(query, ai_config)
                if ai_result.get('success') and ai_result.get('data'):
                    ai_results = ai_result.get('data', [])
                    # 标记来源
                    for r in ai_results:
                        r['_source_type'] = 'ai'
                    logger.info(f"AI 搜索成功，返回 {len(ai_results)} 个结果")
                elif ai_result.get('error'):
                    errors.append(f"AI 搜索: {ai_result.get('error')}")
            except Exception as e:
                logger.warning(f"AI 搜索失败: {e}")
                errors.append(f"AI 搜索: {str(e)}")
        
        # 3. 搜索用户添加的频道/来源
        try:
            from services.source_crawler_service import get_crawler_service
            crawler = get_crawler_service()
            crawled = crawler.search_in_crawled(query)
            if crawled:
                source_results = crawled
                # 标记来源
                for r in source_results:
                    r['_source_type'] = 'user_source'
                logger.info(f"从用户来源中找到 {len(source_results)} 个匹配资源")
        except Exception as e:
            logger.warning(f"搜索用户来源失败: {e}")
        
        # 4. 构建分区响应
        has_any_source = pansou_enabled or ai_enabled or len(source_results) > 0
        
        # 合并所有结果用于兼容旧前端
        all_results = pansou_results + ai_results + source_results
        
        # 确定搜索来源描述
        sources_used = []
        if pansou_results:
            sources_used.append('pansou')
        if ai_results:
            sources_used.append('ai')
        if source_results:
            sources_used.append('user_source')
        
        search_source = '+'.join(sources_used) if sources_used else 'none'
        
        # 如果没有配置任何搜索源
        if not has_any_source:
            return jsonify({
                'success': True,
                'data': [],
                'sections': {},
                'message': '请先配置搜索接口或 AI，或添加频道来源',
                'source': 'none',
                'ai_enabled': False,
                'pansou_enabled': False
            })
        
        # 如果没有搜索到任何结果
        if not all_results:
            error_msg = '；'.join(errors) if errors else f"未找到 '{query}' 相关资源"
            return jsonify({
                'success': True,
                'data': [],
                'sections': {
                    'pansou': [],
                    'ai': [],
                    'user_source': []
                },
                'message': error_msg,
                'source': search_source,
                'ai_enabled': ai_enabled,
                'pansou_enabled': pansou_enabled
            })
        
        return jsonify({
            'success': True,
            'data': all_results,
            'sections': {
                'pansou': pansou_results,
                'ai': ai_results,
                'user_source': source_results
            },
            'source': search_source,
            'ai_enabled': ai_enabled,
            'pansou_enabled': pansou_enabled,
            'total': len(all_results)
        })
        
    except Exception as e:
        logger.error(f"资源搜索失败: {e}")
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


@resource_search_bp.route('/pan', methods=['GET', 'POST'])
@require_auth
def search_pan_resources():
    """
    Search for cloud drive resources via pan.jivon.de API.
    
    GET params or POST body:
    {
        "keyword": "搜索关键词",
        "cloud_types": ["115", "123", "aliyun"] // 可选，筛选网盘类型
    }
    """
    try:
        # 支持 GET 和 POST 请求
        if request.method == 'POST':
            data = request.get_json() or {}
            keyword = data.get('keyword', '').strip()
            cloud_types = data.get('cloud_types')
        else:
            keyword = request.args.get('kw', '').strip() or request.args.get('keyword', '').strip()
            cloud_types_str = request.args.get('cloud_types', '')
            cloud_types = cloud_types_str.split(',') if cloud_types_str else None
        
        if not keyword:
            return jsonify({
                'success': False,
                'error': '请输入搜索关键词'
            }), 400
        
        # 调用网盘搜索服务
        pan_service = get_pan_search_service()
        result = pan_service.search(keyword, cloud_types=cloud_types)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'data': result.get('data', []),
                'total': result.get('total', 0),
                'source': 'pansou',
                'keyword': keyword
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', '搜索失败')
            }), 400
            
    except Exception as e:
        logger.error(f"网盘搜索失败: {e}")
        return jsonify({
            'success': False,
            'error': f'搜索失败: {str(e)}'
        }), 500


@resource_search_bp.route('/pan/115', methods=['GET'])
@require_auth
def search_115_resources():
    """Search only 115 cloud resources."""
    keyword = request.args.get('kw', '').strip()
    if not keyword:
        return jsonify({'success': False, 'error': '请输入搜索关键词'}), 400
    
    pan_service = get_pan_search_service()
    result = pan_service.search_115(keyword)
    return jsonify(result)


@resource_search_bp.route('/pan/123', methods=['GET'])
@require_auth
def search_123_resources():
    """Search only 123 cloud resources."""
    keyword = request.args.get('kw', '').strip()
    if not keyword:
        return jsonify({'success': False, 'error': '请输入搜索关键词'}), 400
    
    pan_service = get_pan_search_service()
    result = pan_service.search_123(keyword)
    return jsonify(result)


@resource_search_bp.route('/pan/config', methods=['GET'])
@require_auth
def get_pansou_config():
    """Get Pansou API configuration."""
    try:
        from app import get_db_session
        from services.secret_store import SecretStore
        from services.pan_search_service import PANSOU_API_KEY, DEFAULT_PANSOU_API_BASE
        
        store = SecretStore(get_db_session)
        url = store.get_secret(PANSOU_API_KEY)
        
        return jsonify({
            'success': True,
            'data': {
                'api_url': url or '',
                'default_url': DEFAULT_PANSOU_API_BASE
            }
        })
    except Exception as e:
        logger.error(f"获取 Pansou 配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@resource_search_bp.route('/pan/config', methods=['POST'])
@require_auth
def save_pansou_config():
    """Save Pansou API configuration."""
    try:
        from app import get_db_session
        from services.secret_store import SecretStore
        from services.pan_search_service import PANSOU_API_KEY, get_pan_search_service
        
        data = request.get_json() or {}
        api_url = data.get('api_url', '').strip()
        
        store = SecretStore(get_db_session)
        
        if api_url:
            store.set_secret(PANSOU_API_KEY, api_url)
            logger.info(f"Pansou API URL 已更新: {api_url}")
        else:
            # 如果为空，则删除配置，使用默认值
            store.delete_secret(PANSOU_API_KEY)
            logger.info("Pansou API URL 已重置为默认值")
        
        # 重置全局服务实例，使其重新读取配置
        import services.pan_search_service as pan_module
        pan_module._pan_search_service = None
        
        return jsonify({
            'success': True,
            'message': '配置已保存'
        })
    except Exception as e:
        logger.error(f"保存 Pansou 配置失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

