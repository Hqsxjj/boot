import json
import logging
import requests
from typing import Dict, Any, Optional, List
from services.secret_store import SecretStore

logger = logging.getLogger(__name__)


class TelegramBotService:
    """Service for managing Telegram bot operations and configuration."""
    
    def __init__(self, secret_store: SecretStore):
        """
        Initialize TelegramBotService.
        
        Args:
            secret_store: SecretStore instance for storing bot credentials
        """
        self.secret_store = secret_store
    
    def validate_bot_token(self, bot_token: str) -> Dict[str, Any]:
        """
        Validate a bot token by calling Telegram's getMe API.
        
        Args:
            bot_token: The bot token to validate
            
        Returns:
            Dict with 'valid' (bool) and 'data' or 'error' keys
        """
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return {
                        'valid': True,
                        'data': data.get('result', {})
                    }
                else:
                    return {
                        'valid': False,
                        'error': data.get('description', 'Unknown Telegram API error')
                    }
            else:
                return {
                    'valid': False,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
        except requests.exceptions.Timeout:
            return {
                'valid': False,
                'error': 'Request to Telegram API timed out'
            }
        except requests.exceptions.RequestException as e:
            return {
                'valid': False,
                'error': f'Failed to connect to Telegram API: {str(e)}'
            }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def save_bot_credentials(self, bot_token: str, admin_user_id: str) -> bool:
        """
        Save bot credentials to encrypted secret store.
        
        Args:
            bot_token: The bot token to store
            admin_user_id: The admin user ID to store
            
        Returns:
            bool indicating success
        """
        try:
            # Store bot token
            if not self.secret_store.set_secret('telegram_bot_token', bot_token):
                return False
                
            # Store admin user ID  
            if not self.secret_store.set_secret('telegram_admin_user_id', admin_user_id):
                return False
                
            return True
        except Exception as e:
            logger.error(f'Failed to save bot credentials: {str(e)}')
            return False
    
    def get_bot_token(self) -> Optional[str]:
        """Get stored bot token from secret store."""
        return self.secret_store.get_secret('telegram_bot_token')
    
    def get_admin_user_id(self) -> Optional[str]:
        """Get stored admin user ID from secret store."""
        return self.secret_store.get_secret('telegram_admin_user_id')
    
    def get_notification_channel(self) -> Optional[str]:
        """Get stored notification channel ID from secret store."""
        return self.secret_store.get_secret('telegram_notification_channel')
    
    def save_notification_channel(self, channel_id: str) -> bool:
        """Save notification channel ID to secret store."""
        try:
            return self.secret_store.set_secret('telegram_notification_channel', channel_id)
        except Exception as e:
            logger.error(f'Failed to save notification channel: {str(e)}')
            return False
    
    def send_test_message(self, target_type: str = 'admin', target_id: str = None) -> Dict[str, Any]:
        """
        Send a test message to verify bot connectivity.
        
        Args:
            target_type: 'admin' or 'channel'
            target_id: Target ID (if not using stored values)
            
        Returns:
            Dict with 'success' (bool) and 'data' or 'error'
        """
        try:
            bot_token = self.get_bot_token()
            if not bot_token:
                return {
                    'success': False,
                    'error': 'Bot token not configured'
                }
            
            # Determine target
            if target_type == 'admin':
                if target_id:
                    chat_id = target_id
                else:
                    chat_id = self.get_admin_user_id()
                    if not chat_id:
                        return {
                            'success': False,
                            'error': 'Admin user ID not configured'
                        }
            elif target_type == 'channel':
                if not target_id:
                    return {
                        'success': False,
                        'error': 'Channel ID is required for channel messages'
                    }
                chat_id = target_id
            else:
                return {
                    'success': False,
                    'error': 'Invalid target type. Use "admin" or "channel"'
                }
            
            # Send test message
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': '🤖 Bot连接测试\n\n如果收到此消息，说明机器人配置正确！\n\n时间: ' + str(__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    return {
                        'success': True,
                        'data': {
                            'message_id': data['result']['message_id'],
                            'chat_id': chat_id,
                            'text': 'Test message sent successfully'
                        }
                    }
                else:
                    return {
                        'success': False,
                        'error': data.get('description', 'Failed to send message')
                    }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}: {response.text}'
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request to Telegram API timed out'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'Failed to connect to Telegram API: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def get_default_commands(self) -> List[Dict[str, str]]:
        """
        Get default bot command definitions.
        
        Returns:
            List of command dictionaries with 'cmd', 'desc', 'example' keys
        """
        return [
            {'cmd': '/start', 'desc': '初始化机器人并检查 115 账号连接状态', 'example': '/start'},
            {'cmd': '/magnet', 'desc': '添加磁力/Ed2k/HTTP 链接离线任务 (115)', 'example': '/magnet magnet:?xt=urn:btih:...'},
            {'cmd': '/123_offline', 'desc': '添加 123 云盘离线下载任务', 'example': '/123_offline http://example.com/file.mp4'},
            {'cmd': '/link', 'desc': '转存 115 分享链接 (支持加密)', 'example': '/link https://115.com/s/...'},
            {'cmd': '/rename', 'desc': '使用 TMDB 手动重命名指定文件/文件夹', 'example': '/rename <file_id> <tmdb_id>'},
            {'cmd': '/organize', 'desc': '对 115 默认目录执行自动分类整理', 'example': '/organize'},
            {'cmd': '/123_organize', 'desc': '对 123 云盘目录执行自动分类整理', 'example': '/123_organize'},
            {'cmd': '/dir', 'desc': '设置或查看当前默认下载文件夹 (CID)', 'example': '/dir 29384812'},
            {'cmd': '/quota', 'desc': '查看 115 账号离线配额和空间使用情况', 'example': '/quota'},
            {'cmd': '/tasks', 'desc': '查看当前正在进行的离线任务列表', 'example': '/tasks'},
        ]
    
    def save_commands(self, commands: List[Dict[str, str]]) -> bool:
        """
        Save custom bot command definitions.
        
        Args:
            commands: List of command dictionaries
            
        Returns:
            bool indicating success
        """
        try:
            # Validate commands format
            for cmd in commands:
                if not all(key in cmd for key in ['cmd', 'desc', 'example']):
                    return False
            
            commands_json = json.dumps(commands)
            return self.secret_store.set_secret('telegram_bot_commands', commands_json)
        except Exception as e:
            logger.error(f'Failed to save bot commands: {str(e)}')
            return False
    
    def get_commands(self) -> List[Dict[str, str]]:
        """
        Get saved bot command definitions or default if none saved.
        
        Returns:
            List of command dictionaries
        """
        try:
            commands_json = self.secret_store.get_secret('telegram_bot_commands')
            if commands_json:
                return json.loads(commands_json)
            else:
                return self.get_default_commands()
        except Exception as e:
            logger.warning(f'Failed to load saved commands, using defaults: {str(e)}')
            return self.get_default_commands()
    
    def send_message(self, chat_id: str, text: str, parse_mode: str = 'Markdown') -> Dict[str, Any]:
        """
        发送文本消息
        
        Args:
            chat_id: 目标聊天ID
            text: 消息文本
            parse_mode: 解析模式
        """
        try:
            bot_token = self.get_bot_token()
            if not bot_token:
                return {'success': False, 'error': 'Bot token not configured'}
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if data.get('ok'):
                return {'success': True, 'message_id': data['result']['message_id']}
            else:
                return {'success': False, 'error': data.get('description', 'Send failed')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def send_choice_buttons(
        self, 
        chat_id: str, 
        text: str, 
        options: List[Dict[str, str]],
        callback_prefix: str = 'choice'
    ) -> Dict[str, Any]:
        """
        发送带选择按钮的消息
        
        Args:
            chat_id: 目标聊天ID
            text: 消息文本
            options: 选项列表 [{'text': '显示文本', 'data': '回调数据'}, ...]
            callback_prefix: 回调前缀
        """
        try:
            bot_token = self.get_bot_token()
            if not bot_token:
                return {'success': False, 'error': 'Bot token not configured'}
            
            # 构建 inline keyboard
            keyboard = []
            row = []
            for opt in options:
                row.append({
                    'text': opt['text'],
                    'callback_data': f"{callback_prefix}:{opt['data']}"
                })
            keyboard.append(row)
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': text,
                'parse_mode': 'Markdown',
                'reply_markup': {
                    'inline_keyboard': keyboard
                }
            }
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if data.get('ok'):
                return {
                    'success': True, 
                    'message_id': data['result']['message_id']
                }
            else:
                return {'success': False, 'error': data.get('description', 'Send failed')}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def send_cloud_choice(
        self, 
        chat_id: str, 
        task_id: str,
        link_info: str,
        options: List[str]
    ) -> Dict[str, Any]:
        """
        发送网盘选择按钮
        
        Args:
            chat_id: 聊天ID
            task_id: 工作流任务ID
            link_info: 链接描述
            options: 可选网盘列表 ['115', '123']
        """
        text = f"🔗 {link_info}\n\n请选择目标网盘："
        
        button_options = []
        for opt in options:
            if opt == '115':
                button_options.append({'text': '📦 115 网盘', 'data': f'{task_id}:115'})
            elif opt == '123':
                button_options.append({'text': '☁️ 123 云盘', 'data': f'{task_id}:123'})
        
        return self.send_choice_buttons(
            chat_id=chat_id,
            text=text,
            options=button_options,
            callback_prefix='cloud_choice'
        )
    
    def send_photo_with_caption(
        self, 
        chat_id: str, 
        photo_url: str, 
        caption: str,
        parse_mode: str = 'Markdown'
    ) -> Dict[str, Any]:
        """
        发送带说明文字的图片（用于发送海报通知）
        
        Args:
            chat_id: 目标聊天ID
            photo_url: 图片URL
            caption: 说明文字
            parse_mode: 解析模式
        """
        try:
            bot_token = self.get_bot_token()
            if not bot_token:
                return {'success': False, 'error': 'Bot token not configured'}
            
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            payload = {
                'chat_id': chat_id,
                'photo': photo_url,
                'caption': caption[:1024],  # Telegram caption 限制 1024 字符
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=30)
            data = response.json()
            
            if data.get('ok'):
                return {
                    'success': True, 
                    'message_id': data['result']['message_id']
                }
            else:
                # 图片发送失败时回退到纯文本
                logger.warning(f"Photo send failed: {data.get('description')}, falling back to text")
                return self.send_message(chat_id, f"🎬 {caption}")
        except Exception as e:
            logger.error(f"Send photo error: {e}")
            return self.send_message(chat_id, f"🎬 {caption}")
    
    def answer_callback_query(
        self, 
        callback_query_id: str, 
        text: str = None,
        show_alert: bool = False
    ) -> Dict[str, Any]:
        """
        响应回调查询（用户点击按钮后的反馈）
        
        Args:
            callback_query_id: 回调查询ID
            text: 提示文本
            show_alert: 是否显示弹窗
        """
        try:
            bot_token = self.get_bot_token()
            if not bot_token:
                return {'success': False, 'error': 'Bot token not configured'}
            
            url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
            payload = {
                'callback_query_id': callback_query_id,
                'show_alert': show_alert
            }
            if text:
                payload['text'] = text
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            return {'success': data.get('ok', False)}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def edit_message_text(
        self, 
        chat_id: str, 
        message_id: int, 
        text: str,
        parse_mode: str = 'Markdown'
    ) -> Dict[str, Any]:
        """
        编辑已发送的消息
        
        Args:
            chat_id: 聊天ID
            message_id: 消息ID
            text: 新文本
        """
        try:
            bot_token = self.get_bot_token()
            if not bot_token:
                return {'success': False, 'error': 'Bot token not configured'}
            
            url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
            payload = {
                'chat_id': chat_id,
                'message_id': message_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            return {'success': data.get('ok', False)}
        except Exception as e:
            return {'success': False, 'error': str(e)}