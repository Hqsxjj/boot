from flask import Blueprint, jsonify, current_app
from services.tmdb_service import TmdbService

wallpaper_bp = Blueprint('wallpaper', __name__, url_prefix='/api/wallpaper')
tmdb_service = TmdbService()

@wallpaper_bp.route('/trending', methods=['GET'])
def get_trending():
    """Get weekly trending wallpaper from TMDB."""
    try:
        # Assuming store is attached to blueprint or available globally
        store = getattr(wallpaper_bp, 'store', None)
        config = store.get_config() if store else {}
        
        url = tmdb_service.get_trending_wallpaper(config)
        
        if url:
            return jsonify({
                'success': True, 
                'url': url,
                'source': 'tmdb'
            })
        
        return jsonify({
            'success': False, 
            'message': 'No wallpaper found'
        }), 404
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': str(e)
        }), 500
