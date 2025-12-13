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
                'error': 'Emby service not initialized'
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
            'error': f'Failed to test connection: {str(e)}'
        }), 500


@emby_bp.route('/scan-missing', methods=['POST'])
@require_auth
def scan_missing_episodes():
    """Scan for missing episodes in Emby."""
    try:
        if not _emby_service:
            return jsonify({
                'success': False,
                'error': 'Emby service not initialized'
            }), 500
        
        result = _emby_service.scan_missing_episodes()
        
        return jsonify({
            'success': result['success'],
            'data': result.get('data', [])
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to scan missing episodes: {str(e)}'
        }), 500


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
        
        # 获取通知目标
        config = _store.get_config() if _store else {}
        telegram_config = config.get('telegram', {})
        notification_channel = telegram_config.get('notificationChannelId')
        
        if not notification_channel:
            return jsonify({'ok': True, 'message': 'No notification channel configured'}), 200
        
        if not _telegram_service:
            return jsonify({'ok': True, 'message': 'Telegram service not available'}), 200
        
        # 处理新媒体入库通知
        if 'library.new' in event_type.lower() or event_type == 'item.add':
            return _handle_library_new(data, notification_channel)
        
        # 处理播放开始通知
        elif 'playback.start' in event_type.lower() or event_type == 'playback.start':
            return _handle_playback_start(data, notification_channel)
        
        # 处理播放停止通知
        elif 'playback.stop' in event_type.lower() or event_type == 'playback.stop':
            return _handle_playback_stop(data, notification_channel)
        
        return jsonify({'ok': True, 'message': f'Event {event_type} not handled'}), 200
        
    except Exception as e:
        import logging
        logging.error(f"Emby webhook error: {e}")
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
            
            return jsonify({'ok': True, 'message': 'Library notification sent'}), 200
    
    # 简单通知
    type_map = {'Movie': '电影', 'Series': '剧集', 'Episode': '单集', 'Season': '季'}
    type_text = type_map.get(item_type, item_type)
    simple_text = f"📥 *新媒体入库*\n\n🎬 *{item_name}*\n📺 类型: {type_text}\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    _telegram_service.send_message(channel_id, simple_text)
    
    return jsonify({'ok': True, 'message': 'Simple notification sent'}), 200


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
    
    return jsonify({'ok': True, 'message': 'Playback start notification sent'}), 200


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
    
    return jsonify({'ok': True, 'message': 'Playback stop notification sent'}), 200


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
                'message': 'Simple test notification sent',
                'result': result
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'测试失败: {str(e)}'
        }), 500
