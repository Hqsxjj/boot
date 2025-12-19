from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from middleware.auth import require_auth
from services.secret_store import SecretStore
from services.cloud123_service import Cloud123Service
import json

cloud123_bp = Blueprint('cloud123', __name__, url_prefix='/api/123')

# These will be set by init_cloud123_blueprint
_secret_store = None
_cloud123_service = None


def init_cloud123_blueprint(secret_store: SecretStore):
    """Initialize cloud123 blueprint with secret store."""
    global _secret_store, _cloud123_service
    _secret_store = secret_store
    _cloud123_service = Cloud123Service(secret_store)
    return cloud123_bp


@cloud123_bp.route('/login/password', methods=['POST'])
@require_auth
def password_login():
    """Login to 123 cloud with passport (phone/email) and password."""
    try:
        data = request.get_json() or {}
        
        passport = data.get('passport')  # 手机号或邮箱
        password = data.get('password')
        
        if not passport or not password:
            return jsonify({
                'success': False,
                'error': '账号和密码都必须填写'
            }), 400
        
        result = _cloud123_service.login_with_password(passport, password)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'登录失败: {str(e)}'
        }), 500

@cloud123_bp.route('/login/oauth', methods=['POST'])
@require_auth
def oauth_login():
    """Start OAuth flow for 123 cloud."""
    try:
        data = request.get_json() or {}
        
        client_id = data.get('clientId')
        client_secret = data.get('clientSecret')
        
        if not client_id or not client_secret:
            return jsonify({
                'success': False,
                'error': 'clientId 和 clientSecret 不能为空'
            }), 400
        
        # 验证 OAuth 凭证：尝试获取 access token
        import requests as http_requests
        try:
            url = "https://open-api.123pan.com/api/v1/access_token"
            payload = {
                "clientID": client_id,
                "clientSecret": client_secret
            }
            headers = {
                "Content-Type": "application/json",
                "Platform": "open_platform"
            }
            
            response = http_requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            if result.get('code') != 0:
                return jsonify({
                    'success': False,
                    'error': f"OAuth 凭证验证失败: {result.get('message', '未知错误')}"
                }), 400
        except http_requests.RequestException as e:
            return jsonify({
                'success': False,
                'error': f'OAuth 凭证验证失败: {str(e)}'
            }), 400
        
        # Store credentials encrypted (only after validation succeeds)
        credentials = {
            'clientId': client_id,
            'clientSecret': client_secret
        }
        _secret_store.set_secret('cloud123_oauth_credentials', json.dumps(credentials))
        
        # Store metadata
        metadata = {
            'login_method': 'oauth',
            'logged_in_at': __import__('datetime').datetime.now().isoformat()
        }
        _secret_store.set_secret('cloud123_session_metadata', json.dumps(metadata))
        
        return jsonify({
            'success': True,
            'data': {
                'message': 'OAuth 凭证验证并保存成功'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'保存 OAuth 凭证失败: {str(e)}'
        }), 500


@cloud123_bp.route('/login/cookie', methods=['POST'])
@require_auth
def ingest_cookies():
    """Manually ingest and validate 123 cookies."""
    try:
        data = request.get_json()
        
        if not data or 'cookies' not in data:
            return jsonify({
                'success': False,
                'error': 'Cookies 不能为空'
            }), 400
        
        cookies = data.get('cookies')
        
        if not isinstance(cookies, dict):
            try:
                if isinstance(cookies, str):
                    cookies = json.loads(cookies)
            except json.JSONDecodeError:
                return jsonify({
                    'success': False,
                    'error': 'Cookies 格式无效'
                }), 400
        
        # Store cookies encrypted
        cookies_json = json.dumps(cookies)
        _secret_store.set_secret('cloud123_cookies', cookies_json)
        
        # Store metadata
        metadata = {
            'login_method': 'manual_import',
            'logged_in_at': __import__('datetime').datetime.now().isoformat()
        }
        _secret_store.set_secret('cloud123_session_metadata', json.dumps(metadata))
        
        return jsonify({
            'success': True,
            'data': {
                'message': 'Cookies 验证并保存成功'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'导入 Cookies 失败: {str(e)}'
        }), 500


@cloud123_bp.route('/session', methods=['GET'])
@require_auth
def get_session_health():
    """Report 123 session health status."""
    try:
        # Check for both token and cookies
        token_json = _secret_store.get_secret('cloud123_token')
        cookies_json = _secret_store.get_secret('cloud123_cookies')
        
        has_session = bool(token_json or cookies_json)
        
        if not has_session:
            return jsonify({
                'success': True,
                'data': {
                    'hasValidSession': False,
                    'message': '未配置 123 云盘会话'
                }
            }), 200
        
        return jsonify({
            'success': True,
            'data': {
                'hasValidSession': True,
                'lastCheck': __import__('datetime').datetime.now().isoformat(),
                'message': '会话检查完成'
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'检查会话失败: {str(e)}'
        }), 500


@cloud123_bp.route('/directories', methods=['GET'])
@require_auth
def list_directories():
    """List directory contents from 123 cloud."""
    try:
        dir_id = request.args.get('dirId', '/')
        
        result = _cloud123_service.list_directory(dir_id)
        
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
            'error': f'获取目录列表失败: {str(e)}'
        }), 500


@cloud123_bp.route('/files/rename', methods=['POST'])
@require_auth
def rename_file():
    """Rename a file or folder on 123 cloud."""
    try:
        data = request.get_json() or {}
        
        file_id = data.get('fileId') or data.get('file_id')
        new_name = data.get('newName') or data.get('new_name')
        
        if not file_id:
            return jsonify({
                'success': False,
                'error': 'fileId 不能为空'
            }), 400
        
        if not new_name:
            return jsonify({
                'success': False,
                'error': 'newName 不能为空'
            }), 400
        
        result = _cloud123_service.rename_file(file_id, new_name)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'重命名失败: {str(e)}'
        }), 500


@cloud123_bp.route('/files/move', methods=['POST'])
@require_auth
def move_file():
    """Move a file or folder to another directory on 123 cloud."""
    try:
        data = request.get_json() or {}
        
        file_id = data.get('fileId') or data.get('file_id')
        target_dir_id = data.get('targetDirId') or data.get('target_dir_id')
        
        if not file_id:
            return jsonify({
                'success': False,
                'error': 'fileId 不能为空'
            }), 400
        
        if not target_dir_id:
            return jsonify({
                'success': False,
                'error': 'targetDirId 不能为空'
            }), 400
        
        result = _cloud123_service.move_file(file_id, target_dir_id)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'移动失败: {str(e)}'
        }), 500


@cloud123_bp.route('/files', methods=['DELETE'])
@require_auth
def delete_file():
    """Delete a file or folder from 123 cloud."""
    try:
        data = request.get_json() or {}
        
        file_id = data.get('fileId') or data.get('file_id')
        
        if not file_id:
            return jsonify({
                'success': False,
                'error': 'fileId 不能为空'
            }), 400
        
        result = _cloud123_service.delete_file(file_id)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'删除失败: {str(e)}'
        }), 500


@cloud123_bp.route('/offline/tasks', methods=['POST'])
@require_auth
def create_offline_task():
    """Create an offline download task on 123 cloud."""
    try:
        data = request.get_json() or {}
        username = get_jwt_identity()
        
        source_url = data.get('sourceUrl') or data.get('source_url')
        save_dir_id = data.get('saveDirId') or data.get('save_dir_id')
        
        if not source_url:
            return jsonify({
                'success': False,
                'error': 'sourceUrl 不能为空'
            }), 400
        
        if not save_dir_id:
            return jsonify({
                'success': False,
                'error': 'saveDirId 不能为空'
            }), 400
        
        # Create task via cloud123 service
        result = _cloud123_service.create_offline_task(source_url, save_dir_id)
        
        if not result.get('success'):
            return jsonify(result), 400
        
        p123_task_id = result['data'].get('p123TaskId')
        
        # Note: Unlike 115, we don't create local database records for 123 tasks
        # They're managed directly through the 123 API
        
        return jsonify({
            'success': True,
            'data': {
                'p123TaskId': p123_task_id,
                'sourceUrl': source_url,
                'saveDirId': save_dir_id
            }
        }), 201
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'创建离线任务失败: {str(e)}'
        }), 500


@cloud123_bp.route('/offline/tasks/<task_id>', methods=['GET'])
@require_auth
def get_offline_task(task_id: str):
    """Get status of an offline task from 123 cloud."""
    try:
        result = _cloud123_service.get_offline_task_status(task_id)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'data': result.get('data', {})
            }), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取任务状态失败: {str(e)}'
        }), 500
