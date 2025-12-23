from flask import Blueprint, request, jsonify
from middleware.auth import require_auth, optional_auth
from services.emby_service import EmbyService
from persistence.store import DataStore
from models import MissingEpisode
import logging

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


@emby_bp.route('/missing', methods=['GET'])
@optional_auth
def get_missing_episodes():
    """
    Get all missing episodes records from database.
    """
    try:
        session = _store.session_factory()
        records = session.query(MissingEpisode).order_by(MissingEpisode.created_at.desc()).all()
        data = [r.to_dict() for r in records]
        session.close()
        return jsonify({
            'success': True,
            'data': data
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@emby_bp.route('/scan-missing/start', methods=['POST'])
@require_auth
def start_missing_scan_background():
    """Start missing episode scan in background (doesn't block, survives page refresh)."""
    import logging
    from services.background_tasks import get_background_service
    
    logger = logging.getLogger(__name__)
    bg_service = get_background_service()
    
    # Check if scan is already running
    running = bg_service.get_running_tasks(task_type='missing_scan')
    if running:
        return jsonify({
            'success': False,
            'error': '缺集扫描正在进行中',
            'task': running[0]
        }), 200
    
    if not _emby_service:
        return jsonify({
            'success': False,
            'error': 'Emby 服务未初始化'
        }), 500
    
    # Create and run background task
    task = bg_service.create_task('missing_scan', '缺集扫描')
    
    def scan_job(task):
        """Background job for missing episode scan."""
        # 1. Clear existing records in DB at start
        session = _store.session_factory()
        try:
            session.query(MissingEpisode).delete()
            session.commit()
            logger.info("已清空旧的缺集记录")
        except Exception as e:
            session.rollback()
            logger.error(f"清空缺集记录失败: {e}")
        finally:
            session.close()

        series_list = _emby_service.get_series_list()
        if not series_list.get('success'):
            raise Exception(series_list.get('error', '获取剧集列表失败'))
        
        series = series_list.get('data', [])
        total = len(series)
        all_missing = []
        scanned_count = 0
        
        logger.info(f"开始扫描 {total} 个剧集")
        
        for i, s in enumerate(series):
            series_name = s.get('name', s.get('id'))
            series_id = s.get('id')
            
            # Update progress BEFORE scanning (shows current item being processed)
            bg_service.update_progress(task, i, total, f"正在扫描: {series_name}")
            
            try:
                logger.info(f"[{i+1}/{total}] 开始扫描: {series_name} (ID: {series_id})")
                result = _emby_service.scan_single_series(series_id)
                
                if result.get('success'):
                    scanned_count += 1
                    items = result.get('data', [])
                    
                    if items:
                        all_missing.extend(items)
                        logger.info(f"[{i+1}/{total}] {series_name} 发现 {len(items)} 个缺集季")
                        
                        # 2. Save new records to DB immediately
                        session = _store.session_factory()
                        try:
                            for item in items:
                                # item format: {id, name, season, totalEp, localEp, missing, poster}
                                record = MissingEpisode(
                                    id=item['id'],
                                    series_id=series_id,
                                    series_name=item['name'],
                                    season_number=item['season'],
                                    total_episodes=item['totalEp'],
                                    local_episodes=item['localEp'],
                                    missing_items=item['missing'],
                                    poster_path=item['poster']
                                )
                                session.merge(record)
                            session.commit()
                            logger.info(f"✓ 已保存 {series_name} 的 {len(items)} 条缺集记录")
                        except Exception as db_err:
                            session.rollback()
                            logger.error(f"✗ 保存 {series_name} 缺集记录失败: {db_err}")
                        finally:
                            session.close()
                    else:
                        logger.info(f"[{i+1}/{total}] {series_name} 无缺集")
                else:
                    logger.warning(f"[{i+1}/{total}] {series_name} 扫描失败: {result.get('error', '未知错误')}")
                        
            except Exception as e:
                logger.error(f"[{i+1}/{total}] {series_name} 扫描异常: {e}", exc_info=True)
            
            # Update progress AFTER scanning completes
            bg_service.update_progress(task, i + 1, total, f"已完成: {series_name}")
        
        logger.info(f"扫描完成: {scanned_count}/{total} 个剧集，发现 {len(all_missing)} 个缺集季")
        return {'missing': all_missing, 'total_series': total, 'scanned': scanned_count}
    
    bg_service.run_task(task, scan_job)
    
    return jsonify({
        'success': True,
        'message': '扫描已在后台启动',
        'task': task.to_dict()
    }), 200


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





@emby_bp.route('/bg-tasks/status', methods=['GET'])
@require_auth
def get_background_tasks_status():
    """Get status of all background tasks."""
    from services.background_tasks import get_background_service
    
    bg_service = get_background_service()
    task_type = request.args.get('type')
    
    if task_type:
        tasks = bg_service.get_running_tasks(task_type)
    else:
        tasks = bg_service.get_all_tasks()
    
    return jsonify({
        'success': True,
        'data': tasks
    }), 200


@emby_bp.route('/bg-tasks/<task_id>', methods=['GET'])
@require_auth
def get_background_task(task_id: str):
    """Get status of a specific background task."""
    from services.background_tasks import get_background_service
    
    bg_service = get_background_service()
    task = bg_service.get_task(task_id)
    
    if not task:
        return jsonify({
            'success': False,
            'error': 'Task not found'
        }), 404
    
    return jsonify({
        'success': True,
        'data': task.to_dict()
    }), 200


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
        proxy_conf = _emby_service._get_proxy_config() if _emby_service else None
        generator.set_emby_config(emby_url, api_key, proxies=proxy_conf)
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
        proxy_conf = _emby_service._get_proxy_config() if _emby_service else None
        generator.set_emby_config(emby_url, api_key, proxies=proxy_conf)
        
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
                sort_by = cover_config.get('sort')
                poster_count = int(cover_config.get('posterCount', 6))
                posters = generator.get_library_posters(lib_id, limit=poster_count, sort_by=sort_by)
                if not posters:
                    results.append({'id': lib_id, 'success': False, 'msg': '无海报'})
                    continue
                
                # 2. 准备参数
                title = target_lib['name']
                font_path = cover_config.get('fontPath')
                sticker_name = cover_config.get('sticker')
                
                sticker_img = None
                if sticker_name:
                    import os
                    from PIL import Image
                    data_dir = get_covers_data_dir()
                    sticker_path_full = os.path.join(data_dir, 'stickers', sticker_name)
                    if os.path.exists(sticker_path_full):
                        sticker_img = Image.open(sticker_path_full).convert("RGBA")
                
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
                    'v_align_pct': cover_config.get('vAlign', 60),
                    'font_path': font_path,
                    'sticker_img': sticker_img
                }
                
                # 3. 创建本地缓存目录 (使用跨平台路径)
                import os
                data_path = os.environ.get('DATA_PATH', os.path.join(os.path.dirname(__file__), '..', 'data'))
                data_dir = os.path.dirname(data_path) if data_path.endswith('.json') else data_path
                cache_dir = os.path.join(data_dir, 'covers', safe_lib_name)
                os.makedirs(cache_dir, exist_ok=True)
                
                # 4. 生成封面并保存到本地
                # APNG 格式使用 .png 扩展名
                file_ext = 'png'  # 静态和动态都使用 .png
                local_file_path = os.path.join(cache_dir, f"{safe_lib_name}.{file_ext}")
                content_type = 'image/png'
                
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
        sort_by = request.args.get('sort')
        
        generator = get_cover_generator()
        proxy_conf = _emby_service._get_proxy_config() if _emby_service else None
        generator.set_emby_config(emby_url, api_key, proxies=proxy_conf)
        posters = generator.get_library_posters(library_id, limit=limit, sort_by=sort_by)
        
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
        angle_scale = cover_config.get('angleScale') or data.get('angleScale', 1.0)
        use_backdrop = cover_config.get('useBackdrop') or data.get('useBackdrop', False)
        
        generator = get_cover_generator()
        
        if emby_url and api_key:
            proxy_conf = _emby_service._get_proxy_config() if _emby_service else None
            generator.set_emby_config(emby_url, api_key, proxies=proxy_conf)
            use_backdrop = data.get('useBackdrop', False)
        poster_count = int(data.get('posterCount', 5))
        poster_count = max(3, min(7, poster_count))
        sort_by = cover_config.get('sort') or data.get('sort')
        font_path = cover_config.get('fontPath') or data.get('fontPath')
        sticker_name = cover_config.get('sticker') or data.get('sticker')
        
        sticker_img = None
        if sticker_name:
            import os
            from PIL import Image
            data_dir = get_covers_data_dir()
            sticker_path_full = os.path.join(data_dir, 'stickers', sticker_name)
            if os.path.exists(sticker_path_full):
                try:
                    sticker_img = Image.open(sticker_path_full).convert("RGBA")
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Failed to load sticker {sticker_name}: {e}")
        
        # 获取海报
        posters = []
        if library_id:
            posters = generator.get_library_posters(library_id, limit=poster_count, sort_by=sort_by)
            
        # 获取背景图 (如果要用)
        backdrop_img = None
        if use_backdrop and library_id:
            backdrop_img = generator.get_library_backdrop(library_id)
        
        if not posters:
            return jsonify({'success': False, 'error': '未能获取海报图片'}), 400
        
        # 创建预览缓存目录 (使用跨平台路径)
        import os
        data_path = os.environ.get('DATA_PATH', os.path.join(os.path.dirname(__file__), '..', 'data'))
        data_dir = os.path.dirname(data_path) if data_path.endswith('.json') else data_path
        cache_dir = os.path.join(data_dir, 'covers', 'preview')
        os.makedirs(cache_dir, exist_ok=True)
        
        # 清理标题用于文件名
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_', '.') else '_' for c in title).strip() or 'cover'
        # 注意：动态封面现在使用 APNG 格式，文件后缀统一为 .png
        file_ext = 'png'  # 静态和动态都使用 .png
        local_file_path = os.path.join(cache_dir, f"{safe_title}.{file_ext}")
        
        # 生成封面
        if output_format.lower() == 'gif':
            # 生成动态 APNG (400x225 16:9)
            apng_data = generator.generate_animated_cover(
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
                spacing=spacing,
                angle_scale=angle_scale,
                use_backdrop=use_backdrop,
                backdrop_img=backdrop_img,
                font_path=font_path,
                sticker_img=sticker_img
            )
            # 保存到本地缓存
            with open(local_file_path, 'wb') as f:
                f.write(apng_data)
            result_b64 = generator.bytes_to_base64(apng_data, "image/png")
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
                spacing=spacing,
                angle_scale=angle_scale,
                use_backdrop=use_backdrop,
                backdrop_img=backdrop_img,
                font_path=font_path,
                sticker_img=sticker_img
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


@emby_bp.route('/cover/batch/start', methods=['POST'])
@require_auth
def start_cover_batch_background():
    """Start batch cover generation in background (survives page refresh)."""
    import logging
    from services.background_tasks import get_background_service
    from services.cover_generator import get_cover_generator
    
    logger = logging.getLogger(__name__)
    bg_service = get_background_service()
    
    # Check if batch is already running
    running = bg_service.get_running_tasks(task_type='cover_batch')
    if running:
        return jsonify({
            'success': False,
            'error': '封面批量生成正在进行中',
            'task': running[0]
        }), 200
    
    data = request.get_json() or {}
    library_ids = data.get('library_ids', [])
    config = data.get('config', {})
    
    if not library_ids:
        return jsonify({
            'success': False,
            'error': '请至少选择一个媒体库'
        }), 400
    
    if not _emby_service:
        return jsonify({
            'success': False,
            'error': 'Emby 服务未初始化'
        }), 500
    
    # Create background task
    task = bg_service.create_task('cover_batch', f'批量生成封面 ({len(library_ids)} 个库)')
    
    def batch_job(task):
        """Background job for batch cover generation."""
        generator = get_cover_generator()
        
        # Get Emby config
        full_config = _store.get_config() if _store else {}
        emby_config = full_config.get('emby', {})
        emby_url = emby_config.get('serverUrl', '').rstrip('/')
        api_key = emby_config.get('apiKey', '').strip()
        
        if emby_url and api_key:
            # Need to get proxy config here safely
            proxies = None
            try:
                # Re-instantiate service inside thread if needed, or query store
                # Since we have _store, let's just get config manually or use emby service if thread-safe
                # _emby_service is global.
                if _emby_service:
                    proxies = _emby_service._get_proxy_config()
            except:
                pass
            generator.set_emby_config(emby_url, api_key, proxies=proxies)
        
        total = len(library_ids)
        success_count = 0
        
        for i, lib_id in enumerate(library_ids):
            lib_name = lib_id  # Will be updated if we can fetch name
            
            try:
                # Get library info
                libs = generator.get_libraries()
                lib_info = next((l for l in libs if l.get('Id') == lib_id), None)
                if lib_info:
                    lib_name = lib_info.get('Name', lib_id)
                
                bg_service.update_progress(task, i + 1, total, lib_name)
                
                # Get posters
                poster_count = config.get('posterCount', 5)
                posters = generator.get_library_posters(lib_id, limit=poster_count)
                
                if not posters:
                    logger.warning(f"[封面生成] {lib_name}: 无海报，跳过")
                    continue
                
                # Generate cover
                title = lib_info.get('Name', '媒体库') if lib_info else '媒体库'
                subtitle = 'MEDIA COLLECTION'
                
                cover_img = generator.generate_cover(
                    posters=posters,
                    title=title,
                    subtitle=subtitle,
                    theme_index=config.get('theme', 0),
                    title_size=config.get('titleSize', 192),
                    offset_x=config.get('offsetX', 40),
                    poster_scale_pct=config.get('posterScale', 30),
                    v_align_pct=config.get('vAlign', 60),
                    spacing=config.get('spacing', 3.0),
                    angle_scale=config.get('angleScale', 1.0),
                    use_backdrop=config.get('useBackdrop', False),
                    backdrop_img=None
                )
                
                # Upload to Emby
                import io
                buffer = io.BytesIO()
                cover_img.save(buffer, format='PNG')
                image_data = buffer.getvalue()
                
                upload_result = generator.upload_cover(lib_id, image_data, "image/png")
                
                if upload_result:
                    logger.info(f"[封面生成] {lib_name}: 上传成功")
                    success_count += 1
                else:
                    logger.warning(f"[封面生成] {lib_name}: 上传失败")
                    
            except Exception as e:
                logger.error(f"[封面生成] {lib_name}: 错误 - {e}")
        
        return {'success_count': success_count, 'total': total}
    
    bg_service.run_task(task, batch_job)
    
    return jsonify({
        'success': True,
        'message': f'批量封面生成已在后台启动 ({len(library_ids)} 个库)',
        'task': task.to_dict()
    }), 200

@emby_bp.route('/cover/upload_rendered', methods=['POST'])
@require_auth
def upload_rendered_cover():
    """接收前端渲染好的图片，保存到本地并上传到 Emby"""
    try:
        if not _store:
            return jsonify({'success': False, 'error': '服务未初始化'}), 500
        
        # 1. 获取上传的文件和参数
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '未包含文件数据'}), 400
            
        file = request.files['file']
        library_id = request.form.get('libraryId')
        title = request.form.get('title', 'cover')
        
        if not library_id:
            return jsonify({'success': False, 'error': '未指定媒体库 ID'}), 400
            
        # 2. 准备配置
        config = _store.get_config()
        emby_config = config.get('emby', {})
        emby_url = emby_config.get('serverUrl', '')
        api_key = emby_config.get('apiKey', '')
        
        if not emby_url or not api_key:
            return jsonify({'success': False, 'error': '请先配置 Emby 服务器'}), 400
            
        generator = get_cover_generator()
        proxy_conf = _emby_service._get_proxy_config() if _emby_service else None
        generator.set_emby_config(emby_url, api_key, proxies=proxy_conf)
        
        # 3. 创建本地缓存目录 (data/covers/custom/[library_id])
        import os
        data_path = os.environ.get('DATA_PATH', os.path.join(os.path.dirname(__file__), '..', 'data'))
        data_dir = os.path.dirname(data_path) if data_path.endswith('.json') else data_path
        
        # 清理标题用于文件名
        safe_title = "".join(c if c.isalnum() or c in (' ', '-', '_', '.') else '_' for c in title).strip()
        cache_dir = os.path.join(data_dir, 'covers', 'studio_generated')
        os.makedirs(cache_dir, exist_ok=True)
        
        timestamp = __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_title}_{timestamp}.png"
        local_file_path = os.path.join(cache_dir, filename)
        
        # 4. 保存到本地
        # 读取二进制数据
        image_data = file.read()
        with open(local_file_path, 'wb') as f:
            f.write(image_data)
        
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Studio 封面已备份到本地: {local_file_path}")
        
        # 5. 上传到 Emby
        # 重置指针以上传
        # 或者直接使用 image_data
        
        if generator.upload_cover(library_id, image_data, "image/png"):
            # 6. 刷新 Emby 项目以清除缓存
            try:
                from services.emby_service import get_emby_service
                emby_service = get_emby_service(_store)
                if emby_service:
                    emby_service.refresh_item(library_id)
            except Exception as e:
                logger.warning(f"刷新库 {library_id} 缓存失败: {e}")
                
            return jsonify({
                'success': True,
                'message': '上传成功',
                'localPath': local_file_path
            }), 200
        else:
            return jsonify({'success': False, 'error': 'Emby 上传失败，但已保存到本地', 'localPath': local_file_path}), 500
            
    except Exception as e:
        import traceback
        logging.getLogger(__name__).error(f"处理 Studio 封面上传失败: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ 封面预设与定时任务 API ============

@emby_bp.route('/cover/sort-options', methods=['GET'])
@require_auth
def get_poster_sort_options():
    """获取海报排序选项列表"""
    try:
        from services.cover_scheduler import get_poster_sort_options
        return jsonify({
            'success': True,
            'data': get_poster_sort_options()
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/presets', methods=['GET'])
@require_auth
def get_cover_presets():
    """获取所有封面预设列表"""
    try:
        from services.cover_scheduler import get_cover_scheduler
        scheduler = get_cover_scheduler()
        scheduler.init(_store, get_cover_generator())
        return jsonify({
            'success': True,
            'data': scheduler.get_presets()
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/presets', methods=['POST'])
@require_auth
def create_cover_preset():
    """创建新的封面预设"""
    try:
        from services.cover_scheduler import get_cover_scheduler
        data = request.get_json() or {}
        name = data.get('name', '新预设')
        
        scheduler = get_cover_scheduler()
        scheduler.init(_store, get_cover_generator())
        
        preset = scheduler.add_preset(name, data)
        return jsonify({
            'success': True,
            'data': preset.to_dict()
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/presets/<preset_id>', methods=['GET'])
@require_auth
def get_cover_preset(preset_id: str):
    """获取指定预设"""
    try:
        from services.cover_scheduler import get_cover_scheduler
        scheduler = get_cover_scheduler()
        scheduler.init(_store, get_cover_generator())
        
        preset = scheduler.get_preset(preset_id)
        if preset:
            return jsonify({'success': True, 'data': preset}), 200
        else:
            return jsonify({'success': False, 'error': '预设不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/presets/<preset_id>', methods=['PUT'])
@require_auth
def update_cover_preset(preset_id: str):
    """更新封面预设"""
    try:
        from services.cover_scheduler import get_cover_scheduler
        data = request.get_json() or {}
        
        scheduler = get_cover_scheduler()
        scheduler.init(_store, get_cover_generator())
        
        preset = scheduler.update_preset(preset_id, data)
        if preset:
            return jsonify({'success': True, 'data': preset.to_dict()}), 200
        else:
            return jsonify({'success': False, 'error': '预设不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/presets/<preset_id>', methods=['DELETE'])
@require_auth
def delete_cover_preset(preset_id: str):
    """删除封面预设"""
    try:
        from services.cover_scheduler import get_cover_scheduler
        scheduler = get_cover_scheduler()
        scheduler.init(_store, get_cover_generator())
        
        if scheduler.delete_preset(preset_id):
            return jsonify({'success': True}), 200
        else:
            return jsonify({'success': False, 'error': '预设不存在'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/presets/<preset_id>/run', methods=['POST'])
@require_auth
def run_cover_preset(preset_id: str):
    """立即执行封面预设"""
    try:
        from services.cover_scheduler import get_cover_scheduler
        scheduler = get_cover_scheduler()
        scheduler.init(_store, get_cover_generator())
        
        result = scheduler.run_preset(preset_id)
        return jsonify(result), 200 if result.get('success') else 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/scheduler/status', methods=['GET'])
@require_auth
def get_scheduler_status():
    """获取调度器状态"""
    try:
        from services.cover_scheduler import get_cover_scheduler
        scheduler = get_cover_scheduler()
        scheduler.init(_store, get_cover_generator())
        
        presets = scheduler.get_presets()
        active_count = sum(1 for p in presets if p.get('scheduleInterval') != 'disabled')
        
        return jsonify({
            'success': True,
            'data': {
                'running': scheduler._running,
                'totalPresets': len(presets),
                'activeSchedules': active_count,
                'presets': presets
            }
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/scheduler/start', methods=['POST'])
@require_auth
def start_cover_scheduler():
    """启动封面定时调度"""
    try:
        from services.cover_scheduler import get_cover_scheduler
        scheduler = get_cover_scheduler()
        scheduler.init(_store, get_cover_generator())
        scheduler.start()
        
        return jsonify({'success': True, 'message': '调度器已启动'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emby_bp.route('/cover/scheduler/stop', methods=['POST'])
@require_auth
def stop_cover_scheduler():
    """停止封面定时调度"""
    try:
        from services.cover_scheduler import get_cover_scheduler
        scheduler = get_cover_scheduler()
        scheduler.stop()
        
        return jsonify({'success': True, 'message': '调度器已停止'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# --- Custom Assets (Fonts & Stickers) ---

def get_covers_data_dir():
    import os
    data_path = os.environ.get('DATA_PATH', os.path.join(os.path.dirname(__file__), '..', 'data'))
    data_dir = os.path.dirname(data_path) if data_path.endswith('.json') else data_path
    return data_dir

@emby_bp.route('/cover/upload_font', methods=['POST'])
@require_auth
def upload_cover_font():
    """上传本地字体文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '未提供文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '文件名为空'}), 400
        
        import os
        from werkzeug.utils import secure_filename
        
        data_dir = get_covers_data_dir()
        font_dir = os.path.join(data_dir, 'fonts')
        os.makedirs(font_dir, exist_ok=True)
        
        filename = secure_filename(file.filename)
        # Ensure it's a font file
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ['.ttf', '.otf', '.ttc']:
            return jsonify({'success': False, 'error': '不支持的字体格式'}), 400
            
        dest_path = os.path.join(font_dir, filename)
        file.save(dest_path)
        
        return jsonify({'success': True, 'data': {'filename': filename}}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@emby_bp.route('/cover/upload_sticker', methods=['POST'])
@require_auth
def upload_cover_sticker():
    """上传水印/贴纸图片"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '未提供文件'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '文件名为空'}), 400
        
        import os
        from werkzeug.utils import secure_filename
        
        data_dir = get_covers_data_dir()
        sticker_dir = os.path.join(data_dir, 'stickers')
        os.makedirs(sticker_dir, exist_ok=True)
        
        filename = secure_filename(file.filename)
        # Ensure it's an image
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ['.png', '.jpg', '.jpeg', '.webp', '.svg']:
             return jsonify({'success': False, 'error': '不支持的图片格式'}), 400
             
        dest_path = os.path.join(sticker_dir, filename)
        file.save(dest_path)
        
        return jsonify({'success': True, 'data': {'filename': filename}}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@emby_bp.route('/cover/assets', methods=['GET'])
@require_auth
def get_cover_assets():
    """获取已上传的字体和贴纸列表"""
    try:
        import os
        data_dir = get_covers_data_dir()
        
        font_dir = os.path.join(data_dir, 'fonts')
        sticker_dir = os.path.join(data_dir, 'stickers')
        
        fonts = []
        if os.path.exists(font_dir):
            fonts = [f for f in os.listdir(font_dir) if f.lower().endswith(('.ttf', '.otf', '.ttc'))]
            
        stickers = []
        if os.path.exists(sticker_dir):
            stickers = [f for f in os.listdir(sticker_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.svg'))]
            
        return jsonify({
            'success': True,
            'data': {
                'fonts': fonts,
                'stickers': stickers
            }
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@emby_bp.route('/cover/sticker/<filename>', methods=['GET'])
def get_cover_sticker(filename: str):
    """获取水印贴纸图片"""
    import os
    from flask import send_from_directory
    data_dir = get_covers_data_dir()
    sticker_dir = os.path.join(data_dir, 'stickers')
    return send_from_directory(sticker_dir, filename)

@emby_bp.route('/cover/font/<filename>', methods=['GET'])
def get_cover_font(filename: str):
    """获取自定义字体文件"""
    import os
    from flask import send_from_directory
    data_dir = get_covers_data_dir()
    font_dir = os.path.join(data_dir, 'fonts')
    return send_from_directory(font_dir, filename)
