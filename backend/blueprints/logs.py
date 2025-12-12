from flask import Blueprint, request, jsonify
from middleware.auth import require_auth
from services.logs_service import LogsService

logs_bp = Blueprint('logs', __name__, url_prefix='/api/logs')

# Global instances (set during initialization)
_logs_service = None


def init_logs_blueprint():
    """Initialize logs blueprint with required services."""
    global _logs_service
    _logs_service = LogsService()
    return logs_bp


@logs_bp.route('', methods=['GET'])
@require_auth
def get_logs():
    """Get application logs."""
    try:
        if not _logs_service:
            return jsonify({
                'success': False,
                'error': 'Logs service not initialized'
            }), 500
        
        limit = request.args.get('limit', 100, type=int)
        since = request.args.get('since', None, type=float)
        
        logs = _logs_service.get_logs(limit=limit, since=since)
        
        return jsonify({
            'success': True,
            'data': logs
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to retrieve logs: {str(e)}'
        }), 500
