from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask_jwt_extended.exceptions import NoAuthorizationError, InvalidHeaderError


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
    
    return wrapper
