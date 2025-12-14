from flask import Blueprint, request, jsonify
from middleware.auth import optional_auth
from persistence.store import DataStore
from services.secret_store import SecretStore
import json
import copy

config_bp = Blueprint('config', __name__, url_prefix='/api')


def init_config_blueprint(store: DataStore, secret_store: SecretStore = None):
    """Initialize config blueprint with data store and secret store."""
    config_bp.store = store
    config_bp.secret_store = secret_store
    return config_bp


def _add_session_flags(config: dict, secret_store: SecretStore) -> dict:
    """Add session health flags to config."""
    if not secret_store:
        config['cloud115']['hasValidSession'] = False
        config['cloud123']['hasValidSession'] = False
        return config
    
    # Check if we have valid 115 cookies
    cookies_json = secret_store.get_secret('cloud115_cookies')
    config['cloud115']['hasValidSession'] = bool(cookies_json)
    
    # Check if we have valid 123 token, cookies, or OAuth credentials
    token_json = secret_store.get_secret('cloud123_token')
    cookies_123_json = secret_store.get_secret('cloud123_cookies')
    oauth_credentials = secret_store.get_secret('cloud123_oauth_credentials')
    config['cloud123']['hasValidSession'] = bool(token_json or cookies_123_json or oauth_credentials)
    
    return config


def _parse_cookie_string(cookie_str: str) -> dict:
    cookies = {}
    for part in cookie_str.split(';'):
        part = part.strip()
        if not part or '=' not in part:
            continue
        key, value = part.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key:
            cookies[key] = value
    return cookies


def _sync_cloud115_cookies_from_config(payload: dict, secret_store: SecretStore | None) -> None:
    if not secret_store or not isinstance(payload, dict):
        return

    cloud115 = payload.get('cloud115')
    if not isinstance(cloud115, dict):
        return

    cookies_value = cloud115.get('cookies')
    if not isinstance(cookies_value, str):
        return

    cookies_str = cookies_value.strip()

    if not cookies_str:
        secret_store.delete_secret('cloud115_cookies')
        secret_store.delete_secret('cloud115_session_metadata')
        return

    parsed = _parse_cookie_string(cookies_str)
    if not parsed:
        return

    secret_store.set_secret('cloud115_cookies', json.dumps(parsed))
    metadata = {
        'login_method': 'manual_import',
        'login_app': cloud115.get('loginApp', 'web'),
        'logged_in_at': __import__('datetime').datetime.now().isoformat(),
    }
    secret_store.set_secret('cloud115_session_metadata', json.dumps(metadata))


def _sync_cloud123_credentials_from_config(payload: dict, secret_store: SecretStore | None) -> None:
    """同步123云盘OAuth凭证到SecretStore"""
    if not secret_store or not isinstance(payload, dict):
        return

    cloud123 = payload.get('cloud123')
    if not isinstance(cloud123, dict):
        return

    client_id = cloud123.get('clientId', '').strip()
    client_secret = cloud123.get('clientSecret', '').strip()

    if not client_id or not client_secret:
        # 如果凭证被清空，删除存储的token
        return

    # 存储OAuth凭证
    credentials = {
        'clientId': client_id,
        'clientSecret': client_secret
    }
    secret_store.set_secret('cloud123_oauth_credentials', json.dumps(credentials))
    
    # 存储元数据
    metadata = {
        'login_method': 'oauth',
        'logged_in_at': __import__('datetime').datetime.now().isoformat()
    }
    secret_store.set_secret('cloud123_session_metadata', json.dumps(metadata))


def _sync_ai_credentials_from_config(payload: dict, secret_store: SecretStore | None) -> None:
    """同步 AI (LLM) 凭证到 SecretStore"""
    if not secret_store or not isinstance(payload, dict):
        return

    organize = payload.get('organize')
    if not isinstance(organize, dict):
        return
        
    ai = organize.get('ai')
    if not isinstance(ai, dict):
        return

    api_key = ai.get('apiKey', '').strip()
    
    # 如果 apiKey 存在且不是占位符，则更新
    # 注意：update_config 会先还原 mask，所以这里拿到的应该是明文
    if api_key and api_key != MASK_PLACEHOLDER:
        secret_store.set_secret('llm_api_key', api_key)
    
    # 同步其他非敏感字段
    if 'baseUrl' in ai:
        secret_store.set_secret('llm_base_url', ai.get('baseUrl', ''))
    if 'model' in ai:
        secret_store.set_secret('llm_model', ai.get('model', ''))
    if 'provider' in ai:
        secret_store.set_secret('llm_provider', ai.get('provider', ''))


# 定义敏感字段路径列表
SENSITIVE_FIELDS = [
    ['cloud115', 'cookies'],
    ['cloud123', 'clientSecret'],
    ['openList', 'password'],
    ['tmdb', 'apiKey'],
    ['telegram', 'botToken'],
    ['emby', 'apiKey'],
    ['proxy', 'password'],
    ['organize', 'ai', 'apiKey'],
]

MASK_PLACEHOLDER = '__MASKED__'

def _mask_sensitive_data(config: dict) -> dict:
    """Mask sensitive data in config dict."""
    masked = copy.deepcopy(config)
    
    for path in SENSITIVE_FIELDS:
        target = masked
        for key in path[:-1]:
            if isinstance(target, dict):
                target = target.get(key)
            else:
                target = None
                break
        
        if isinstance(target, dict) and path[-1] in target:
            val = target[path[-1]]
            if val and isinstance(val, str) and val.strip():
                target[path[-1]] = MASK_PLACEHOLDER
                
    return masked

def _unmask_sensitive_data(new_config: dict, old_config: dict) -> dict:
    """Restore masked data from old config."""
    restored = copy.deepcopy(new_config)
    
    for path in SENSITIVE_FIELDS:
        # 获取新配置中的值
        new_target = restored
        for key in path[:-1]:
            if isinstance(new_target, dict):
                new_target = new_target.get(key)
            else:
                new_target = None
                break
        
        # 获取旧配置中的值
        old_target = old_config
        for key in path[:-1]:
            if isinstance(old_target, dict):
                old_target = old_target.get(key)
            else:
                old_target = None
                break
                
        # 如果新值是占位符，且旧值存在，则恢复旧值
        if (isinstance(new_target, dict) and path[-1] in new_target and 
            new_target[path[-1]] == MASK_PLACEHOLDER):
            
            if (isinstance(old_target, dict) and path[-1] in old_target):
                new_target[path[-1]] = old_target[path[-1]]
            else:
                # 如果旧值不存在（奇怪的情况），则设为空或者保持原样
                new_target[path[-1]] = ''
                
    return restored


@config_bp.route('/config', methods=['GET'])
@optional_auth
def get_config():
    """Get application configuration with optional masking."""
    try:
        config = config_bp.store.get_config()

        # Bootstrap SecretStore from persisted config for frontend compatibility
        if config_bp.secret_store:
            # 同步115 cookies
            if not config_bp.secret_store.get_secret('cloud115_cookies'):
                cloud115 = config.get('cloud115') if isinstance(config, dict) else None
                if isinstance(cloud115, dict) and isinstance(cloud115.get('cookies'), str) and cloud115.get('cookies').strip():
                    _sync_cloud115_cookies_from_config(config, config_bp.secret_store)
            
            # 同步123云盘凭证
            if not config_bp.secret_store.get_secret('cloud123_oauth_credentials'):
                cloud123 = config.get('cloud123') if isinstance(config, dict) else None
                if isinstance(cloud123, dict):
                    client_id = cloud123.get('clientId', '').strip() if isinstance(cloud123.get('clientId'), str) else ''
                    client_secret = cloud123.get('clientSecret', '').strip() if isinstance(cloud123.get('clientSecret'), str) else ''
                    if client_id and client_secret:
                        _sync_cloud123_credentials_from_config(config, config_bp.secret_store)
            
            # 同步 AI 凭证
            if not config_bp.secret_store.get_secret('llm_api_key'):
                 _sync_ai_credentials_from_config(config, config_bp.secret_store)
        
        # Add session health flags
        config = _add_session_flags(config, config_bp.secret_store)
        
        # Mask sensitive data if 2FA is enabled (detected by presence of secret)
        if config.get('twoFactorSecret'):
            config = _mask_sensitive_data(config)
        
        return jsonify({
            'success': True,
            'data': config
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to retrieve config: {str(e)}'
        }), 500


@config_bp.route('/config', methods=['PUT', 'POST'])
@optional_auth
def update_config():
    """Update application configuration. Supports both PUT and POST methods."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Config data is required'
        }), 400
    
    try:
        # 获取当前配置用于恢复被 mask 的数据
        current_config = config_bp.store.get_config()
        
        # 如果新配置中有 masked 数据，尝试还原
        final_config = _unmask_sensitive_data(data, current_config)
        
        # Update config in store (no masking, full round-trip)
        config_bp.store.update_config(final_config)

        # Sync 115 cookies from the config payload into SecretStore for real /api/115 usage
        _sync_cloud115_cookies_from_config(final_config, config_bp.secret_store)
        
        # Sync 123 cloud OAuth credentials into SecretStore
        _sync_cloud123_credentials_from_config(final_config, config_bp.secret_store)
        
        # Sync AI credentials
        _sync_ai_credentials_from_config(final_config, config_bp.secret_store)
        
        # Return updated config with session flags
        updated_config = config_bp.store.get_config()
        updated_config = _add_session_flags(updated_config, config_bp.secret_store)
        
        # Mask responsive data if needed
        if updated_config.get('twoFactorSecret'):
            updated_config = _mask_sensitive_data(updated_config)
        
        return jsonify({
            'success': True,
            'data': updated_config
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to update config: {str(e)}'
        }), 500


@config_bp.route('/me', methods=['GET'])
@optional_auth
def get_me():
    """Get current user information (alternative endpoint)."""
    from flask_jwt_extended import get_jwt_identity
    
    try:
        username = get_jwt_identity()
        if not username:
            username = 'admin'  # Default in dev mode
    except:
        username = 'admin'  # Default in dev mode
    
    two_factor_enabled = config_bp.store.is_two_factor_enabled()
    
    return jsonify({
        'success': True,
        'data': {
            'username': username,
            'twoFactorEnabled': two_factor_enabled
        }
    }), 200


@config_bp.route('/user/summary', methods=['GET'])
def user_summary():
    """Frontend compatibility alias for auth status."""
    from blueprints.auth import status as auth_status

    return auth_status()
