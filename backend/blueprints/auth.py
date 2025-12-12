import os
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, get_jwt_identity, get_jwt, verify_jwt_in_request
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp

from middleware.auth import require_auth
from persistence.store import DataStore

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


def init_auth_blueprint(store: DataStore):
    """Initialize auth blueprint with data store."""
    auth_bp.store = store
    auth_bp.failed_attempts_by_client = {}
    auth_bp.max_failed_attempts = int(os.environ.get('AUTH_MAX_FAILED_ATTEMPTS', '5'))
    return auth_bp


def _get_client_key() -> str:
    return request.remote_addr or 'unknown'


def _get_failed_attempts(client_key: str) -> int:
    return int(auth_bp.failed_attempts_by_client.get(client_key, 0))


def _is_locked(client_key: str) -> bool:
    return _get_failed_attempts(client_key) >= auth_bp.max_failed_attempts


def _reset_attempts(client_key: str):
    auth_bp.failed_attempts_by_client.pop(client_key, None)


def _increment_attempts(client_key: str) -> int:
    next_val = _get_failed_attempts(client_key) + 1
    auth_bp.failed_attempts_by_client[client_key] = next_val
    return next_val


def _build_auth_state(is_authenticated: bool, is_2fa_verified: bool, client_key: str, include_secret: bool = False):
    data = {
        'isAuthenticated': bool(is_authenticated),
        'is2FAVerified': bool(is_2fa_verified),
        'isLocked': _is_locked(client_key),
        'failedAttempts': _get_failed_attempts(client_key)
    }

    if include_secret and auth_bp.store.is_two_factor_enabled():
        data['twoFactorSecret'] = auth_bp.store.get_two_factor_secret()

    return data


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login endpoint - validates username/password and returns JWT."""
    client_key = _get_client_key()

    if _is_locked(client_key):
        return jsonify({
            'success': False,
            'error': 'Account locked',
            'data': _build_auth_state(False, False, client_key)
        }), 423

    data = request.get_json()

    if not data or 'username' not in data or 'password' not in data:
        return jsonify({
            'success': False,
            'error': 'Username and password are required'
        }), 400

    username = data['username']
    password = data['password']

    # Get admin credentials from store
    admin = auth_bp.store.get_admin_credentials()

    # If no password is set yet, set it on first login
    if not admin.get('password_hash'):
        password_hash = generate_password_hash(password)
        auth_bp.store.update_admin_password(password_hash)
        _reset_attempts(client_key)

        # Create access token
        access_token = create_access_token(identity=username)

        return jsonify({
            'success': True,
            'data': {
                'token': access_token,
                'username': username,
                'requires2FA': False
            }
        }), 200

    # Check username and password
    if username != admin.get('username') or not check_password_hash(admin.get('password_hash'), password):
        _increment_attempts(client_key)
        return jsonify({
            'success': False,
            'error': 'Invalid credentials'
        }), 401

    # Successful login resets failed attempts
    _reset_attempts(client_key)

    # Check if 2FA is enabled
    requires_2fa = auth_bp.store.is_two_factor_enabled()

    # Create access token
    access_token = create_access_token(identity=username)

    return jsonify({
        'success': True,
        'data': {
            'token': access_token,
            'username': username,
            'requires2FA': requires_2fa
        }
    }), 200


@auth_bp.route('/verify-otp', methods=['POST'])
@require_auth
def verify_otp():
    """Verify OTP code for 2FA."""
    data = request.get_json()
    
    if not data or 'code' not in data:
        return jsonify({
            'success': False,
            'error': 'OTP code is required'
        }), 400
    
    code = data['code']
    
    # Get 2FA secret
    secret = auth_bp.store.get_two_factor_secret()
    
    if not secret:
        return jsonify({
            'success': False,
            'error': '2FA is not enabled'
        }), 400
    
    # Verify OTP
    totp = pyotp.TOTP(secret)
    is_valid = totp.verify(code, valid_window=1)
    
    if not is_valid:
        return jsonify({
            'success': False,
            'error': 'Invalid OTP code'
        }), 401

    # Mark current token as 2FA-verified
    try:
        jti = get_jwt().get('jti')
        if jti:
            current_app.two_fa_verified_jti.add(jti)
    except Exception:
        pass

    return jsonify({
        'success': True,
        'data': {
            'verified': True
        }
    }), 200


@auth_bp.route('/me', methods=['GET'])
@require_auth
def get_me():
    """Get current user information."""
    username = get_jwt_identity()
    two_factor_enabled = auth_bp.store.is_two_factor_enabled()
    
    return jsonify({
        'success': True,
        'data': {
            'username': username,
            'twoFactorEnabled': two_factor_enabled
        }
    }), 200


@auth_bp.route('/setup-2fa', methods=['POST'])
@require_auth
def setup_2fa():
    """Setup 2FA by generating and storing a new secret."""
    # Generate new secret
    secret = pyotp.random_base32()
    
    # Store secret
    auth_bp.store.update_two_factor_secret(secret)
    
    # Generate provisioning URI for QR code
    username = get_jwt_identity()
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=username,
        issuer_name='115 Telegram Bot'
    )
    
    return jsonify({
        'success': True,
        'data': {
            'secret': secret,
            'qrCodeUri': provisioning_uri
        }
    }), 200


@auth_bp.route('/status', methods=['GET'])
def status():
    """Get current auth/lockout/2FA verification status.

    Returns data shaped like the frontend AuthState plus twoFactorSecret when relevant.
    """
    client_key = _get_client_key()

    identity = None
    jti = None
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
        jwt_data = get_jwt()
        jti = jwt_data.get('jti') if jwt_data else None
    except Exception:
        identity = None
        jti = None

    two_factor_enabled = auth_bp.store.is_two_factor_enabled()

    if not identity:
        is_2fa_verified = False
    elif not two_factor_enabled:
        is_2fa_verified = True
    else:
        is_2fa_verified = bool(jti and jti in getattr(current_app, 'two_fa_verified_jti', set()))

    return jsonify({
        'success': True,
        'data': _build_auth_state(
            is_authenticated=bool(identity),
            is_2fa_verified=is_2fa_verified,
            client_key=client_key,
            include_secret=bool(identity) and two_factor_enabled
        )
    }), 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout by revoking the current JWT and clearing any 2FA verifier state."""
    client_key = _get_client_key()

    jti = None
    try:
        verify_jwt_in_request(optional=True)
        jwt_data = get_jwt()
        jti = jwt_data.get('jti') if jwt_data else None
    except Exception:
        jti = None

    if jti:
        current_app.revoked_jti.add(jti)
        current_app.two_fa_verified_jti.discard(jti)

    return jsonify({
        'success': True,
        'data': _build_auth_state(False, False, client_key)
    }), 200


@auth_bp.route('/password', methods=['PUT'])
@require_auth
def update_password():
    """Update admin password.

    Requires the current password when one is already set.
    """
    client_key = _get_client_key()
    data = request.get_json() or {}

    current_password = data.get('currentPassword') or data.get('current_password') or data.get('oldPassword')
    new_password = data.get('newPassword') or data.get('new_password') or data.get('password')

    if not new_password:
        return jsonify({
            'success': False,
            'error': 'New password is required'
        }), 400

    admin = auth_bp.store.get_admin_credentials()
    existing_hash = admin.get('password_hash')

    if existing_hash:
        if not current_password:
            return jsonify({
                'success': False,
                'error': 'Current password is required'
            }), 400
        if not check_password_hash(existing_hash, current_password):
            return jsonify({
                'success': False,
                'error': 'Invalid current password'
            }), 401

    password_hash = generate_password_hash(new_password)
    auth_bp.store.update_admin_password(password_hash)

    two_factor_enabled = auth_bp.store.is_two_factor_enabled()
    identity = get_jwt_identity()
    jti = get_jwt().get('jti')

    is_2fa_verified = True
    if two_factor_enabled:
        is_2fa_verified = bool(jti and jti in getattr(current_app, 'two_fa_verified_jti', set()))

    return jsonify({
        'success': True,
        'data': _build_auth_state(
            is_authenticated=bool(identity),
            is_2fa_verified=is_2fa_verified,
            client_key=client_key,
            include_secret=two_factor_enabled
        )
    }), 200
