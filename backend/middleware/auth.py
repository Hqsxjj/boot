from functools import wraps
from flask import jsonify, current_app
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError
import os


def require_auth(fn):
    """Decorator to require JWT authentication."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            identity = get_jwt_identity()
            if not identity:
                return jsonify({
                    'success': False,
                    'error': 'Invalid token'
                }), 401
            return fn(*args, **kwargs)
        except (NoAuthorizationError, InvalidHeaderError) as e:
            return jsonify({
                'success': False,
                'error': 'Missing or invalid authorization header'
            }), 401
        except Exception as e:
            return jsonify({
                'success': False,
                'error': 'Authentication failed'
            }), 401
    
    return wrapper


def optional_auth(fn):
    """Decorator for optional JWT authentication with dev mode support."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Check if ALLOW_UNAUTHENTICATED_CONFIG is enabled
        allow_unauth = os.environ.get('ALLOW_UNAUTHENTICATED_CONFIG', 'false').lower() == 'true'
        
        try:
            verify_jwt_in_request()
            identity = get_jwt_identity()
            if not identity:
                return jsonify({
                    'success': False,
                    'error': 'Invalid token'
                }), 401
            return fn(*args, **kwargs)
        except (NoAuthorizationError, InvalidHeaderError) as e:
            # If dev mode is enabled, allow without auth
            if allow_unauth:
                return fn(*args, **kwargs)
            return jsonify({
                'success': False,
                'error': 'Missing or invalid authorization header'
            }), 401
        except Exception as e:
            if allow_unauth:
                return fn(*args, **kwargs)
            return jsonify({
                'success': False,
                'error': 'Authentication failed'
            }), 401
    
    return wrapper
