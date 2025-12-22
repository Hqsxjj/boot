from flask import Blueprint, request, jsonify
from middleware.auth import require_auth
from services.emby_service import EmbyService
from persistence.store import DataStore

emby_bp = Blueprint('emby', __name__, url_prefix='/api/emby')

# Global instances (set during initialization)
_emby_service = None
_store = None


def init_emby_blueprint(store: DataStore):
    """Initialize emby blueprint with required services."""
    global _emby_service, _store
    _store = store
    _emby_service = EmbyService(store)
    emby_bp.store = store
    return emby_bp


@emby_bp.route('/test-connection', methods=['POST'])
@require_auth
def test_emby_connection():
    """Test connection to Emby server."""
    try:
        if not _emby_service:
            return jsonify({
                'success': False,
                'error': 'Emby 服务未初始化'
            }), 500
        
        result = _emby_service.test_connection()
        
        return jsonify({
            'success': result['success'],
            'data': {
                'success': result['success'],
                'latency': result.get('latency', 0),
                'msg': result.get('msg', '')
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'连接测试失败: {str(e)}'
        }), 500


@emby_bp.route('/scan-missing', methods=['POST'])
@require_auth
def scan_missing_episodes():
    """Scan for missing episodes in Emby."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        if not _emby_service:
            return jsonify({
                'success': False,
                'error': 'Emby 服务未初始化'
            }), 500
        
        # 检查是否请求演示数据
        data = request.get_json() or {}
        demo_mode = data.get('demo', False)
        
        if demo_mode:
            # 返回模拟数据用于演示
            mock_data = _get_mock_missing_data()
            return jsonify({
                'success': True,
                'data': mock_data,
                'demo': True
            }), 200
        
        result = _emby_service.scan_missing_episodes()
        logger.info(f"扫描缺集结果: 成功={result.get('success')}, 数量={len(result.get('data', []))}")
        
        # 如果扫描失败，返回错误信息
        if not result.get('success'):
            error_msg = result.get('error', '扫描失败')
            logger.warning(f"扫描缺集失败: {error_msg}")
            
            # 检查是否是配置问题
            if 'Emby未配置' in error_msg:
                return jsonify({
                    'success': False,
                    'error': '请先配置 Emby 服务器地址和 API Key',
                    'data': []
                }), 200
            elif '连接' in error_msg or 'timeout' in error_msg.lower():
                return jsonify({
                    'success': False,
                    'error': f'无法连接 Emby 服务器: {error_msg}',
                    'data': []
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': error_msg,
                    'data': []
                }), 200
        
        return jsonify({
            'success': True,
            'data': result.get('data', [])
        }), 200
        
    except Exception as e:
        import traceback
        logging.getLogger(__name__).error(f"扫描缺集异常: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': f'扫描缺集失败: {str(e)}'
        }), 500


@emby_bp.route('/series-list', methods=['GET'])
@require_auth
def get_series_list():
    """获取 Emby 中所有电视剧列表 (用于逐个扫描缺集)"""
    try:
        if not _emby_service:
            return jsonify({'success': False, 'error': 'Emby 服务未初始化'}), 500
        
        result = _emby_service.get_series_list()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/scan-series/<series_id>', methods=['POST'])
@require_auth
def scan_single_series(series_id: str):
    """扫描单个电视剧的缺集情况"""
    try:
        if not _emby_service:
            return jsonify({'success': False, 'error': 'Emby 服务未初始化'}), 500
        
        result = _emby_service.scan_single_series(series_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def _get_mock_missing_data():
    """返回演示用的模拟缺集数据"""
    return [
        {
            'id': 'mock1',
            'name': '鱿鱼游戏',
            'season': 2,
            'totalEp': 7,
            'localEp': 4,
            'missing': 'E05, E06, E07',
            'poster': 'https://image.tmdb.org/t/p/w200/dDlEmu3EZ0Pgg93K2SVNLCjCSvE.jpg'
        },
        {
            'id': 'mock2',
            'name': '怪奇物语',
            'season': 4,
            'totalEp': 9,
            'localEp': 7,
            'missing': 'E08, E09',
            'poster': 'https://image.tmdb.org/t/p/w200/49WJfeN0moxb9IPfGn8AIqMGskD.jpg'
        },
        {
            'id': 'mock3',
            'name': '黑暗荣耀',
            'season': 2,
            'totalEp': 8,
            'localEp': 6,
            'missing': 'E07, E08',
            'poster': 'https://image.tmdb.org/t/p/w200/9knZcsG1XM4T6PEk9WPGH0ZmPHf.jpg'
        },
        {
            'id': 'mock4',
            'name': '权力的游戏',
            'season': 8,
            'totalEp': 6,
            'localEp': 6,
            'missing': '',
            'poster': 'https://image.tmdb.org/t/p/w200/z121dSTR7PY9KxKuvwiIFSYW8cf.jpg'
        },
        {
            'id': 'mock5',
            'name': '纸钞屋',
            'season': 5,
            'totalEp': 10,
            'localEp': 8,
            'missing': 'E09, E10',
            'poster': 'https://image.tmdb.org/t/p/w200/reEMJA1uzscCbkpeRJeTT2bjqUp.jpg'
        }
    ]


@emby_bp.route('/refresh-library', methods=['POST'])
@require_auth
def refresh_library():
    """刷新 Emby 媒体库"""
    try:
        if not _emby_service:
            return jsonify({
                'success': False,
                'error': 'Emby 服务未初始化'
            }), 500
        
        data = request.get_json() or {}
        library_id = data.get('libraryId')
        
        result = _emby_service.refresh_library(library_id)
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'刷新失败: {str(e)}'
        }), 500


@emby_bp.route('/media-info/<item_id>', methods=['GET'])
@require_auth
def get_media_info(item_id: str):
    """获取媒体文件的技术信息（分辨率、编码、字幕等）"""
    try:
        if not _emby_service:
            return jsonify({
                'success': False,
                'error': 'Emby 服务未初始化'
            }), 500
        
        result = _emby_service.get_media_info(item_id)
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取媒体信息失败: {str(e)}'
        }), 500


@emby_bp.route('/scan-and-notify', methods=['POST'])
@require_auth
def scan_and_notify():
    """扫描媒体库并获取新增项目（含媒体信息），用于 Bot 通知"""
    try:
        if not _emby_service:
            return jsonify({
                'success': False,
                'error': 'Emby 服务未初始化'
            }), 500
        
        data = request.get_json() or {}
        library_id = data.get('libraryId')
        
        result = _emby_service.scan_and_notify(library_id)
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'扫描失败: {str(e)}'
        }), 500


@emby_bp.route('/latest-items', methods=['GET'])
@require_auth
def get_latest_items():
    """获取最新入库的项目"""
    try:
        if not _emby_service:
            return jsonify({
                'success': False,
                'error': 'Emby 服务未初始化'
            }), 500
        
        limit = request.args.get('limit', 10, type=int)
        item_type = request.args.get('type')
        
        result = _emby_service.get_latest_items(limit=limit, item_type=item_type)
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取失败: {str(e)}'
        }), 500


# Telegram Bot Service 引用 (用于发送通知)
_telegram_service = None

def set_telegram_service(telegram_service):
    """设置 Telegram 服务实例"""
    global _telegram_service
    _telegram_service = telegram_service


@emby_bp.route('/webhook', methods=['POST'])
def emby_webhook():
    """
    处理 Emby Webhook 回调
    
    支持的事件类型:
    - library.new: 新媒体入库
    - playback.start: 开始播放
    - playback.stop: 停止播放
    """
    try:
        data = request.get_json() or {}
        event_type = data.get('Event') or data.get('event', '')
        
        # 获取通知目标 - 优先从 TelegramBotService 获取
        notification_channel = None
        if _telegram_service:
            notification_channel = _telegram_service.get_notification_channel()
        
        # 回退到 config store
        if not notification_channel and _store:
            config = _store.get_config()
            telegram_config = config.get('telegram', {})
            notification_channel = telegram_config.get('notificationChannelId')
        
        if not notification_channel:
            return jsonify({'ok': True, 'message': '未配置通知频道'}), 200
        
        if not _telegram_service:
            return jsonify({'ok': True, 'message': 'Telegram 服务不可用'}), 200
        
        # 处理新媒体入库通知
        if 'library.new' in event_type.lower() or event_type == 'item.add':
            return _handle_library_new(data, notification_channel)
        
        # 处理播放开始通知
        elif 'playback.start' in event_type.lower() or event_type == 'playback.start':
            return _handle_playback_start(data, notification_channel)
        
        # 处理播放停止通知
        elif 'playback.stop' in event_type.lower() or event_type == 'playback.stop':
            return _handle_playback_stop(data, notification_channel)
        
        return jsonify({'ok': True, 'message': f'事件 {event_type} 未处理'}), 200
        
    except Exception as e:
        import logging
        logging.error(f"Emby webhook 错误: {e}")
        return jsonify({'ok': True}), 200


def _handle_library_new(data: dict, channel_id: str):
    """处理新媒体入库通知"""
    from datetime import datetime
    
    item = data.get('Item', {})
    item_id = item.get('Id')
    item_name = item.get('Name', '未知')
    item_type = item.get('Type', 'Unknown')
    
    # 获取详细信息
    if _emby_service and item_id:
        details = _emby_service.get_item_details(item_id)
        if details.get('success'):
            item_data = details.get('data', {})
            
            # 构建通知文本
            text = _emby_service.format_notification_text(item_data)
            text = f"📥 *新媒体入库*\n\n{text}\n\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            # 获取高清横幅图 (backdrop) 或海报
            image_url = item_data.get('backdrop_url') or item_data.get('poster_url')
            
            if image_url:
                _telegram_service.send_photo_with_caption(
                    chat_id=channel_id,
                    photo_url=image_url,
                    caption=text
                )
            else:
                _telegram_service.send_message(channel_id, text)
            
            return jsonify({'ok': True, 'message': '媒体入库通知已发送'}), 200
    
    # 简单通知
    type_map = {'Movie': '电影', 'Series': '剧集', 'Episode': '单集', 'Season': '季'}
    type_text = type_map.get(item_type, item_type)
    simple_text = f"📥 *新媒体入库*\n\n🎬 *{item_name}*\n📺 类型: {type_text}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    _telegram_service.send_message(channel_id, simple_text)
    
    return jsonify({'ok': True, 'message': '简单通知已发送'}), 200


def _handle_playback_start(data: dict, channel_id: str):
    """处理播放开始通知"""
    from datetime import datetime
    
    item = data.get('Item', {})
    session = data.get('Session', {})
    user = session.get('UserName') or data.get('User', {}).get('Name', '未知用户')
    
    item_name = item.get('Name', '未知')
    item_type = item.get('Type', 'Unknown')
    series_name = item.get('SeriesName')
    
    # 如果是剧集，显示剧名
    if series_name:
        season_num = item.get('ParentIndexNumber', '')
        episode_num = item.get('IndexNumber', '')
        if season_num and episode_num:
            display_name = f"{series_name} S{season_num}E{episode_num}\n_{item_name}_"
        else:
            display_name = f"{series_name} - {item_name}"
    else:
        display_name = item_name
    
    # 获取设备信息
    device_name = session.get('DeviceName', '未知设备')
    client = session.get('Client', '')
    client_version = session.get('ApplicationVersion', '')
    
    # 构建客户端信息
    client_info = client
    if client_version:
        client_info = f"{client} {client_version}"
    
    # 获取位置信息 (从 RemoteEndPoint 解析)
    remote_ip = session.get('RemoteEndPoint', '')
    location = data.get('Location') or session.get('Location', '')
    
    # 获取高清图片
    item_id = item.get('Id')
    image_url = None
    
    if _emby_service and item_id:
        details = _emby_service.get_item_details(item_id)
        if details.get('success'):
            item_data = details.get('data', {})
            image_url = item_data.get('backdrop_url') or item_data.get('poster_url')
    
    # 构建通知
    text = (
        f"▶️ *开始播放*\n\n"
        f"🎬 *{display_name}*\n"
        f"👤 用户: {user}\n"
        f"📱 设备: {device_name}"
    )
    if client_info:
        text += f"\n📲 客户端: {client_info}"
    if location:
        text += f"\n📍 位置: {location}"
    text += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    if image_url:
        _telegram_service.send_photo_with_caption(
            chat_id=channel_id,
            photo_url=image_url,
            caption=text
        )
    else:
        _telegram_service.send_message(channel_id, text)
    
    return jsonify({'ok': True, 'message': '播放开始通知已发送'}), 200


def _handle_playback_stop(data: dict, channel_id: str):
    """处理播放停止通知"""
    from datetime import datetime
    
    item = data.get('Item', {})
    session = data.get('Session', {})
    user = session.get('UserName') or data.get('User', {}).get('Name', '未知用户')
    
    item_name = item.get('Name', '未知')
    series_name = item.get('SeriesName')
    
    # 如果是剧集，显示剧名
    if series_name:
        display_name = f"{series_name} - {item_name}"
    else:
        display_name = item_name
    
    # 播放进度
    position_ticks = data.get('PlaybackPositionTicks', 0)
    runtime_ticks = item.get('RunTimeTicks', 1)
    
    if runtime_ticks > 0:
        progress = min(100, int((position_ticks / runtime_ticks) * 100))
    else:
        progress = 0
    
    progress_bar = '█' * (progress // 10) + '░' * (10 - progress // 10)
    
    text = (
        f"⏹️ *停止播放*\n\n"
        f"🎬 *{display_name}*\n"
        f"👤 用户: {user}\n"
        f"📊 进度: {progress_bar} {progress}%\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    
    _telegram_service.send_message(channel_id, text)
    
    return jsonify({'ok': True, 'message': '播放停止通知已发送'}), 200


@emby_bp.route('/test-notification', methods=['POST'])
@require_auth
def test_emby_notification():
    """测试发送 Emby 通知到指定群组"""
    try:
        if not _emby_service:
            return jsonify({
                'success': False,
                'error': 'Emby 服务未初始化'
            }), 500
        
        if not _telegram_service:
            return jsonify({
                'success': False,
                'error': 'Telegram 服务未初始化'
            }), 500
        
        # 获取通知渠道
        config = _store.get_config() if _store else {}
        telegram_config = config.get('telegram', {})
        notification_channel = telegram_config.get('notificationChannelId')
        
        if not notification_channel:
            return jsonify({
                'success': False,
                'error': '未配置通知频道ID'
            }), 400
        
        data = request.get_json() or {}
        
        # 获取最新的媒体项作为测试
        latest = _emby_service.get_latest_items(limit=1)
        
        if latest.get('success') and latest.get('data'):
            item = latest['data'][0]
            item_id = item.get('id')
            
            # 获取详细信息
            details = _emby_service.get_item_details(item_id)
            if details.get('success'):
                item_data = details.get('data', {})
                text = _emby_service.format_notification_text(item_data)
                text = f"🧪 *测试通知*\n\n{text}\n\n⏰ {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}"
                
                image_url = item_data.get('backdrop_url') or item_data.get('poster_url')
                
                if image_url:
                    result = _telegram_service.send_photo_with_caption(
                        chat_id=notification_channel,
                        photo_url=image_url,
                        caption=text
                    )
                else:
                    result = _telegram_service.send_message(notification_channel, text)
                
                return jsonify({
                    'success': True,
                    'data': {
                        'item_name': item_data.get('name'),
                        'channel_id': notification_channel,
                        'has_image': bool(image_url),
                        'result': result
                    }
                }), 200
        
        # 无媒体项时发送简单测试
        from datetime import datetime
        simple_text = f"🧪 *Emby 通知测试*\n\n连接正常！\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        result = _telegram_service.send_message(notification_channel, simple_text)
        
        return jsonify({
            'success': True,
            'data': {
                'message': '简单测试通知已发送',
                'result': result
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'测试失败: {str(e)}'
        }), 500


# ==================== 封面生成器 API ====================

from services.cover_generator import get_cover_generator, THEMES


@emby_bp.route('/cover/themes', methods=['GET'])
@require_auth
def get_cover_themes():
    """获取可用的封面主题列表"""
    themes = [{"index": i, "name": t["name"], "colors": t["colors"]} for i, t in enumerate(THEMES)]
    return jsonify({
        'success': True,
        'data': themes
    }), 200


@emby_bp.route('/cover/libraries', methods=['GET'])
@require_auth
def get_cover_libraries():
    """获取 Emby 媒体库列表（用于封面生成）"""
    try:
        if not _store:
            return jsonify({'success': False, 'error': '服务未初始化'}), 500
            
        config = _store.get_config()
        emby_config = config.get('emby', {})
        emby_url = emby_config.get('serverUrl', '')
        api_key = emby_config.get('apiKey', '')
        
        if not emby_url or not api_key:
            return jsonify({'success': False, 'error': '请先配置 Emby 服务器'}), 400
        
        generator = get_cover_generator()
        generator.set_emby_config(emby_url, api_key)
        libraries = generator.get_libraries()
        
        return jsonify({
            'success': True,
            'data': libraries
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@emby_bp.route('/apply_covers', methods=['POST'])
@require_auth
def apply_covers_to_emby():
    """批量生成并覆盖封面"""
    try:
        if not _store:
            return jsonify({'success': False, 'error': '服务未初始化'}), 500
        
        config = _store.get_config()
        emby_config = config.get('emby', {})
        emby_url = emby_config.get('serverUrl', '')
        api_key = emby_config.get('apiKey', '')
        
        if not emby_url or not api_key:
            return jsonify({'success': False, 'error': '请先配置 Emby 服务器'}), 400
        
        data = request.get_json()
        library_ids = data.get('library_ids', [])
        cover_config = data.get('config', {})
        
        if not library_ids:
            return jsonify({'success': False, 'error': '未选择任何媒体库'}), 400
            
        generator = get_cover_generator()
        generator.set_emby_config(emby_url, api_key)
        
        # 获取所有库的信息以便查名称
        libraries = generator.get_libraries()
        lib_map = {l['id']: l for l in libraries}
        
        success_count = 0
        results = []
        
        for lib_id in library_ids:
            try:
                target_lib = lib_map.get(lib_id)
                if not target_lib:
                    results.append({'id': lib_id, 'success': False, 'msg': '库不存在'})
                    continue
                
                # 1. 获取海报
                posters = generator.get_library_posters(lib_id, limit=6)
                if not posters:
                    results.append({'id': lib_id, 'success': False, 'msg': '无海报'})
                    continue
                
                # 2. 准备参数
                title = target_lib['name']
                
                # 清理库名称用于文件夹/文件名 (移除不安全字符)
                safe_lib_name = "".join(c if c.isalnum() or c in (' ', '-', '_', '.') else '_' for c in title).strip()
                if not safe_lib_name:
                    safe_lib_name = lib_id
                
                # 自动副标题
                type_map = {
                    'movies': 'MOVIE COLLECTION',
                    'tvshows': 'TV SHOWS',
                    'music': 'MUSIC COLLECTION',
                    'homevideos': 'HOME VIDEOS',
                    'books': 'BOOK COLLECTION',
                    'photos': 'PHOTO ALBUM',
                    'musicvideos': 'MUSIC VIDEOS'
                }
                subtitle = type_map.get(target_lib.get('type', '').lower(), 'MEDIA COLLECTION')
                
                width = 1920
                height = 1080
                cover_format = cover_config.get('format', 'png')
                
                # 生成参数
                # [差异化] 基于媒体库 ID 计算唯一的主题索引，实现"每个媒体库都不一样"
                # 用户选择的主题作为基准，ID hash 作为偏移量
                import zlib
                from services.cover_generator import THEMES
                base_theme_idx = cover_config.get('theme', 0)
                id_hash = zlib.adler32(lib_id.encode('utf-8'))
                # 使用 hash 偏移主题，保证确定性随机
                final_theme_idx = (base_theme_idx + id_hash) % len(THEMES)

                gen_kwargs = {
                    'title': title,
                    'subtitle': subtitle,
                    'theme_index': final_theme_idx,
                    'width': width,
                    'height': height,
                    'title_size': cover_config.get('titleSize', 172),
                    'offset_x': cover_config.get('offsetX', 50),
                    'poster_scale_pct': cover_config.get('posterScale', 32),
                    'v_align_pct': cover_config.get('vAlign', 60)
                }
                
                # 3. 创建本地缓存目录
                import os
                cache_dir = os.path.join('/data', 'covers', safe_lib_name)
                os.makedirs(cache_dir, exist_ok=True)
                
                # 4. 生成封面并保存到本地
                file_ext = 'gif' if cover_format == 'gif' else 'png'
                local_file_path = os.path.join(cache_dir, f"{safe_lib_name}.{file_ext}")
                content_type = 'image/gif' if cover_format == 'gif' else 'image/png'
                
                if cover_format == 'gif':
                    image_data = generator.generate_animated_cover(
                        posters, 
                        frame_count=len(posters) * 4,
                        duration_ms=150,
                        **gen_kwargs
                    )
                    with open(local_file_path, 'wb') as f:
                        f.write(image_data)
                else:
                    img = generator.generate_cover(posters, **gen_kwargs)
                    img.save(local_file_path, format='PNG')
                
                import logging
                logging.getLogger(__name__).info(f"封面已保存到本地: {local_file_path}")
                
                # 5. 读取本地文件并上传到 Emby
                with open(local_file_path, 'rb') as f:
                    image_data = f.read()
                
                if generator.upload_cover(lib_id, image_data, content_type):
                    success_count += 1
                    results.append({'id': lib_id, 'success': True, 'localPath': local_file_path})
                else:
                    results.append({'id': lib_id, 'success': False, 'msg': '上传失败', 'localPath': local_file_path})
                    
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"处理库 {lib_id} 失败: {e}")
                results.append({'id': lib_id, 'success': False, 'msg': str(e)})
        
        return jsonify({
            'success': True,
            'processed': len(library_ids),
            'success_count': success_count,
            'details': results
        }), 200
        
    except Exception as e:
        import traceback
        import logging
        logging.getLogger(__name__).error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/posters/<library_id>', methods=['GET'])
@require_auth
def get_library_posters(library_id: str):
    """获取媒体库海报列表（base64 格式）"""
    try:
        if not _store:
            return jsonify({'success': False, 'error': '服务未初始化'}), 500
            
        config = _store.get_config()
        emby_config = config.get('emby', {})
        emby_url = emby_config.get('serverUrl', '')
        api_key = emby_config.get('apiKey', '')
        
        if not emby_url or not api_key:
            return jsonify({'success': False, 'error': '请先配置 Emby 服务器'}), 400
        
        limit = request.args.get('limit', 10, type=int)
        
        generator = get_cover_generator()
        generator.set_emby_config(emby_url, api_key)
        posters = generator.get_library_posters(library_id, limit=limit)
        
        # 转换为 base64
        poster_data = []
        for img in posters:
            b64 = generator.cover_to_base64(img)
            poster_data.append(b64)
        
        return jsonify({
            'success': True,
            'data': poster_data
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/generate', methods=['POST'])
@require_auth
def generate_cover():
    """生成封面图"""
    try:
        if not _store:
            return jsonify({'success': False, 'error': '服务未初始化'}), 500
            
        config = _store.get_config()
        emby_config = config.get('emby', {})
        emby_url = emby_config.get('serverUrl', '')
        api_key = emby_config.get('apiKey', '')
        
        data = request.get_json() or {}
        
        # 支持两种格式：直接参数或嵌套在 config 中
        cover_config = data.get('config', {})
        
        library_id = data.get('libraryId')
        title = cover_config.get('title') or data.get('title', '电影收藏')
        subtitle = cover_config.get('subtitle') or data.get('subtitle', 'MOVIE COLLECTION')
        theme_index = cover_config.get('theme') or data.get('themeIndex', 0)
        output_format = cover_config.get('format') or data.get('format', 'png')  # 'png' or 'gif'
        title_size = cover_config.get('titleSize') or data.get('titleSize', 130)
        offset_x = cover_config.get('offsetX') or data.get('offsetX', 200)
        poster_scale = cover_config.get('posterScale') or data.get('posterScale', 30)
        v_align = cover_config.get('vAlign') or data.get('vAlign', 22)
        spacing = cover_config.get('spacing') or data.get('spacing', 1.0)
        
        generator = get_cover_generator()
        
        if emby_url and api_key:
            generator.set_emby_config(emby_url, api_key)
        
        # 获取海报
        posters = []
        if library_id:
            posters = generator.get_library_posters(library_id, limit=5)
        
        if not posters:
            return jsonify({'success': False, 'error': '未能获取海报图片'}), 400
        
        # 创建预览缓存目录
        import os
        cache_dir = os.path.join('/data', 'covers', 'preview')
        os.makedirs(cache_dir, exist_ok=True)
        
        # 清理标题用于文件名
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_', '.') else '_' for c in title).strip() or 'cover'
        file_ext = 'gif' if output_format.lower() == 'gif' else 'png'
        local_file_path = os.path.join(cache_dir, f"{safe_title}.{file_ext}")
        
        # 生成封面
        if output_format.lower() == 'gif':
            gif_data = generator.generate_animated_cover(
                posters=posters,
                title=title,
                subtitle=subtitle,
                theme_index=theme_index,
                title_size=title_size,
                offset_x=offset_x,
                poster_scale_pct=poster_scale,
                v_align_pct=v_align,
                frame_count=len(posters) * 4,
                duration_ms=150,
                spacing=spacing
            )
            # 保存到本地缓存
            with open(local_file_path, 'wb') as f:
                f.write(gif_data)
            result_b64 = generator.bytes_to_base64(gif_data, "image/gif")
        else:
            cover_img = generator.generate_cover(
                posters=posters,
                title=title,
                subtitle=subtitle,
                theme_index=theme_index,
                title_size=title_size,
                offset_x=offset_x,
                poster_scale_pct=poster_scale,
                v_align_pct=v_align,
                spacing=spacing
            )
            # 保存到本地缓存
            cover_img.save(local_file_path, format='PNG')
            result_b64 = generator.cover_to_base64(cover_img)
        
        import logging
        logging.getLogger(__name__).info(f"封面预览已保存到本地: {local_file_path}")
        
        return jsonify({
            'success': True,
            'data': {
                'image': result_b64,
                'format': output_format,
                'localPath': local_file_path
            }
        }), 200
    except Exception as e:
        import traceback
        import logging
        logging.error(f"生成封面失败: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

