"""
媒体整理 API 蓝图
提供文件名解析、TMDB 搜索、重命名整理的 REST API
"""
from flask import Blueprint, request, jsonify
from middleware.auth import require_auth, optional_auth
from services.media_parser import get_media_parser, MediaInfo
from services.media_organizer import get_media_organizer
from services.tmdb_service import TmdbService
from persistence.store import DataStore
import logging

logger = logging.getLogger(__name__)

organize_bp = Blueprint('organize', __name__, url_prefix='/api/organize')

# 全局服务实例
_tmdb_service = None
_media_organizer = None
_store = None


def init_organize_blueprint(store: DataStore, tmdb_service: TmdbService = None, 
                            cloud115_service=None, cloud123_service=None):
    """初始化整理蓝图"""
    global _tmdb_service, _media_organizer, _store
    _store = store
    _tmdb_service = tmdb_service or TmdbService(config_store=store)
    _media_organizer = get_media_organizer(store, cloud115_service, cloud123_service)
    return organize_bp


@organize_bp.route('/parse', methods=['POST'])
@optional_auth
def parse_filename():
    """
    解析文件名
    
    Request:
        {"filename": "行尸走肉.The.Walking.Dead.S01E01.1080p.WEB-DL.x264.mkv"}
    
    Response:
        {
            "success": true,
            "data": {
                "title": "行尸走肉",
                "year": null,
                "type": "tv",
                "season": 1,
                "episode": 1,
                "season_str": "S01",
                "episode_str": "E01",
                "resolution": "1080p",
                "resource_type": "WEB-DL",
                "video_codec": "AVC"
            }
        }
    """
    try:
        data = request.get_json() or {}
        filename = data.get('filename', '').strip()
        
        if not filename:
            return jsonify({
                'success': False,
                'error': '文件名不能为空'
            }), 400
        
        parser = get_media_parser()
        info = parser.parse(filename)
        
        return jsonify({
            'success': True,
            'data': info.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"解析文件名失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@organize_bp.route('/search', methods=['POST'])
@require_auth
def search_tmdb():
    """
    搜索 TMDB
    
    Request:
        {
            "title": "行尸走肉",
            "type": "tv",  // movie, tv, auto
            "year": "2010"  // 可选
        }
    
    Response:
        {
            "success": true,
            "data": {
                "results": [...],
                "total_results": 10
            }
        }
    """
    try:
        data = request.get_json() or {}
        title = data.get('title', '').strip()
        media_type = data.get('type', 'auto')
        year = data.get('year')
        
        if not title:
            return jsonify({
                'success': False,
                'error': '标题不能为空'
            }), 400
        
        config = _store.get_config() if _store else {}
        result = _tmdb_service.search(title, media_type, year, config)
        
        return jsonify(result), 200 if result.get('success') else 400
        
    except Exception as e:
        logger.error(f"TMDB 搜索失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@organize_bp.route('/details/<media_type>/<int:tmdb_id>', methods=['GET'])
@require_auth
def get_tmdb_details(media_type: str, tmdb_id: int):
    """
    获取 TMDB 详情
    
    URL:
        /api/organize/details/movie/12345
        /api/organize/details/tv/12345
    """
    try:
        config = _store.get_config() if _store else {}
        
        if media_type == 'movie':
            result = _tmdb_service.get_movie_details(tmdb_id, config)
        elif media_type == 'tv':
            result = _tmdb_service.get_tv_details(tmdb_id, config)
        else:
            return jsonify({
                'success': False,
                'error': f'无效的媒体类型: {media_type}'
            }), 400
        
        return jsonify(result), 200 if result.get('success') else 400
        
    except Exception as e:
        logger.error(f"获取 TMDB 详情失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@organize_bp.route('/preview', methods=['POST'])
@require_auth
def preview_organize():
    """
    预览整理结果
    
    Request:
        {
            "filename": "行尸走肉.S01E01.mkv",
            "tmdb_id": 1402,  // 可选
            "media_type": "tv",  // 可选
            "name_template": "{{title}} - {{season}}{{episode}}",  // 可选
            "dir_template": "电视剧/{{title}}/Season {{season_num}}",  // 可选
            "base_dir": "/downloads"  // 可选
        }
    """
    try:
        data = request.get_json() or {}
        filename = data.get('filename', '').strip()
        tmdb_id = data.get('tmdb_id')
        media_type = data.get('media_type', 'auto')
        name_template = data.get('name_template')
        dir_template = data.get('dir_template')
        base_dir = data.get('base_dir', '')
        
        if not filename:
            return jsonify({
                'success': False,
                'error': 'filename is required'
            }), 400
        
        # 解析文件名
        parser = get_media_parser()
        media_info = parser.parse(filename)
        
        # 获取文件扩展名
        ext = ''
        for e in ['.mkv', '.mp4', '.avi', '.wmv', '.flv', '.mov', '.ts']:
            if filename.lower().endswith(e):
                ext = e
                break
        if not ext:
            ext = '.mkv'
        
        # 获取 TMDB 信息
        tmdb_info = None
        config = _store.get_config() if _store else {}
        
        if tmdb_id:
            # 直接获取详情
            if media_type == 'movie':
                result = _tmdb_service.get_movie_details(tmdb_id, config)
            else:
                result = _tmdb_service.get_tv_details(tmdb_id, config)
            
            if result.get('success'):
                tmdb_info = result['data']
        elif media_info.title:
            # 自动搜索
            search_type = media_type if media_type != 'auto' else (
                'tv' if media_info.type.value == 'tv' else 'movie'
            )
            result = _tmdb_service.search(
                media_info.title, 
                search_type, 
                media_info.year, 
                config
            )
            if result.get('success') and result['data']['results']:
                # 使用第一个结果
                first = result['data']['results'][0]
                if first.get('media_type') == 'movie':
                    detail_result = _tmdb_service.get_movie_details(first['id'], config)
                else:
                    detail_result = _tmdb_service.get_tv_details(first['id'], config)
                
                if detail_result.get('success'):
                    tmdb_info = detail_result['data']
        
        # 预览整理结果
        preview = _media_organizer.preview_organize(
            media_info,
            tmdb_info,
            ext,
            name_template,
            dir_template,
            base_dir
        )
        
        return jsonify(preview), 200
        
    except Exception as e:
        logger.error(f"Preview organize failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@organize_bp.route('/execute', methods=['POST'])
@require_auth
def execute_organize():
    """
    执行重命名整理
    
    Request:
        {
            "cloud_type": "115",  // 115 或 123
            "file_id": "abc123",
            "new_name": "行尸走肉 (2010) - S01E01.mkv",
            "target_dir": "电视剧/行尸走肉 (2010)/Season 1"  // 可选
        }
    """
    try:
        data = request.get_json() or {}
        cloud_type = data.get('cloud_type', '').strip()
        file_id = data.get('file_id', '').strip()
        new_name = data.get('new_name', '').strip()
        target_dir = data.get('target_dir')
        
        if not cloud_type or not file_id or not new_name:
            return jsonify({
                'success': False,
                'error': 'cloud_type, file_id, and new_name are required'
            }), 400
        
        result = _media_organizer.organize_file(
            cloud_type,
            file_id,
            new_name,
            target_dir
        )
        
        return jsonify(result), 200 if result.get('success') else 400
        
    except Exception as e:
        logger.error(f"执行整理失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@organize_bp.route('/batch', methods=['POST'])
@require_auth
def batch_organize():
    """
    批量整理预览
    
    Request:
        {
            "filenames": ["file1.mkv", "file2.mkv"],
            "media_type": "tv",
            "name_template": "...",
            "dir_template": "...",
            "base_dir": "..."
        }
    """
    try:
        data = request.get_json() or {}
        filenames = data.get('filenames', [])
        media_type = data.get('media_type', 'auto')
        name_template = data.get('name_template')
        dir_template = data.get('dir_template')
        base_dir = data.get('base_dir', '')
        
        if not filenames:
            return jsonify({
                'success': False,
                'error': 'filenames is required'
            }), 400
        
        parser = get_media_parser()
        config = _store.get_config() if _store else {}
        results = []
        
        for filename in filenames[:50]:  # 最多50个
            try:
                media_info = parser.parse(filename)
                
                # 获取扩展名
                ext = '.mkv'
                for e in ['.mkv', '.mp4', '.avi', '.wmv', '.flv', '.mov', '.ts']:
                    if filename.lower().endswith(e):
                        ext = e
                        break
                
                # 尝试搜索 TMDB
                tmdb_info = None
                if media_info.title:
                    search_type = media_type if media_type != 'auto' else (
                        'tv' if media_info.type.value == 'tv' else 'movie'
                    )
                    result = _tmdb_service.search(
                        media_info.title,
                        search_type,
                        media_info.year,
                        config
                    )
                    if result.get('success') and result['data']['results']:
                        first = result['data']['results'][0]
                        tmdb_info = first
                
                # 预览
                preview = _media_organizer.preview_organize(
                    media_info,
                    tmdb_info,
                    ext,
                    name_template,
                    dir_template,
                    base_dir
                )
                
                if preview.get('success'):
                    results.append(preview['data'])
                else:
                    results.append({
                        'original_name': filename,
                        'error': preview.get('error')
                    })
                    
            except Exception as e:
                results.append({
                    'original_name': filename,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'data': {
                'results': results,
                'total': len(results)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Batch organize failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
