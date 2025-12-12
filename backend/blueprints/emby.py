from flask import Blueprint, request, jsonify
from middleware.auth import require_auth
from services.emby_service import EmbyService
from persistence.store import DataStore

emby_bp = Blueprint('emby', __name__, url_prefix='/api/emby')

# Global instances (set during initialization)
_emby_service = None
_store = None


def init_emby_blueprint(store: DataStore):
    """Initialize emby blueprint with required services."""
    global _emby_service, _store
    _store = store
    _emby_service = EmbyService(store)
    emby_bp.store = store
    return emby_bp


@emby_bp.route('/test-connection', methods=['POST'])
@require_auth
def test_emby_connection():
    """Test connection to Emby server."""
    try:
        if not _emby_service:
            return jsonify({
                'success': False,
                'error': 'Emby service not initialized'
            }), 500
        
        result = _emby_service.test_connection()
        
        return jsonify({
            'success': result['success'],
            'data': {
                'success': result['success'],
                'latency': result.get('latency', 0),
                'msg': result.get('msg', '')
            }
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to test connection: {str(e)}'
        }), 500


@emby_bp.route('/scan-missing', methods=['POST'])
@require_auth
def scan_missing_episodes():
    """Scan for missing episodes in Emby."""
    try:
        if not _emby_service:
            return jsonify({
                'success': False,
                'error': 'Emby service not initialized'
            }), 500
        
        result = _emby_service.scan_missing_episodes()
        
        return jsonify({
            'success': result['success'],
            'data': result.get('data', [])
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to scan missing episodes: {str(e)}'
        }), 500
