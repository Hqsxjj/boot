import os
from datetime import timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from persistence.store import DataStore
from blueprints.auth import auth_bp, init_auth_blueprint
from blueprints.config import config_bp, init_config_blueprint
from blueprints.health import health_bp
from blueprints.cloud115 import cloud115_bp, init_cloud115_blueprint
from blueprints.offline import offline_bp, init_offline_blueprint
from models.database import init_db, get_session_factory
from models.offline_task import OfflineTask
from services.secret_store import SecretStore
from services.offline_tasks import OfflineTaskService
from services.task_poller import create_task_poller


def create_app(config=None):
    """Application factory for Flask app."""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
    
    # CORS configuration
    cors_origins = os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')
    CORS(app, resources={
        r"/api/*": {
            "origins": cors_origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    
    # JWT Manager
    jwt = JWTManager(app)
    
    # Rate Limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://"
    )
    
    # Apply rate limiting to auth endpoints
    limiter.limit("5 per minute")(auth_bp)
    
    # Custom error handlers for JWT
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'success': False,
            'error': 'Token has expired'
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'success': False,
            'error': 'Invalid token'
        }), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'success': False,
            'error': 'Missing authorization token'
        }), 401
    
    # Initialize data store
    data_path = os.environ.get('DATA_PATH', '/data/appdata.json')
    store = DataStore(data_path)
    
    # Initialize database and secret store
    engine = init_db()
    session_factory = get_session_factory(engine)
    secret_store = SecretStore(session_factory)
    
    # Store secret_store and engine in app context for access in blueprints
    app.secret_store = secret_store
    app.db_engine = engine
    app.session_factory = session_factory
    
    # Initialize offline task service and poller
    offline_task_service = OfflineTaskService(session_factory, store, None)
    task_poller = create_task_poller(offline_task_service)
    
    # Store services in app context
    app.offline_task_service = offline_task_service
    app.task_poller = task_poller
    
    # Start task poller
    if not app.config.get('TESTING'):
        task_poller.start()
    
    # Initialize and register blueprints
    init_auth_blueprint(store)
    init_config_blueprint(store, secret_store)
    init_cloud115_blueprint(secret_store)
    init_offline_blueprint(offline_task_service)
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(cloud115_bp)
    app.register_blueprint(offline_bp)
    
    # Root endpoint
    @app.route('/')
    def index():
        return jsonify({
            'success': True,
            'data': {
                'service': '115-telegram-bot-admin',
                'version': '1.0.0',
                'endpoints': {
                    'health': '/api/health',
                    'auth': '/api/auth/*',
                    'config': '/api/config',
                    'me': '/api/me'
                }
            }
        }), 200
    
    # Global error handler
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': 'Endpoint not found'
        }), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
    
    # Allow custom config override
    if config:
        app.config.update(config)
    
    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False').lower() == 'true')
