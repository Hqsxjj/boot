from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from middleware.auth import require_auth
from services.offline_tasks import OfflineTaskService

offline_bp = Blueprint('offline', __name__, url_prefix='/api/115/offline')

# These will be set by init_offline_blueprint
_offline_task_service: OfflineTaskService = None


def init_offline_blueprint(offline_task_service: OfflineTaskService):
    """Initialize offline blueprint with service."""
    global _offline_task_service
    _offline_task_service = offline_task_service
    return offline_bp


@offline_bp.route('/tasks', methods=['POST'])
@require_auth
def create_task():
    """Create a new offline task."""
    try:
        data = request.get_json() or {}
        username = get_jwt_identity()
        
        # Validate required fields
        source_url = data.get('sourceUrl') or data.get('source_url')
        save_cid = data.get('saveCid') or data.get('save_cid')
        requested_by = data.get('requestedBy') or data.get('requested_by') or username
        requested_chat = data.get('requestedChat') or data.get('requested_chat') or ''
        
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
        
        # Create task
        result = _offline_task_service.create_task(
            source_url=source_url,
            save_cid=save_cid,
            requested_by=requested_by,
            requested_chat=requested_chat
        )
        
        if result.get('success'):
            return jsonify(result), 201
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to create task: {str(e)}'
        }), 500


@offline_bp.route('/tasks', methods=['GET'])
@require_auth
def list_tasks():
    """List offline tasks with optional filtering and refresh."""
    try:
        # Query parameters
        status = request.args.get('status')
        requested_by = request.args.get('requestedBy')
        limit = int(request.args.get('limit', '50'))
        offset = int(request.args.get('offset', '0'))
        refresh = request.args.get('refresh', 'false').lower() == 'true'
        
        # Refresh from 115 if requested
        if refresh:
            sync_result = _offline_task_service.sync_all()
            if not sync_result.get('success'):
                return jsonify({
                    'success': False,
                    'error': f'Failed to refresh from 115: {sync_result.get("error")}'
                }), 500
        
        # List tasks
        result = _offline_task_service.list_tasks(
            status=status,
            requested_by=requested_by,
            limit=limit,
            offset=offset
        )
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': f'Invalid parameter: {str(e)}'
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to list tasks: {str(e)}'
        }), 500


@offline_bp.route('/tasks/<task_id>', methods=['GET'])
@require_auth
def get_task(task_id: str):
    """Get a single offline task."""
    try:
        task = _offline_task_service.get_task(task_id)
        
        if not task:
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404
        
        return jsonify({
            'success': True,
            'data': task.to_dict()
        }), 200
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to get task: {str(e)}'
        }), 500


@offline_bp.route('/tasks/<task_id>', methods=['DELETE'])
@require_auth
def delete_task(task_id: str):
    """Delete an offline task."""
    try:
        result = _offline_task_service.delete_task(task_id)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to delete task: {str(e)}'
        }), 500


@offline_bp.route('/tasks/<task_id>', methods=['PATCH'])
@require_auth
def cancel_task(task_id: str):
    """Cancel an offline task."""
    try:
        result = _offline_task_service.cancel_task(task_id)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 404
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to cancel task: {str(e)}'
        }), 500


@offline_bp.route('/tasks/<task_id>/retry', methods=['POST'])
@require_auth
def retry_task(task_id: str):
    """Retry a failed offline task."""
    try:
        result = _offline_task_service.retry_task(task_id)
        
        if result.get('success'):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to retry task: {str(e)}'
        }), 500
