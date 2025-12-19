
import logging
from flask import Blueprint, jsonify, request
from services.subscription_service import SubscriptionService
from auth.auth import require_auth
from typing import Optional

logger = logging.getLogger(__name__)
subscription_bp = Blueprint('subscription', __name__, url_prefix='/api/subscription')

_subscription_service: Optional[SubscriptionService] = None

def init_subscription_service(service: SubscriptionService):
    global _subscription_service
    _subscription_service = service

def get_subscription_service() -> SubscriptionService:
    if not _subscription_service:
        raise RuntimeError("SubscriptionService not initialized")
    return _subscription_service

@subscription_bp.route('/list', methods=['GET'])
@require_auth
def list_subscriptions():
    """List all subscriptions."""
    try:
        service = get_subscription_service()
        subs = service.get_subscriptions()
        return jsonify({
            'success': True,
            'data': subs
        })
    except Exception as e:
        logger.error(f"Failed to list subscriptions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_bp.route('/add', methods=['POST'])
@require_auth
def add_subscription():
    """
    Add a subscription.
    Body: { "keyword": "Matrix", "cloud_type": "115", "filter_config": {...} }
    """
    try:
        data = request.get_json()
        keyword = data.get('keyword')
        cloud_type = data.get('cloud_type', '115')
        filter_config = data.get('filter_config', {})
        
        if not keyword:
            return jsonify({'success': False, 'error': 'Missing keyword'}), 400
            
        service = get_subscription_service()
        sub = service.add_subscription(keyword, cloud_type, filter_config)
        
        return jsonify({
            'success': True,
            'data': sub
        })
    except Exception as e:
        logger.error(f"Failed to add subscription: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_bp.route('/delete/<sub_id>', methods=['DELETE'])
@require_auth
def delete_subscription(sub_id):
    """Delete a subscription."""
    try:
        service = get_subscription_service()
        if service.delete_subscription(sub_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Subscription not found'}), 404
    except Exception as e:
        logger.error(f"Failed to delete subscription: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@subscription_bp.route('/run', methods=['POST'])
@require_auth
def run_checks_manually():
    """Manually trigger subscription checks."""
    try:
        service = get_subscription_service()
        # Run in a separate thread to avoid blocking? 
        # For now run synchronously for feedback or maybe thread it.
        # User might want to know result immediately if it's manual trigger.
        # But extensive search might take time.
        # Let's run it synchronously for the MVP feedback.
        service.run_checks()
        return jsonify({
            'success': True,
            'message': 'Subscription checks completed'
        })
    except Exception as e:
        logger.error(f"Failed to run checks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
