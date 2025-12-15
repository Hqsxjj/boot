# blueprints/keywords.py
# 识别词 API 端点

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required


keywords_bp = Blueprint('keywords', __name__, url_prefix='/api')

# 服务实例会在 main.py 中注入
keyword_store = None


def set_keyword_store(store):
    """Set the keyword store instance."""
    global keyword_store
    keyword_store = store


@keywords_bp.route('/keywords', methods=['GET'])
@jwt_required()
def list_keywords():
    """List keywords with optional search."""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 50, type=int)
    media_type = request.args.get('mediaType')
    
    if not keyword_store:
        return jsonify({'success': False, 'error': 'Service not initialized'}), 500
    
    if query:
        results = keyword_store.search_keywords(query, limit)
    else:
        results = keyword_store.get_most_used(limit, media_type)
    
    return jsonify({'success': True, 'data': results})


@keywords_bp.route('/keywords', methods=['POST'])
@jwt_required()
def add_keyword():
    """Add or update a keyword."""
    data = request.get_json() or {}
    
    keyword = data.get('keyword', '').strip()
    normalized = data.get('normalized', '').strip()
    
    if not keyword or not normalized:
        return jsonify({'success': False, 'error': 'keyword and normalized are required'}), 400
    
    if not keyword_store:
        return jsonify({'success': False, 'error': 'Service not initialized'}), 500
    
    result = keyword_store.add_keyword(
        keyword=keyword,
        normalized=normalized,
        media_type=data.get('mediaType', 'movie'),
        tmdb_id=data.get('tmdbId'),
        source=data.get('source', 'manual'),
        extra_info=data.get('extraInfo')
    )
    
    return jsonify(result)


@keywords_bp.route('/keywords/<int:keyword_id>', methods=['DELETE'])
@jwt_required()
def delete_keyword(keyword_id):
    """Delete a keyword by ID."""
    if not keyword_store:
        return jsonify({'success': False, 'error': 'Service not initialized'}), 500
    
    result = keyword_store.delete_keyword(keyword_id)
    return jsonify(result)


@keywords_bp.route('/keywords/search', methods=['GET'])
@jwt_required()
def search_keyword():
    """Search for a matching keyword."""
    keyword = request.args.get('keyword', '').strip()
    
    if not keyword:
        return jsonify({'success': False, 'error': 'keyword parameter required'}), 400
    
    if not keyword_store:
        return jsonify({'success': False, 'error': 'Service not initialized'}), 500
    
    result = keyword_store.find_keyword(keyword)
    
    if result:
        return jsonify({'success': True, 'data': result, 'found': True})
    return jsonify({'success': True, 'data': None, 'found': False})


@keywords_bp.route('/keywords/import', methods=['POST'])
@jwt_required()
def bulk_import():
    """Bulk import keywords."""
    data = request.get_json() or {}
    keywords = data.get('keywords', [])
    source = data.get('source', 'import')
    
    if not keywords:
        return jsonify({'success': False, 'error': 'keywords array required'}), 400
    
    if not keyword_store:
        return jsonify({'success': False, 'error': 'Service not initialized'}), 500
    
    result = keyword_store.bulk_import(keywords, source)
    return jsonify(result)


@keywords_bp.route('/keywords/stats', methods=['GET'])
@jwt_required()
def get_stats():
    """Get keyword statistics."""
    if not keyword_store:
        return jsonify({'success': False, 'error': 'Service not initialized'}), 500
    
    stats = keyword_store.get_stats()
    return jsonify({'success': True, 'data': stats})
