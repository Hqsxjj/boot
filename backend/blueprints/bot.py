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