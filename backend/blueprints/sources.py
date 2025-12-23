"""
来源管理 API - 管理用户添加的 TG 频道和网站来源
使用数据库存储替代 JSON 文件
"""
import uuid
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

sources_bp = Blueprint('sources', __name__)

# 全局数据库存储实例
_db_source_store = None


def init_sources_blueprint(session_factory):
    """初始化来源蓝图，设置数据库连接"""
    global _db_source_store
    from persistence.db_source_store import DbSourceStore
    _db_source_store = DbSourceStore(session_factory)
    return sources_bp


def get_source_store():
    """获取数据库存储实例"""
    global _db_source_store
    return _db_source_store


@sources_bp.route('/api/sources', methods=['GET'])
def get_sources():
    """获取所有来源列表"""
    store = get_source_store()
    if store:
        sources = store.get_sources()
    else:
        sources = []
    
    return jsonify({
        'success': True,
        'data': sources
    })


@sources_bp.route('/api/sources', methods=['POST'])
def add_source():
    """添加新来源"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': '缺少数据'}), 400
    
    source_type = data.get('type')
    url = data.get('url', '').strip()
    name = data.get('name', '').strip()
    
    if source_type not in ['telegram', 'website']:
        return jsonify({'success': False, 'error': '无效的来源类型'}), 400
    
    if not url:
        return jsonify({'success': False, 'error': '链接不能为空'}), 400
    
    # 验证链接格式
    if source_type == 'telegram':
        if not (url.startswith('https://t.me/') or url.startswith('t.me/') or url.startswith('@')):
            return jsonify({'success': False, 'error': 'Telegram 链接格式无效，应为 https://t.me/xxx 或 @xxx'}), 400
    elif source_type == 'website':
        if not (url.startswith('http://') or url.startswith('https://')):
            return jsonify({'success': False, 'error': '网站链接应以 http:// 或 https:// 开头'}), 400
    
    # 自动生成名称
    if not name:
        if source_type == 'telegram':
            if url.startswith('@'):
                name = url
            elif 't.me/' in url:
                name = '@' + url.split('t.me/')[-1].split('/')[0]
            else:
                name = url
        else:
            try:
                parsed = urlparse(url)
                name = parsed.netloc or url
            except:
                name = url
    
    store = get_source_store()
    if not store:
        return jsonify({'success': False, 'error': '数据库未初始化'}), 500
    
    # 检查是否已存在
    existing = store.get_sources()
    for s in existing:
        if s.get('url') == url:
            return jsonify({'success': False, 'error': '该来源已存在'}), 400
    
    try:
        new_source = store.add_source(source_type, url, name)
        return jsonify({
            'success': True,
            'data': new_source,
            'message': '来源添加成功'
        })
    except Exception as e:
        logger.error(f"添加来源失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sources_bp.route('/api/sources/<source_id>', methods=['DELETE'])
def delete_source(source_id):
    """删除来源"""
    store = get_source_store()
    if not store:
        return jsonify({'success': False, 'error': '数据库未初始化'}), 500
    
    if store.delete_source(source_id):
        return jsonify({
            'success': True,
            'message': '来源已删除'
        })
    else:
        return jsonify({'success': False, 'error': '来源不存在'}), 404


@sources_bp.route('/api/sources/<source_id>', methods=['PUT'])
def update_source(source_id):
    """更新来源（启用/禁用）"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': '缺少数据'}), 400
    
    store = get_source_store()
    if not store:
        return jsonify({'success': False, 'error': '数据库未初始化'}), 500
    
    updates = {}
    if 'enabled' in data:
        updates['enabled'] = bool(data['enabled'])
    if 'name' in data:
        updates['name'] = data['name'].strip()
    
    result = store.update_source(source_id, **updates)
    
    if result:
        return jsonify({
            'success': True,
            'data': result,
            'message': '来源已更新'
        })
    else:
        return jsonify({'success': False, 'error': '来源不存在'}), 404


@sources_bp.route('/api/sources/crawl', methods=['POST'])
def crawl_sources():
    """手动触发爬取所有启用的来源"""
    try:
        from services.source_crawler_service import get_crawler_service
        crawler = get_crawler_service()
        result = crawler.crawl_all_enabled_sources()
        return jsonify(result)
    except Exception as e:
        logger.error(f"爬取失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sources_bp.route('/api/sources/crawl/<source_id>', methods=['POST'])
def crawl_single_source(source_id):
    """爬取单个来源"""
    try:
        from services.source_crawler_service import get_crawler_service
        
        store = get_source_store()
        if not store:
            return jsonify({'success': False, 'error': '数据库未初始化'}), 500
        
        source = store.get_source(source_id)
        if not source:
            return jsonify({'success': False, 'error': '来源不存在'}), 404
        
        crawler = get_crawler_service()
        result = crawler.crawl_source(source)
        return jsonify(result)
    except Exception as e:
        logger.error(f"爬取失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sources_bp.route('/api/sources/results', methods=['GET'])
def get_crawl_results():
    """获取爬取结果"""
    try:
        store = get_source_store()
        if not store:
            return jsonify({'success': False, 'error': '数据库未初始化'}), 500
        
        keyword = request.args.get('keyword', '')
        
        if keyword:
            resources = store.search_crawled(keyword)
        else:
            resources = store.get_crawled_resources()
        
        return jsonify({
            'success': True,
            'data': resources
        })
    except Exception as e:
        logger.error(f"获取爬取结果失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@sources_bp.route('/api/sources/stats', methods=['GET'])
def get_crawl_stats():
    """获取爬取统计"""
    try:
        store = get_source_store()
        if not store:
            return jsonify({'success': False, 'error': '数据库未初始化'}), 500
        
        stats = store.get_crawl_stats()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
