import os
from datetime import timedelta
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 确保这些模块路径在你的项目中存在
from persistence.store import DataStore
from blueprints.auth import auth_bp, init_auth_blueprint
from blueprints.config import config_bp, init_config_blueprint
from blueprints.health import health_bp
from blueprints.cloud115 import cloud115_bp, init_cloud115_blueprint
from blueprints.cloud123 import cloud123_bp, init_cloud123_blueprint
from blueprints.offline import offline_bp, init_offline_blueprint
from blueprints.bot import bot_bp, init_bot_blueprint
from blueprints.emby import emby_bp, init_emby_blueprint
from blueprints.strm import strm_bp, init_strm_blueprint
from blueprints.logs import logs_bp, init_logs_blueprint
from blueprints.keywords import keywords_bp, set_keyword_store
from models.database import init_all_databases, get_session_factory
from models.offline_task import OfflineTask
from services.secret_store import SecretStore
from services.cloud115_service import Cloud115Service
from services.cloud123_service import Cloud123Service
from services.telegram_bot import TelegramBotService
from services.offline_tasks import OfflineTaskService
from services.task_poller import create_task_poller
from utils.logger import get_app_logger, get_api_logger


def create_app(config=None):
    """Application factory for Flask app."""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

    # Allow custom config override early
    if config:
        app.config.update(config)
    
    # [微调] CORS configuration - 允许所有来源 (Regex) 以支持 LAN IP 访问
    # default_origins = 'http://localhost:5173,http://localhost:3000,http://localhost:18080'
    # cors_origins = os.environ.get('CORS_ORIGINS', default_origins).split(',')
    
    CORS(app, resources={
        r"/api/*": {
            "origins": r"^https?://.*$",  # 允许所有 HTTP/HTTPS 来源
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True
        }
    })
    
    # JWT Manager
    jwt = JWTManager(app)

    # In-memory JWT deny list
    app.revoked_jti = set()
    app.two_fa_verified_jti = set()

    @jwt.token_in_blocklist_loader
    def is_token_revoked(jwt_header, jwt_payload):
        return jwt_payload.get('jti') in app.revoked_jti

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'success': False,
            'error': 'Token has been revoked'
        }), 401
    
    # Rate Limiter
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://",
        enabled=not app.config.get('TESTING', False)
    )
    
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
    
    # Initialize logger
    logger = get_app_logger()
    logger.info('Starting application initialization...')
    
    # Initialize dual databases (secrets.db + appdata.db)
    secrets_engine, appdata_engine = init_all_databases()
    secrets_session_factory = get_session_factory(secrets_engine)
    appdata_session_factory = get_session_factory(appdata_engine)
    secret_store = SecretStore(secrets_session_factory)
    
    logger.info('Database initialized: secrets.db (encrypted), appdata.db (general data)')
    
    # Store in app context
    app.secret_store = secret_store
    app.secrets_engine = secrets_engine
    app.appdata_engine = appdata_engine
    app.secrets_session_factory = secrets_session_factory
    app.appdata_session_factory = appdata_session_factory
    # Legacy aliases for backward compatibility
    app.db_engine = secrets_engine
    app.session_factory = secrets_session_factory
    
    # Initialize services
    cloud115_service = Cloud115Service(secret_store)
    cloud123_service = Cloud123Service(secret_store)
    
    # Initialize sensitive data service for encrypted storage
    from services.sensitive_data_service import SensitiveDataService
    sensitive_data_service = SensitiveDataService(secret_store)
    app.sensitive_data_service = sensitive_data_service
    
    # Initialize offline task service and poller
    offline_task_service = OfflineTaskService(secrets_session_factory, store, None, cloud115_service)
    task_poller = create_task_poller(offline_task_service)
    
    app.cloud115_service = cloud115_service
    app.cloud123_service = cloud123_service
    app.offline_task_service = offline_task_service
    app.task_poller = task_poller
    
    logger.info('Services initialized successfully')
    
    # Start task poller
    if not app.config.get('TESTING'):
        task_poller.start()
    
    # Initialize blueprints
    init_auth_blueprint(store)
    init_config_blueprint(store, secret_store)
    init_cloud115_blueprint(secret_store)
    init_cloud123_blueprint(secret_store)
    init_offline_blueprint(offline_task_service)
    init_bot_blueprint(secret_store, store)
    init_emby_blueprint(store)
    init_strm_blueprint(store)
    init_logs_blueprint()
    
    # Initialize keyword store for AI recognition caching
    from services.keyword_store import KeywordStore
    keyword_store = KeywordStore(secrets_session_factory)
    app.keyword_store = keyword_store
    set_keyword_store(keyword_store)
    
    # Initialize Workflow Service for Bot automation
    from services.link_parser import LinkParser
    from services.workflow_service import WorkflowService
    from services.emby_service import EmbyService
    from services.strm_service import StrmService
    from blueprints.bot import set_workflow_service
    
    link_parser = LinkParser()
    telegram_service = TelegramBotService(secret_store)
    emby_service = EmbyService(store)
    strm_service = StrmService(store)
    
    workflow_service = WorkflowService(
        link_parser=link_parser,
        cloud115_service=cloud115_service,
        cloud123_service=cloud123_service,
        offline_service=offline_task_service,
        strm_service=strm_service,
        emby_service=emby_service,
        telegram_service=telegram_service,
        config_store=store
    )
    
    app.workflow_service = workflow_service
    set_workflow_service(workflow_service)
    
    # 设置 Emby 的 Telegram 通知服务
    from blueprints.emby import set_telegram_service
    set_telegram_service(telegram_service)
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(cloud115_bp)
    app.register_blueprint(cloud123_bp)
    app.register_blueprint(offline_bp)
    app.register_blueprint(bot_bp)
    app.register_blueprint(emby_bp)
    app.register_blueprint(strm_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(keywords_bp)
    
    # Initialize Wallpaper Blueprint
    from blueprints.wallpaper import wallpaper_bp
    wallpaper_bp.store = store
    app.register_blueprint(wallpaper_bp)
    
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
                    'me': '/api/me',
                    'bot': '/api/bot/*'
                }
            }
        }), 200
    
    # Global error handlers
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
    
    if config:
        app.config.update(config)
    
    return app


def get_offline_task_service():
    try:
        from flask import current_app
        return getattr(current_app, 'offline_task_service', None)
    except:
        return None


def get_app():
    try:
        from flask import current_app
        return current_app
    except:
        return None


if __name__ == '__main__':
    app = create_app()
    # [关键修改] 默认端口改为 8000，以匹配 Nginx 配置
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False').lower() == 'true')