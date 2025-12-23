"""
媒体整理 API 蓝图
提供文件名解析、TMDB 搜索、重命名整理的 REST API
支持后台任务执行和 QPS 限速
"""
from flask import Blueprint, request, jsonify
from middleware.auth import require_auth, optional_auth
from services.media_parser import get_media_parser, MediaInfo
from services.media_organizer import get_media_organizer
from services.tmdb_service import TmdbService
from services.organize_worker import get_organize_worker
from persistence.store import DataStore
import logging

logger = logging.getLogger(__name__)

organize_bp = Blueprint('organize', __name__, url_prefix='/api/organize')

# 全局服务实例
_tmdb_service = None
_media_organizer = None
_store = None
_organize_worker = None


def init_organize_blueprint(store: DataStore, tmdb_service: TmdbService = None, 
                            cloud115_service=None, cloud123_service=None):
    """初始化整理蓝图"""
    global _tmdb_service, _media_organizer, _store, _organize_worker
    _store = store
    _tmdb_service = tmdb_service or TmdbService(config_store=store)
    _media_organizer = get_media_organizer(store, cloud115_service, cloud123_service)
    
    # 初始化后台整理工作器
    _organize_worker = get_organize_worker()
    _organize_worker.set_services(cloud115_service, cloud123_service, _media_organizer)
    
    # 从配置获取 QPS 限制
    try:
        config = store.get_config()
        qps_115 = config.get('cloud115', {}).get('qps', 1.0)
        qps_123 = config.get('cloud123', {}).get('qps', 2.0)
        _organize_worker.set_qps('115', qps_115)
        _organize_worker.set_qps('123', qps_123)
    except Exception as e:
        logger.warning(f'获取 QPS 配置失败，使用默认值: {e}')
    
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


# ==================== 后台任务 API ====================

@organize_bp.route('/submit', methods=['POST'])
@require_auth
def submit_organize_task():
    """
    提交后台整理任务
    
    Request:
        {
            "cloud_type": "115",  // 115 或 123
            "items": [
                {
                    "fileId": "abc123",
                    "originalName": "原文件名.mkv",  // 可选，用于显示
                    "newName": "新文件名.mkv",
                    "targetDir": "电视剧/xxx/Season 1"  // 可选
                },
                ...
            ]
        }
    
    Response:
        {
            "success": true,
            "data": {
                "taskId": "12345678",
                "status": "pending",
                "totalItems": 10
            }
        }
    """
    try:
        data = request.get_json() or {}
        cloud_type = data.get('cloud_type', '').strip()
        items = data.get('items', [])
        
        if not cloud_type:
            return jsonify({
                'success': False,
                'error': 'cloud_type is required'
            }), 400
        
        if not items:
            return jsonify({
                'success': False,
                'error': 'items is required'
            }), 400
        
        if cloud_type not in ('115', '123'):
            return jsonify({
                'success': False,
                'error': f'不支持的云盘类型: {cloud_type}'
            }), 400
        
        # 验证每个 item
        for item in items:
            if not item.get('fileId') or not item.get('newName'):
                return jsonify({
                    'success': False,
                    'error': '每个 item 必须包含 fileId 和 newName'
                }), 400
        
        # 创建任务
        task = _organize_worker.create_task(cloud_type, items)
        
        # 启动后台执行
        _organize_worker.start_task(task.task_id)
        
        return jsonify({
            'success': True,
            'data': {
                'taskId': task.task_id,
                'status': task.status,
                'totalItems': len(task.items)
            }
        }), 200
        
    except Exception as e:
        logger.error(f"提交整理任务失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@organize_bp.route('/task/<task_id>', methods=['GET'])
@require_auth
def get_organize_task_status(task_id: str):
    """
    获取整理任务状态
    
    Response:
        {
            "success": true,
            "data": {
                "taskId": "12345678",
                "cloudType": "115",
                "status": "running",
                "progress": 50,
                "currentItem": "正在处理的文件名",
                "totalItems": 10,
                "completedCount": 5,
                "failedCount": 0,
                "items": [...]
            }
        }
    """
    try:
        task = _organize_worker.get_task(task_id)
        
        if not task:
            return jsonify({
                'success': False,
                'error': f'任务 {task_id} 不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'data': task.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@organize_bp.route('/task/<task_id>', methods=['DELETE'])
@require_auth
def cancel_organize_task(task_id: str):
    """
    取消整理任务（仅限 pending 状态）
    """
    try:
        success = _organize_worker.cancel_task(task_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'任务 {task_id} 已取消'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': f'无法取消任务 {task_id}（可能已在运行或不存在）'
            }), 400
        
    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@organize_bp.route('/tasks', methods=['GET'])
@require_auth
def list_organize_tasks():
    """
    列出所有整理任务
    """
    try:
        tasks = _organize_worker.get_all_tasks()
        
        return jsonify({
            'success': True,
            'data': tasks
        }), 200
        
    except Exception as e:
        logger.error(f"获取任务列表失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
