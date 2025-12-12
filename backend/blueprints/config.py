from flask import Blueprint, request, jsonify
from middleware.auth import optional_auth
from persistence.store import DataStore
from services.secret_store import SecretStore
import json

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
    
    # Check if we have valid 123 token or cookies
    token_json = secret_store.get_secret('cloud123_token')
    cookies_123_json = secret_store.get_secret('cloud123_cookies')
    config['cloud123']['hasValidSession'] = bool(token_json or cookies_123_json)
    
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


@config_bp.route('/config', methods=['GET'])
@optional_auth
def get_config():
    """Get full application configuration without masking."""
    try:
        config = config_bp.store.get_config()

        # Bootstrap SecretStore from persisted config for frontend compatibility
        if config_bp.secret_store and not config_bp.secret_store.get_secret('cloud115_cookies'):
            cloud115 = config.get('cloud115') if isinstance(config, dict) else None
            if isinstance(cloud115, dict) and isinstance(cloud115.get('cookies'), str) and cloud115.get('cookies').strip():
                _sync_cloud115_cookies_from_config(config, config_bp.secret_store)
        
        # Add session health flags
        config = _add_session_flags(config, config_bp.secret_store)
        
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
        # Update config in store (no masking, full round-trip)
        config_bp.store.update_config(data)

        # Sync 115 cookies from the config payload into SecretStore for real /api/115 usage
        _sync_cloud115_cookies_from_config(data, config_bp.secret_store)
        
        # Return updated config with session flags
        updated_config = config_bp.store.get_config()
        updated_config = _add_session_flags(updated_config, config_bp.secret_store)
        
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
