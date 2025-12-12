from flask import Blueprint, request, jsonify
from middleware.auth import require_auth
from services.strm_service import StrmService
from persistence.store import DataStore

strm_bp = Blueprint('strm', __name__, url_prefix='/api/strm')

# Global instances (set during initialization)
_strm_service = None
_store = None


def init_strm_blueprint(store: DataStore):
    """Initialize strm blueprint with required services."""
    global _strm_service, _store
    _store = store
    _strm_service = StrmService(store)
    strm_bp.store = store
    return strm_bp


@strm_bp.route('/generate', methods=['POST'])
@require_auth
def generate_strm():
    """Generate STRM files for specified provider."""
    try:
        if not _strm_service:
            return jsonify({
                'success': False,
                'error': 'STRM service not initialized'
            }), 500
        
        data = request.get_json() or {}
        strm_type = data.get('type', '115')  # 115, 123, or openlist
        config = data.get('config', {})
        
        result = _strm_service.generate_strm(strm_type, config)
        
        return jsonify({
            'success': result['success'],
            'data': result.get('data', {})
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to generate STRM: {str(e)}'
        }), 500


@strm_bp.route('/tasks', methods=['GET'])
@require_auth
def list_strm_tasks():
    """List STRM generation tasks."""
    try:
        if not _strm_service:
            return jsonify({
                'success': False,
                'error': 'STRM service not initialized'
            }), 500
        
        tasks = _strm_service.list_tasks()
        
        return jsonify({
            'success': True,
            'data': tasks
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to list STRM tasks: {str(e)}'
        }), 500
