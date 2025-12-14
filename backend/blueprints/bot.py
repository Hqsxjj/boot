from flask import Blueprint, request, jsonify
from middleware.auth import optional_auth, require_auth
from services.telegram_bot import TelegramBotService
from services.secret_store import SecretStore
from persistence.store import DataStore

bot_bp = Blueprint('bot', __name__, url_prefix='/api/bot')

# Global instances (set during initialization)
_bot_service = None


def init_bot_blueprint(secret_store: SecretStore, store: DataStore):
    """Initialize bot blueprint with required services."""
    global _bot_service
    _bot_service = TelegramBotService(secret_store)
    bot_bp.secret_store = secret_store
    bot_bp.store = store
    return bot_bp


@bot_bp.route('/config', methods=['GET'])
@optional_auth
def get_bot_config():
    """Get bot configuration from both config store and secret store."""
    try:
        # Get config from YAML (fallback values)
        config = bot_bp.store.get_config()
        telegram_config = config.get('telegram', {})
        
        # Override with real values from secret store if available
        if _bot_service:
            bot_token = _bot_service.get_bot_token()
            admin_user_id = _bot_service.get_admin_user_id()
            
            # Use stored values if available, fallback to config
            if bot_token:
                telegram_config['botToken'] = bot_token
            if admin_user_id:
                telegram_config['adminUserId'] = admin_user_id
        
        # Check if we have valid bot credentials
        has_valid_config = bool(
            telegram_config.get('botToken') and 
            telegram_config.get('adminUserId')
        )
        telegram_config['hasValidConfig'] = has_valid_config
        
        return jsonify({
            'success': True,
            'data': telegram_config
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to retrieve bot config: {str(e)}'
        }), 500


@bot_bp.route('/config', methods=['POST'])
@require_auth
def update_bot_config():
    """Update bot configuration in both config store and secret store."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Bot config data is required'
            }), 400
        
        # Validate required fields
        bot_token = data.get('botToken', '').strip()
        admin_user_id = data.get('adminUserId', '').strip()
        notification_channel_id = data.get('notificationChannelId', '').strip()
        whitelist_mode = data.get('whitelistMode', False)
        
        # Validate bot token if provided
        if bot_token and bot_token.strip():
            validation_result = _bot_service.validate_bot_token(bot_token)
            if not validation_result['valid']:
                return jsonify({
                    'success': False,
                    'error': f'Invalid bot token: {validation_result["error"]}'
                }), 400
        
        # Save credentials to secret store
        if bot_token or admin_user_id:
            if not _bot_service.save_bot_credentials(bot_token, admin_user_id):
                return jsonify({
                    'success': False,
                    'error': 'Failed to save bot credentials securely'
                }), 500
        
        # Save notification channel to secret store
        if notification_channel_id:
            _bot_service.save_notification_channel(notification_channel_id)
        
        # Update config in YAML store
        try:
            current_config = bot_bp.store.get_config()
            telegram_config = current_config.get('telegram', {})
            
            # Update fields that go in config (not secrets)
            if notification_channel_id:
                telegram_config['notificationChannelId'] = notification_channel_id
            telegram_config['whitelistMode'] = whitelist_mode
            
            # Always update the full config to ensure consistency
            current_config['telegram'] = telegram_config
            bot_bp.store.update_config(current_config)
            
        except Exception as e:
            # Don't fail the whole request if config update fails
            # The secrets are already saved
            pass
        
        # Return updated config
        return get_bot_config()
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to update bot config: {str(e)}'
        }), 500


@bot_bp.route('/commands', methods=['GET'])
@optional_auth
def get_bot_commands():
    """Get bot command definitions."""
    try:
        commands = _bot_service.get_commands()
        
        return jsonify({
            'success': True,
            'data': commands
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to retrieve bot commands: {str(e)}'
        }), 500


@bot_bp.route('/commands', methods=['PUT'])
@require_auth
def update_bot_commands():
    """Update bot command definitions."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Commands data is required'
            }), 400
        
        commands = data.get('commands', [])
        
        # Validate commands format
        if not isinstance(commands, list):
            return jsonify({
                'success': False,
                'error': 'Commands must be a list'
            }), 400
        
        for i, cmd in enumerate(commands):
            if not isinstance(cmd, dict) or not all(key in cmd for key in ['cmd', 'desc', 'example']):
                return jsonify({
                    'success': False,
                    'error': f'Invalid command format at index {i}. Each command must have cmd, desc, and example fields'
                }), 400
        
        # Save commands
        if not _bot_service.save_commands(commands):
            return jsonify({
                'success': False,
                'error': 'Failed to save commands'
            }), 500
        
        return jsonify({
            'success': True,
            'data': commands
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to update bot commands: {str(e)}'
        }), 500


@bot_bp.route('/test-message', methods=['POST'])
@require_auth
def send_test_message():
    """Send a test message to verify bot connectivity."""
    try:
        data = request.get_json() or {}
        target_type = data.get('target_type', 'admin')
        target_id = data.get('target_id')
        
        result = _bot_service.send_test_message(target_type, target_id)
        
        if result['success']:
            return jsonify({
                'success': True,
                'data': result['data']
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to send test message: {str(e)}'
        }), 500


# ==================== Webhook 相关端点 ====================

# 全局工作流服务实例
_workflow_service = None


def set_workflow_service(workflow_service):
    """设置工作流服务实例"""
    global _workflow_service
    _workflow_service = workflow_service


@bot_bp.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    处理 Telegram Webhook 回调
    接收用户发送的消息并处理
    """
    try:
        update = request.get_json()
        
        if not update:
            return jsonify({'ok': True}), 200
        
        # 处理普通消息
        if 'message' in update:
            message = update['message']
            chat_id = str(message.get('chat', {}).get('id', ''))
            user_id = str(message.get('from', {}).get('id', ''))
            text = message.get('text', '')
            
            if text and chat_id:
                _handle_user_message(chat_id, user_id, text)
        
        # 处理按钮回调
        elif 'callback_query' in update:
            callback = update['callback_query']
            callback_id = callback.get('id')
            chat_id = str(callback.get('message', {}).get('chat', {}).get('id', ''))
            message_id = callback.get('message', {}).get('message_id')
            user_id = str(callback.get('from', {}).get('id', ''))
            data = callback.get('data', '')
            
            _handle_callback_query(callback_id, chat_id, message_id, user_id, data)
        
        return jsonify({'ok': True}), 200
        
    except Exception as e:
        import logging
        logging.error(f"Webhook error: {e}")
        return jsonify({'ok': True}), 200  # 返回 200 避免 Telegram 重试


def _handle_user_message(chat_id: str, user_id: str, text: str):
    """处理用户消息"""
    global _workflow_service, _bot_service
    
    if not _bot_service:
        return
    
    # 处理命令消息
    if text.startswith('/'):
        _handle_command(chat_id, user_id, text)
        return
    
    # 处理链接（需要 workflow_service）
    if not _workflow_service:
        return
    
    result = _workflow_service.process_message(chat_id, user_id, text)
    
    if not result.get('success'):
        # 不是有效链接，忽略
        return
    
    if result.get('action') == 'choose':
        # 需要用户选择网盘
        _bot_service.send_cloud_choice(
            chat_id=chat_id,
            task_id=result['task_id'],
            link_info=result['link_info'],
            options=result['options']
        )
    else:
        # 直接执行成功
        _bot_service.send_message(
            chat_id=chat_id,
            text=f"✅ {result.get('message', '操作成功')}"
        )


def _handle_command(chat_id: str, user_id: str, text: str):
    """处理机器人命令"""
    global _bot_service, _workflow_service
    
    if not _bot_service:
        return
    
    # 解析命令和参数
    parts = text.split(maxsplit=1)
    command = parts[0].lower().split('@')[0]  # 移除 @botname 后缀
    args = parts[1] if len(parts) > 1 else ''
    
    # 命令处理映射
    if command == '/start':
        _cmd_start(chat_id, user_id)
    elif command == '/help':
        _cmd_help(chat_id, user_id)
    elif command == '/status':
        _cmd_status(chat_id, user_id)
    elif command == '/cancel':
        _cmd_cancel(chat_id, user_id, args)
    elif command == '/tasks':
        _cmd_tasks(chat_id, user_id)
    elif command == '/ping':
        _cmd_ping(chat_id, user_id)
    else:
        # 未知命令，发送帮助信息
        _bot_service.send_message(
            chat_id=chat_id,
            text="❓ 未知命令。发送 /help 查看可用命令。"
        )


def _cmd_start(chat_id: str, user_id: str):
    """处理 /start 命令"""
    welcome_msg = """
🎉 *欢迎使用 115/123 云盘机器人！*

我可以帮你：
• 接收分享链接并转存到网盘
• 接收离线下载链接（磁力/种子）
• 自动整理文件并生成 STRM
• 通知 Emby 刷新媒体库

📤 *使用方法*
直接发送分享链接或磁力链接给我即可！

_发送 /help 查看更多命令_
"""
    _bot_service.send_message(chat_id=chat_id, text=welcome_msg)


def _cmd_help(chat_id: str, user_id: str):
    """处理 /help 命令"""
    # 获取自定义命令列表
    commands = _bot_service.get_commands()
    
    help_msg = "📚 *可用命令*\n\n"
    for cmd in commands:
        help_msg += f"`{cmd['cmd']}` - {cmd['desc']}\n"
    
    help_msg += """
📤 *支持的链接*
• 115 分享链接
• 123 云盘分享链接
• 磁力链接 (magnet:)
• 种子文件 (直接发送)
"""
    _bot_service.send_message(chat_id=chat_id, text=help_msg)


def _cmd_status(chat_id: str, user_id: str):
    """处理 /status 命令 - 显示系统状态"""
    global _workflow_service
    
    status_msg = "📊 *系统状态*\n\n"
    
    # 检查各服务状态
    status_msg += "• 🤖 机器人: ✅ 运行中\n"
    
    if _workflow_service:
        status_msg += "• 🔄 工作流服务: ✅ 正常\n"
        
        # 获取待处理任务数
        pending_tasks = _workflow_service.get_pending_tasks(user_id)
        status_msg += f"• 📋 待处理任务: {len(pending_tasks)} 个\n"
        
        if _workflow_service.cloud115_service:
            status_msg += "• ☁️ 115 网盘: ✅ 已连接\n"
        else:
            status_msg += "• ☁️ 115 网盘: ❌ 未配置\n"
            
        if _workflow_service.cloud123_service:
            status_msg += "• ☁️ 123 云盘: ✅ 已连接\n"
        else:
            status_msg += "• ☁️ 123 云盘: ❌ 未配置\n"
    else:
        status_msg += "• 🔄 工作流服务: ⚠️ 未初始化\n"
    
    _bot_service.send_message(chat_id=chat_id, text=status_msg)


def _cmd_tasks(chat_id: str, user_id: str):
    """处理 /tasks 命令 - 显示待处理任务"""
    global _workflow_service
    
    if not _workflow_service:
        _bot_service.send_message(chat_id=chat_id, text="⚠️ 工作流服务未初始化")
        return
    
    pending_tasks = _workflow_service.get_pending_tasks(user_id)
    
    if not pending_tasks:
        _bot_service.send_message(chat_id=chat_id, text="📋 暂无待处理任务")
        return
    
    msg = f"📋 *待处理任务* ({len(pending_tasks)} 个)\n\n"
    for i, task in enumerate(pending_tasks[:10], 1):  # 最多显示10个
        task_dict = task.to_dict() if hasattr(task, 'to_dict') else task
        msg += f"{i}. `{task_dict.get('id', 'N/A')[:8]}...`\n"
        msg += f"   状态: {task_dict.get('status', 'unknown')}\n"
        if task_dict.get('error'):
            msg += f"   错误: {task_dict.get('error')}\n"
    
    if len(pending_tasks) > 10:
        msg += f"\n_...还有 {len(pending_tasks) - 10} 个任务_"
    
    _bot_service.send_message(chat_id=chat_id, text=msg)


def _cmd_cancel(chat_id: str, user_id: str, args: str):
    """处理 /cancel 命令 - 取消任务"""
    global _workflow_service
    
    if not _workflow_service:
        _bot_service.send_message(chat_id=chat_id, text="⚠️ 工作流服务未初始化")
        return
    
    if not args:
        # 取消所有待处理任务
        pending_tasks = _workflow_service.get_pending_tasks(user_id)
        if not pending_tasks:
            _bot_service.send_message(chat_id=chat_id, text="📋 暂无可取消的任务")
            return
        
        # 清理待处理任务（简单实现：标记为失败）
        cancelled_count = 0
        for task in pending_tasks:
            if hasattr(task, 'status'):
                task.status = 'cancelled'
                task.error = '用户取消'
                cancelled_count += 1
        
        _bot_service.send_message(
            chat_id=chat_id,
            text=f"✅ 已取消 {cancelled_count} 个任务"
        )
    else:
        # 取消指定任务
        task = _workflow_service.get_task(args.strip())
        if task:
            task.status = 'cancelled'
            task.error = '用户取消'
            _bot_service.send_message(chat_id=chat_id, text=f"✅ 已取消任务 `{args[:8]}...`")
        else:
            _bot_service.send_message(chat_id=chat_id, text=f"❌ 未找到任务 `{args}`")


def _cmd_ping(chat_id: str, user_id: str):
    """处理 /ping 命令 - 测试机器人响应"""
    import time
    _bot_service.send_message(
        chat_id=chat_id,
        text=f"🏓 Pong! 响应时间: {int(time.time() * 1000) % 1000}ms"
    )


def _handle_callback_query(callback_id: str, chat_id: str, message_id: int, user_id: str, data: str):
    """处理按钮回调"""
    global _workflow_service, _bot_service
    
    if not _workflow_service or not _bot_service:
        return
    
    # 解析回调数据
    # 格式: cloud_choice:task_id:target
    if data.startswith('cloud_choice:'):
        parts = data.split(':')
        if len(parts) >= 3:
            task_id = parts[1]
            target_cloud = parts[2]
            
            # 响应按钮点击
            _bot_service.answer_callback_query(
                callback_query_id=callback_id,
                text=f"正在处理，目标: {target_cloud} 网盘"
            )
            
            # 更新消息
            _bot_service.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⏳ 正在处理，目标网盘: {target_cloud}..."
            )
            
            # 执行工作流
            result = _workflow_service.execute_with_target(task_id, target_cloud)
            
            if result.get('success'):
                _bot_service.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"✅ {result.get('message', '任务已开始')}\n\n完成后将自动通知您。"
                )
            else:
                _bot_service.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ 失败: {result.get('error', '未知错误')}"
                )


@bot_bp.route('/webhook/set', methods=['POST'])
@require_auth
def set_webhook():
    """设置 Telegram Webhook URL"""
    try:
        data = request.get_json() or {}
        webhook_url = data.get('url', '').strip()
        
        if not webhook_url:
            return jsonify({
                'success': False,
                'error': 'Webhook URL is required'
            }), 400
        
        bot_token = _bot_service.get_bot_token()
        if not bot_token:
            return jsonify({
                'success': False,
                'error': 'Bot token not configured'
            }), 400
        
        import requests
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={'url': webhook_url},
            timeout=10
        )
        
        result = response.json()
        
        if result.get('ok'):
            return jsonify({
                'success': True,
                'data': {'webhook_url': webhook_url}
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('description', 'Failed to set webhook')
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bot_bp.route('/webhook/info', methods=['GET'])
@require_auth
def get_webhook_info():
    """获取当前 Webhook 信息"""
    try:
        bot_token = _bot_service.get_bot_token()
        if not bot_token:
            return jsonify({
                'success': False,
                'error': 'Bot token not configured'
            }), 400
        
        import requests
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getWebhookInfo",
            timeout=10
        )
        
        result = response.json()
        
        if result.get('ok'):
            return jsonify({
                'success': True,
                'data': result.get('result', {})
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('description', 'Failed to get webhook info')
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bot_bp.route('/process-link', methods=['POST'])
@require_auth
def process_link_api():
    """
    手动处理链接（用于测试或 API 调用）
    """
    try:
        if not _workflow_service:
            return jsonify({
                'success': False,
                'error': 'Workflow service not initialized'
            }), 500
        
        data = request.get_json() or {}
        text = data.get('text', '').strip()
        chat_id = data.get('chat_id', 'api')
        user_id = data.get('user_id', 'api')
        
        if not text:
            return jsonify({
                'success': False,
                'error': 'Text is required'
            }), 400
        
        result = _workflow_service.process_message(chat_id, user_id, text)
        
        return jsonify(result), 200 if result.get('success') else 400
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bot_bp.route('/execute-task', methods=['POST'])
@require_auth
def execute_task_api():
    """
    执行工作流任务（选择网盘后）
    """
    try:
        if not _workflow_service:
            return jsonify({
                'success': False,
                'error': 'Workflow service not initialized'
            }), 500
        
        data = request.get_json() or {}
        task_id = data.get('task_id', '').strip()
        target_cloud = data.get('target_cloud', '').strip()
        
        if not task_id or not target_cloud:
            return jsonify({
                'success': False,
                'error': 'task_id and target_cloud are required'
            }), 400
        
        result = _workflow_service.execute_with_target(task_id, target_cloud)
        
        return jsonify(result), 200 if result.get('success') else 400
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500