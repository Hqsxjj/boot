from flask import Blueprint, request, jsonify
from middleware.auth import optional_auth
from persistence.store import DataStore
from services.secret_store import SecretStore

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
        return config
    
    # Check if we have valid 115 cookies
    cookies_json = secret_store.get_secret('cloud115_cookies')
    config['cloud115']['hasValidSession'] = bool(cookies_json)
    
    return config


@config_bp.route('/config', methods=['GET'])
@optional_auth
def get_config():
    """Get full application configuration without masking."""
    try:
        config = config_bp.store.get_config()
        
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
