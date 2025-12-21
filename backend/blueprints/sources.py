"""
来源管理 API - 管理用户添加的 TG 频道和网站来源
"""
import os
import json
import uuid
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from functools import wraps

logger = logging.getLogger(__name__)

sources_bp = Blueprint('sources', __name__)

# 来源存储文件路径
SOURCES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'sources.json')

def ensure_data_dir():
    """确保数据目录存在"""
    data_dir = os.path.dirname(SOURCES_FILE)
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)

def load_sources():
    """加载来源列表"""
    ensure_data_dir()
    if os.path.exists(SOURCES_FILE):
        try:
            with open(SOURCES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载来源文件失败: {e}")
    return []

def save_sources(sources):
    """保存来源列表"""
    ensure_data_dir()
    try:
        with open(SOURCES_FILE, 'w', encoding='utf-8') as f:
            json.dump(sources, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存来源文件失败: {e}")
        return False


@sources_bp.route('/api/sources', methods=['GET'])
def get_sources():
    """获取所有来源列表"""
    sources = load_sources()
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
        # 支持 t.me/xxx 或 @xxx 格式
        if not (url.startswith('https://t.me/') or url.startswith('t.me/') or url.startswith('@')):
            return jsonify({'success': False, 'error': 'Telegram 链接格式无效，应为 https://t.me/xxx 或 @xxx'}), 400
    elif source_type == 'website':
        if not (url.startswith('http://') or url.startswith('https://')):
            return jsonify({'success': False, 'error': '网站链接应以 http:// 或 https:// 开头'}), 400
    
    # 自动生成名称
    if not name:
        if source_type == 'telegram':
            # 从链接中提取频道名
            if url.startswith('@'):
                name = url
            elif 't.me/' in url:
                name = '@' + url.split('t.me/')[-1].split('/')[0]
            else:
                name = url
        else:
            # 从网址中提取域名
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                name = parsed.netloc or url
            except:
                name = url
    
    sources = load_sources()
    
    # 检查是否已存在相同链接
    for s in sources:
        if s.get('url') == url:
            return jsonify({'success': False, 'error': '该来源已存在'}), 400
    
    new_source = {
        'id': str(uuid.uuid4())[:8],
        'type': source_type,
        'url': url,
        'name': name,
        'enabled': True,
        'created_at': datetime.now().isoformat()
    }
    
    sources.append(new_source)
    
    if save_sources(sources):
        return jsonify({
            'success': True,
            'data': new_source,
            'message': '来源添加成功'
        })
    else:
        return jsonify({'success': False, 'error': '保存失败'}), 500


@sources_bp.route('/api/sources/<source_id>', methods=['DELETE'])
def delete_source(source_id):
    """删除来源"""
    sources = load_sources()
    
    new_sources = [s for s in sources if s.get('id') != source_id]
    
    if len(new_sources) == len(sources):
        return jsonify({'success': False, 'error': '来源不存在'}), 404
    
    if save_sources(new_sources):
        return jsonify({
            'success': True,
            'message': '来源已删除'
        })
    else:
        return jsonify({'success': False, 'error': '保存失败'}), 500


@sources_bp.route('/api/sources/<source_id>', methods=['PUT'])
def update_source(source_id):
    """更新来源（启用/禁用）"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': '缺少数据'}), 400
    
    sources = load_sources()
    
    for source in sources:
        if source.get('id') == source_id:
            if 'enabled' in data:
                source['enabled'] = bool(data['enabled'])
            if 'name' in data:
                source['name'] = data['name'].strip()
            
            if save_sources(sources):
                return jsonify({
                    'success': True,
                    'data': source,
                    'message': '来源已更新'
                })
            else:
                return jsonify({'success': False, 'error': '保存失败'}), 500
    
    return jsonify({'success': False, 'error': '来源不存在'}), 404
