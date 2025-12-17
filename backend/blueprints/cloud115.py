from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from middleware.auth import require_auth
from p115_bridge import get_p115_service
from services.secret_store import SecretStore
from services.cloud115_service import Cloud115Service
import json

cloud115_bp = Blueprint('cloud115', __name__, url_prefix='/api/115')

# These will be set by init_cloud115_blueprint
_secret_store = None
_p115_service = None
_cloud115_service = None


def init_cloud115_blueprint(secret_store: SecretStore):
    """Initialize cloud115 blueprint with secret store."""
    global _secret_store, _p115_service, _cloud115_service
    _secret_store = secret_store
    _p115_service = get_p115_service()
    _cloud115_service = Cloud115Service(secret_store)
    return cloud115_bp


@cloud115_bp.route('/login/qrcode', methods=['POST'])
@require_auth
def start_qr_login():
    """Start a QR code login session for 115 cloud."""
    try:
        data = request.get_json() or {}
        
        login_app = data.get('loginApp', 'web')
        login_method = data.get('loginMethod', 'qrcode')
        app_id = data.get('appId')  # 第三方 App ID (仅 open_app 模式需要)
        
        # 调试日志
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"start_qr_login called: login_app={login_app}, login_method={login_method}, app_id={app_id}, raw_data={data}")
        
        # 验证登录方式
        if login_method not in ['qrcode', 'cookie', 'open_app']:
            return jsonify({
                'success': False,
                'error': 'Invalid login method. Use qrcode, cookie, or open_app'
            }), 400
        
        # open_app 模式必须提供 appId
        if login_method == 'open_app' and not app_id:
            return jsonify({
                'success': False,
                'error': 'appId is required for open_app login method'
            }), 400
        
        # Start QR login
        result = _p115_service.start_qr_login(
            login_app=login_app,
            login_method=login_method,
            app_id=app_id  # 传递第三方 App ID
        )
        
        if 'error' in result and result.get('success') == False:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to start QR login')
            }), 400
        
        return jsonify({
            'success': True,
            'data': {
                'sessionId': result['sessionId'],
                'qrcode': result['qrcode'],
                'loginMethod': result['login_method'],
                'loginApp': result['login_app']
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to start QR login: {str(e)}'
        }), 500


@cloud115_bp.route('/login/status/<session_id>', methods=['GET'])
@require_auth
def poll_login_status(session_id: str):
    """Poll QR code login status and persist cookies on success."""
    try:
        result = _p115_service.poll_login_status(session_id)
        
        if not result.get('success'):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Login failed'),
                'status': result.get('status', 'error')
            }), 400
        
        if result.get('status') == 'success':
            # Persist cookies to secret store
            cookies = result.get('cookies', {})
            
            if not cookies:
                return jsonify({
                    'success': False,
                    'error': 'No cookies received from login'
                }), 400
            
            # Store cookies encrypted - use method-specific key for independent storage
            cookies_json = json.dumps(cookies)
            login_method = _p115_service._session_cache.get(session_id, {}).get('login_method')
            
            if login_method == 'open_app':
                _secret_store.set_secret('cloud115_openapp_cookies', cookies_json)
            else:
                _secret_store.set_secret('cloud115_qr_cookies', cookies_json)
            
            # Also update legacy key for backwards compatibility
            _secret_store.set_secret('cloud115_cookies', cookies_json)
            
            # Also store session metadata
            metadata = {
                'login_method': login_method,
                'login_app': _p115_service._session_cache.get(session_id, {}).get('login_app'),
                'app_id': _p115_service._session_cache.get(session_id, {}).get('app_id'),
                'logged_in_at': __import__('datetime').datetime.now().isoformat()
            }
            _secret_store.set_secret('cloud115_session_metadata', json.dumps(metadata))
            
            # Clear session
            _p115_service.clear_session(session_id)
            
            return jsonify({
                'success': True,
                'data': {
                    'status': 'success',
                    'message': 'Login successful and cookies stored'
                }
            }), 200
        
        # Still waiting
        return jsonify({
            'success': True,
            'data': {
                'status': result.get('status', 'waiting'),
                'message': 'Waiting for user to scan QR code'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to poll status: {str(e)}'
        }), 500


@cloud115_bp.route('/login/cookie', methods=['POST'])
@require_auth
def ingest_cookies():
    """Manually ingest and validate 115 cookies."""
    try:
        data = request.get_json()
        
        if not data or 'cookies' not in data:
            return jsonify({
                'success': False,
                'error': 'Cookies are required'
            }), 400
        
        cookies = data.get('cookies')
        
        if not isinstance(cookies, dict):
            try:
                if isinstance(cookies, str):
                    cookies = json.loads(cookies)
            except json.JSONDecodeError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid cookies format'
                }), 400
        
        # Validate cookies
        is_valid = _p115_service.validate_cookies(cookies)
        
        if not is_valid:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired cookies'
            }), 401
        
        # Store cookies encrypted - use manual-specific key for independent storage
        cookies_json = json.dumps(cookies)
        _secret_store.set_secret('cloud115_manual_cookies', cookies_json)
        # Also update legacy key for backwards compatibility
        _secret_store.set_secret('cloud115_cookies', cookies_json)
        
        # Store metadata
        metadata = {
            'login_method': 'manual_import',
            'login_app': data.get('loginApp', 'web'),
            'logged_in_at': __import__('datetime').datetime.now().isoformat()
        }
        _secret_store.set_secret('cloud115_session_metadata', json.dumps(metadata))
        
        return jsonify({
            'success': True,
            'data': {
                'message': 'Cookies validated and stored successfully'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to ingest cookies: {str(e)}'
        }), 500


@cloud115_bp.route('/session', methods=['GET'])
@require_auth
def get_session_health():
    """Report 115 session health status."""
    try:
        # Try to get stored cookies
        cookies_json = _secret_store.get_secret('cloud115_cookies')
        
        if not cookies_json:
            return jsonify({
                'success': True,
                'data': {
                    'hasValidSession': False,
                    'message': 'No 115 session configured'
                }
            }), 200
        
        try:
            cookies = json.loads(cookies_json)
        except json.JSONDecodeError:
            return jsonify({
                'success': True,
                'data': {
                    'hasValidSession': False,
                    'message': 'Invalid session data'
                }
            }), 200
        
        # Check session health
        health = _p115_service.get_session_health(cookies)
        
        return jsonify({
            'success': True,
            'data': {
                'hasValidSession': health.get('hasValidSession', False),
                'lastCheck': health.get('lastCheck'),
                'message': 'Session check complete'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to check session: {str(e)}'
        }), 500


@cloud115_bp.route('/directories', methods=['GET'])
@require_auth
def list_directories():
    """List directory contents from 115 cloud."""
    try:
        cid = request.args.get('cid', '0')
        
        result = _cloud115_service.list_directory(cid)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'data': result.get('data', [])
            }), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to list directories: {str(e)}'
        }), 500


@cloud115_bp.route('/files/rename', methods=['POST'])
@require_auth
def rename_file():
    """Rename a file or folder on 115 cloud."""
    try:
        data = request.get_json() or {}
        
        file_id = data.get('fileId') or data.get('file_id')
        new_name = data.get('newName') or data.get('new_name')
        
        if not file_id:
            return jsonify({
                'success': False,
                'error': 'fileId is required'
            }), 400
        
        if not new_name:
            return jsonify({
                'success': False,
                'error': 'newName is required'
            }), 400
        
        result = _cloud115_service.rename_file(file_id, new_name)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to rename: {str(e)}'
        }), 500


@cloud115_bp.route('/files/move', methods=['POST'])
@require_auth
def move_file():
    """Move a file or folder to another directory on 115 cloud."""
    try:
        data = request.get_json() or {}
        
        file_id = data.get('fileId') or data.get('file_id')
        target_cid = data.get('targetCid') or data.get('target_cid')
        
        if not file_id:
            return jsonify({
                'success': False,
                'error': 'fileId is required'
            }), 400
        
        if not target_cid:
            return jsonify({
                'success': False,
                'error': 'targetCid is required'
            }), 400
        
        result = _cloud115_service.move_file(file_id, target_cid)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to move: {str(e)}'
        }), 500


@cloud115_bp.route('/files', methods=['DELETE'])
@require_auth
def delete_file():
    """Delete a file or folder from 115 cloud."""
    try:
        data = request.get_json() or {}
        
        file_id = data.get('fileId') or data.get('file_id')
        
        if not file_id:
            return jsonify({
                'success': False,
                'error': 'fileId is required'
            }), 400
        
        result = _cloud115_service.delete_file(file_id)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to delete: {str(e)}'
        }), 500


@cloud115_bp.route('/files/offline', methods=['POST'])
@require_auth
def create_offline_task():
    """Create an offline download task (alias for /api/115/offline/tasks)."""
    try:
        data = request.get_json() or {}
        username = get_jwt_identity()
        
        source_url = data.get('sourceUrl') or data.get('source_url')
        save_cid = data.get('saveCid') or data.get('save_cid')
        
        if not source_url:
            return jsonify({
                'success': False,
                'error': 'sourceUrl is required'
            }), 400
        
        if not save_cid:
            return jsonify({
                'success': False,
                'error': 'saveCid is required'
            }), 400
        
        # Create task via cloud115 service first to get p115 task ID
        result = _cloud115_service.create_offline_task(source_url, save_cid)
        
        if not result.get('success'):
            return jsonify(result), 400
        
        p115_task_id = result['data'].get('p115TaskId')
        
        # Import offline task service at runtime to avoid circular dependency
        from main import get_offline_task_service
        offline_service = get_offline_task_service()
        
        if offline_service:
            # Store in local database
            local_result = offline_service.create_task(
                source_url=source_url,
                save_cid=save_cid,
                requested_by=username,
                requested_chat=''
            )
            
            if local_result.get('success'):
                # Update with p115 task ID
                task = offline_service.get_task(local_result['data']['id'])
                if task:
                    from models.database import get_session_factory
                    from main import get_app
                    app = get_app()
                    session = app.session_factory()
                    task.p115_task_id = p115_task_id
                    session.merge(task)
                    session.commit()
                    session.close()
                
                return jsonify(local_result), 201
        
        # Fallback: return just the 115 task info
        return jsonify({
            'success': True,
            'data': {
                'p115TaskId': p115_task_id,
                'sourceUrl': source_url,
                'saveCid': save_cid
            }
        }), 201
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to create offline task: {str(e)}'
        }), 500



# ============================================================
# 🚀 追加的新接口：返回全部 loginApp 端
# ============================================================

@cloud115_bp.route('/login/apps', methods=['GET'])
@require_auth
def list_login_apps():
    """Return all supported loginApp device profiles."""
    try:
        from p115_bridge import ALL_DEVICE_PROFILES_FULL

        apps = [{"key": k, "appId": v} for k, v in ALL_DEVICE_PROFILES_FULL.items()]

        return jsonify({
            "success": True,
            "data": apps
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Failed to list login apps: {str(e)}"
        }), 500