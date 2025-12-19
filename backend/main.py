import os
from datetime import timedelta
from flask import Flask, jsonify, send_from_directory
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 静态文件目录配置
STATIC_FOLDER = os.environ.get('STATIC_FOLDER', '/app/static')

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
from blueprints.resource_search import resource_search_bp, init_resource_search_blueprint
from blueprints.keywords import keywords_bp, set_keyword_store
from blueprints.subscription import subscription_bp, init_subscription_service
from services.subscription_service import SubscriptionService
from services.pan_search_service import get_pan_search_service
import threading
import time
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
    # 检查静态文件目录是否存在
    static_folder = STATIC_FOLDER if os.path.isdir(STATIC_FOLDER) else None
    
    app = Flask(__name__, static_folder=static_folder, static_url_path='')
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)

    # Allow custom config override early
    if config:
        app.config.update(config)
    
    # 单体架构：无需 CORS 配置（前后端同源）
    
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
            'error': '令牌已被撤销'
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
            'error': '令牌已过期'
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'success': False,
            'error': '无效令牌'
        }), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'success': False,
            'error': '缺少认证令牌'
        }), 401
    
    # Initialize data store
    data_path = os.environ.get('DATA_PATH', '/data/appdata.json')
    store = DataStore(data_path)
    
    # Initialize logger
    logger = get_app_logger()
    logger.info('正在启动应用初始化...')
    
    # Initialize dual databases (secrets.db + appdata.db)
    secrets_engine, appdata_engine = init_all_databases()
    secrets_session_factory = get_session_factory(secrets_engine)
    appdata_session_factory = get_session_factory(appdata_engine)
    secret_store = SecretStore(secrets_session_factory)
    
    logger.info('数据库初始化完成: secrets.db (加密), appdata.db (常规数据)')
    
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
    
    logger.info('服务初始化成功')
    
    # Start task poller
    if not app.config.get('TESTING'):
        task_poller.start()
    
    # Blueprints
    init_auth_blueprint(store)
    init_config_blueprint(store, secret_store)
    init_cloud115_blueprint(secret_store)
    init_cloud123_blueprint(secret_store)
    init_offline_blueprint(offline_task_service)
    init_logs_blueprint()
    
    from blueprints.keywords import set_keyword_store
    from services.keyword_store import KeywordStore
    keyword_store_instance = KeywordStore(store)
    set_keyword_store(keyword_store_instance)

    telegram_bot_service = init_bot_blueprint(store, secret_store)
    init_resource_search_blueprint(store)
    
    init_strm_blueprint(store)
    
    # 注入 TelegramBotService 到 EmbyService (用于 Webhook 通知)
    telegram_service = TelegramBotService(secret_store)
    init_emby_blueprint(store)
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
    app.register_blueprint(resource_search_bp)
    
    # Initialize Wallpaper Blueprint
    from blueprints.wallpaper import wallpaper_bp
    wallpaper_bp.store = store
    app.register_blueprint(wallpaper_bp)
    
    # Initialize Organize Blueprint (TMDB 重命名整理)
    from blueprints.organize import organize_bp, init_organize_blueprint
    from services.tmdb_service import TmdbService
    tmdb_service = TmdbService(secret_store, store)
    init_organize_blueprint(store, tmdb_service, cloud115_service, cloud123_service)
    app.register_blueprint(organize_bp)

    # Initialize Subscription Service
    data_dir = os.path.dirname(data_path)
    pan_search_service = get_pan_search_service()
    subscription_service = SubscriptionService(data_dir, pan_search_service, cloud115_service, cloud123_service)
    init_subscription_service(subscription_service)
    app.register_blueprint(subscription_bp)

    if not app.config.get('TESTING'):
        subscription_service.start_scheduler()
        logger.info("已启动订阅自动检测调度器 (APScheduler)")


    
    # 前端静态文件服务（SPA fallback）
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve_frontend(path):
        # API 路由由 Blueprint 处理，这里只处理前端请求
        if path.startswith('api/'):
            # 返回 404，让 Flask 的 errorhandler 处理
            return jsonify({'success': False, 'error': '未找到接口'}), 404
        
        # STRM 文件浏览由专门路由处理
        if path.startswith('strm/'):
            strm_path = path[5:]  # 移除 'strm/' 前缀
            strm_dir = '/data/strm'
            file_path = os.path.join(strm_dir, strm_path)
            if os.path.isfile(file_path):
                return send_from_directory(strm_dir, strm_path)
            elif os.path.isdir(file_path):
                # 目录列表
                import json
                try:
                    files = os.listdir(file_path)
                    return jsonify({'files': files})
                except Exception as e:
                    logger.error(f"列出目录失败: {e}")
                    return jsonify({'success': False, 'error': str(e)}), 500
            else:
                return jsonify({'error': '未找到'}), 404
        
        # 静态文件服务
        if app.static_folder:
            file_path = os.path.join(app.static_folder, path)
            if path and os.path.isfile(file_path):
                return send_from_directory(app.static_folder, path)
            else:
                # SPA fallback: 所有非文件请求返回 index.html
                index_path = os.path.join(app.static_folder, 'index.html')
                if os.path.isfile(index_path):
                    return send_from_directory(app.static_folder, 'index.html')
        
        return "Frontend not built or static folder not found", 404

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'success': False,
            'error': '未找到该页面'
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'success': False,
            'error': '内部服务器错误'
        }), 500
    
    if config:
        app.config.update(config)
        
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=18080, debug=True)