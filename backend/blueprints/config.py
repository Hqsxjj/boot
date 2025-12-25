from flask import Blueprint, request, jsonify
from middleware.auth import optional_auth
from persistence.store import DataStore
from services.secret_store import SecretStore
import json
import copy

config_bp = Blueprint('config', __name__, url_prefix='/api')


def init_config_blueprint(store: DataStore, secret_store: SecretStore = None):
    """Initialize config blueprint with data store and secret store."""
    config_bp.store = store
    config_bp.secret_store = secret_store
    return config_bp


def _add_session_flags(config: dict, secret_store: SecretStore) -> dict:
    """Add session health flags to config."""
    if not secret_store:
        config['cloud115']['hasValidSession'] = False
        config['cloud123']['hasValidSession'] = False
        return config
    
    # Check if we have valid 115 cookies
    cookies_json = secret_store.get_secret('cloud115_cookies')
    config['cloud115']['hasValidSession'] = bool(cookies_json)
    
    # Check if we have valid 123 token, cookies, OAuth, or password credentials
    token_json = secret_store.get_secret('cloud123_token')
    cookies_123_json = secret_store.get_secret('cloud123_cookies')
    oauth_credentials = secret_store.get_secret('cloud123_oauth_credentials')
    password_credentials = secret_store.get_secret('cloud123_password_credentials')
    config['cloud123']['hasValidSession'] = bool(token_json or cookies_123_json or oauth_credentials or password_credentials)
    
    return config


def _parse_cookie_string(cookie_str: str) -> dict:
    cookies = {}
    for part in cookie_str.split(';'):
        part = part.strip()
        if not part or '=' not in part:
            continue
        key, value = part.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"')
        if key:
            cookies[key] = value
    return cookies


def _sync_cloud115_cookies_from_config(payload: dict, secret_store: SecretStore | None) -> None:
    """同步 115 Cookie 到 SecretStore"""
    import logging
    logger = logging.getLogger(__name__)
    
    if not secret_store or not isinstance(payload, dict):
        logger.debug('_sync_cloud115_cookies: secret_store 或 payload 无效')
        return

    cloud115 = payload.get('cloud115')
    if not isinstance(cloud115, dict):
        logger.debug('_sync_cloud115_cookies: cloud115 配置无效')
        return

    cookies_value = cloud115.get('cookies')
    if not isinstance(cookies_value, str):
        logger.debug('_sync_cloud115_cookies: cookies 不是字符串')
        return

    cookies_str = cookies_value.strip()

    if not cookies_str:
        logger.info('_sync_cloud115_cookies: Cookie 为空，删除已存储的凭证')
        secret_store.delete_secret('cloud115_cookies')
        secret_store.delete_secret('cloud115_manual_cookies')
        secret_store.delete_secret('cloud115_session_metadata')
        return

    parsed = _parse_cookie_string(cookies_str)
    if not parsed:
        logger.warning(f'_sync_cloud115_cookies: Cookie 解析失败，原始值: {cookies_str[:50]}...')
        return

    logger.info(f'_sync_cloud115_cookies: 成功解析 {len(parsed)} 个 Cookie 键: {list(parsed.keys())}')
    
    # 保存到多个密钥确保兼容性
    cookies_json = json.dumps(parsed)
    secret_store.set_secret('cloud115_cookies', cookies_json)
    secret_store.set_secret('cloud115_manual_cookies', cookies_json)  # 添加手动导入密钥
    
    metadata = {
        'login_method': 'manual_import',
        'login_app': cloud115.get('loginApp', 'web'),
        'logged_in_at': __import__('datetime').datetime.now().isoformat(),
    }
    secret_store.set_secret('cloud115_session_metadata', json.dumps(metadata))
    logger.info('_sync_cloud115_cookies: Cookie 已保存到 SecretStore')


def _sync_cloud123_credentials_from_config(payload: dict, secret_store: SecretStore | None) -> None:
    """同步123云盘OAuth凭证到SecretStore"""
    if not secret_store or not isinstance(payload, dict):
        return

    cloud123 = payload.get('cloud123')
    if not isinstance(cloud123, dict):
        return

    client_id = cloud123.get('clientId', '').strip()
    client_secret = cloud123.get('clientSecret', '').strip()

    if not client_id or not client_secret:
        # 如果凭证被清空，删除存储的token
        return

    # 存储OAuth凭证
    credentials = {
        'clientId': client_id,
        'clientSecret': client_secret
    }
    secret_store.set_secret('cloud123_oauth_credentials', json.dumps(credentials))
    
    # 存储元数据
    metadata = {
        'login_method': 'oauth',
        'logged_in_at': __import__('datetime').datetime.now().isoformat()
    }
    secret_store.set_secret('cloud123_session_metadata', json.dumps(metadata))


def _sync_ai_credentials_from_config(payload: dict, secret_store: SecretStore | None) -> None:
    """同步 AI (LLM) 凭证到 SecretStore"""
    if not secret_store or not isinstance(payload, dict):
        return

    organize = payload.get('organize')
    if not isinstance(organize, dict):
        return
        
    ai = organize.get('ai')
    if not isinstance(ai, dict):
        return

    api_key = ai.get('apiKey', '').strip()
    
    # 如果 apiKey 存在且不是占位符，则更新
    # 注意：update_config 会先还原 mask，所以这里拿到的应该是明文
    if api_key and api_key != MASK_PLACEHOLDER:
        secret_store.set_secret('llm_api_key', api_key)
    
    # 同步其他非敏感字段
    if 'baseUrl' in ai:
        secret_store.set_secret('llm_base_url', ai.get('baseUrl', ''))
    if 'model' in ai:
        secret_store.set_secret('llm_model', ai.get('model', ''))
    if 'provider' in ai:
        secret_store.set_secret('llm_provider', ai.get('provider', ''))


def _sync_tmdb_credentials_from_config(payload: dict, secret_store: SecretStore | None) -> None:
    """同步 TMDB API Key 到 SecretStore"""
    if not secret_store or not isinstance(payload, dict):
        return
    
    tmdb = payload.get('tmdb')
    if not isinstance(tmdb, dict):
        return
    
    api_key = tmdb.get('apiKey', '').strip() if isinstance(tmdb.get('apiKey'), str) else ''
    
    # 只有非空且非占位符时才保存
    if api_key and api_key != MASK_PLACEHOLDER:
        secret_store.set_secret('tmdb_api_key', api_key)
        import logging
        logging.getLogger(__name__).info('TMDB API Key 已保存到 SecretStore')


def _sync_emby_credentials_from_config(payload: dict, secret_store: SecretStore | None) -> None:
    """同步 Emby 凭证到 SecretStore"""
    if not secret_store or not isinstance(payload, dict):
        return
    
    emby = payload.get('emby')
    if not isinstance(emby, dict):
        return
    
    api_key = emby.get('apiKey', '').strip() if isinstance(emby.get('apiKey'), str) else ''
    server_url = emby.get('serverUrl', '').strip() if isinstance(emby.get('serverUrl'), str) else ''
    
    # 保存 API Key
    if api_key and api_key != MASK_PLACEHOLDER:
        secret_store.set_secret('emby_api_key', api_key)
    
    # 保存 Server URL（非敏感，但为了一致性也保存到数据库）
    if server_url:
        secret_store.set_secret('emby_server_url', server_url)


def _sync_proxy_credentials_from_config(payload: dict, secret_store: SecretStore | None) -> None:
    """同步 Proxy 凭证到 SecretStore"""
    if not secret_store or not isinstance(payload, dict):
        return
    
    proxy = payload.get('proxy')
    if not isinstance(proxy, dict):
        return
    
    password = proxy.get('password', '').strip() if isinstance(proxy.get('password'), str) else ''
    
    # 保存 password
    if password and password != MASK_PLACEHOLDER:
        secret_store.set_secret('proxy_password', password)


def _sync_telegram_credentials_from_config(payload: dict, secret_store: SecretStore | None) -> None:
    """同步 Telegram Bot Token 到 SecretStore"""
    if not secret_store or not isinstance(payload, dict):
        return
    
    telegram = payload.get('telegram')
    if not isinstance(telegram, dict):
        return
    
    bot_token = telegram.get('botToken', '').strip() if isinstance(telegram.get('botToken'), str) else ''
    
    if bot_token and bot_token != MASK_PLACEHOLDER:
        secret_store.set_secret('telegram_bot_token', bot_token)


def _populate_secrets_from_cache(config: dict, secrets_cache: dict) -> dict:
    """[性能优化] 使用预获取的缓存填充敏感字段，不再查询数据库。"""
    # 1. 115 Cookies
    cookies_json = secrets_cache.get('cloud115_cookies')
    if cookies_json:
        try:
            cookies = json.loads(cookies_json)
            if isinstance(cookies, dict):
                cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
                if 'cloud115' not in config:
                    config['cloud115'] = {}
                config['cloud115']['cookies'] = cookie_str
        except:
            pass

    # 2. 123 Password Credentials
    pwd_creds_json = secrets_cache.get('cloud123_password_credentials')
    if pwd_creds_json:
        try:
            creds = json.loads(pwd_creds_json)
            if 'cloud123' not in config:
                config['cloud123'] = {}
            if creds.get('passport'):
                config['cloud123']['passport'] = creds.get('passport')
            if creds.get('password'):
                config['cloud123']['password'] = creds.get('password')
        except:
            pass

    # 3. 123 OAuth Credentials
    oauth_creds_json = secrets_cache.get('cloud123_oauth_credentials')
    if oauth_creds_json:
        try:
            creds = json.loads(oauth_creds_json)
            if 'cloud123' not in config:
                config['cloud123'] = {}
            if creds.get('clientId'):
                config['cloud123']['clientId'] = creds.get('clientId')
            if creds.get('clientSecret'):
                config['cloud123']['clientSecret'] = creds.get('clientSecret')
        except:
            pass
            
    # 4. AI (LLM) Config
    llm_key = secrets_cache.get('llm_api_key')
    llm_base_url = secrets_cache.get('llm_base_url')
    llm_model = secrets_cache.get('llm_model')
    llm_provider = secrets_cache.get('llm_provider')
    
    if any([llm_key, llm_base_url, llm_model, llm_provider]):
        if 'organize' not in config:
            config['organize'] = {}
        if 'ai' not in config['organize']:
            config['organize']['ai'] = {}
            
        if llm_key:
            config['organize']['ai']['apiKey'] = llm_key
        if llm_base_url:
            config['organize']['ai']['baseUrl'] = llm_base_url
        if llm_model:
            config['organize']['ai']['model'] = llm_model
        if llm_provider:
            config['organize']['ai']['provider'] = llm_provider

    # 5. TMDB API Key
    tmdb_key = secrets_cache.get('tmdb_api_key')
    if tmdb_key:
        if 'tmdb' not in config:
            config['tmdb'] = {}
        config['tmdb']['apiKey'] = tmdb_key

    # 6. Emby Credentials
    emby_key = secrets_cache.get('emby_api_key')
    emby_url = secrets_cache.get('emby_server_url')
    if emby_key or emby_url:
        if 'emby' not in config:
            config['emby'] = {}
        if emby_key:
            config['emby']['apiKey'] = emby_key
        if emby_url:
            config['emby']['serverUrl'] = emby_url

    # 7. Proxy Password
    proxy_password = secrets_cache.get('proxy_password')
    if proxy_password:
        if 'proxy' not in config:
            config['proxy'] = {}
        config['proxy']['password'] = proxy_password

    # 8. Telegram Bot Token
    telegram_token = secrets_cache.get('telegram_bot_token')
    if telegram_token:
        if 'telegram' not in config:
            config['telegram'] = {}
        config['telegram']['botToken'] = telegram_token

    return config


def _add_session_flags_from_cache(config: dict, secrets_cache: dict) -> dict:
    """[性能优化] 使用预获取的缓存添加会话标志，不再查询数据库。"""
    # 115 Session
    cookies_json = secrets_cache.get('cloud115_cookies')
    if 'cloud115' not in config:
        config['cloud115'] = {}
    config['cloud115']['hasValidSession'] = bool(cookies_json)
    
    # 123 Session - check all credential types including password
    token_json = secrets_cache.get('cloud123_token')
    cookies_123_json = secrets_cache.get('cloud123_cookies')
    oauth_credentials = secrets_cache.get('cloud123_oauth_credentials')
    password_credentials = secrets_cache.get('cloud123_password_credentials')
    if 'cloud123' not in config:
        config['cloud123'] = {}
    config['cloud123']['hasValidSession'] = bool(token_json or cookies_123_json or oauth_credentials or password_credentials)
    
    return config


def _populate_secrets_to_config(config: dict, secret_store: SecretStore) -> dict:
    """Populate sensitive fields in config from SecretStore."""
    if not secret_store:
        return config
    
    # 1. 115 Cookies
    cookies_json = secret_store.get_secret('cloud115_cookies')
    if cookies_json:
        try:
            cookies = json.loads(cookies_json)
            if isinstance(cookies, dict):
                # Convert dict back to cookie string
                cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
                if 'cloud115' not in config:
                    config['cloud115'] = {}
                config['cloud115']['cookies'] = cookie_str
        except:
            pass

    # 2. 123 Password Credentials
    pwd_creds_json = secret_store.get_secret('cloud123_password_credentials')
    if pwd_creds_json:
        try:
            creds = json.loads(pwd_creds_json)
            if 'cloud123' not in config:
                config['cloud123'] = {}
            if creds.get('passport'):
                config['cloud123']['passport'] = creds.get('passport')
            if creds.get('password'):
                config['cloud123']['password'] = creds.get('password')
        except:
            pass

    # 3. 123 OAuth Credentials
    oauth_creds_json = secret_store.get_secret('cloud123_oauth_credentials')
    if oauth_creds_json:
        try:
            creds = json.loads(oauth_creds_json)
            if 'cloud123' not in config:
                config['cloud123'] = {}
            if creds.get('clientId'):
                config['cloud123']['clientId'] = creds.get('clientId')
            if creds.get('clientSecret'):
                config['cloud123']['clientSecret'] = creds.get('clientSecret')
        except:
            pass
            
    # 4. AI (LLM) Config
    llm_key = secret_store.get_secret('llm_api_key')
    llm_base_url = secret_store.get_secret('llm_base_url')
    llm_model = secret_store.get_secret('llm_model')
    llm_provider = secret_store.get_secret('llm_provider')
    
    if any([llm_key, llm_base_url, llm_model, llm_provider]):
        if 'organize' not in config:
            config['organize'] = {}
        if 'ai' not in config['organize']:
            config['organize']['ai'] = {}
            
        if llm_key:
            config['organize']['ai']['apiKey'] = llm_key
        if llm_base_url:
            config['organize']['ai']['baseUrl'] = llm_base_url
        if llm_model:
            config['organize']['ai']['model'] = llm_model
        if llm_provider:
            config['organize']['ai']['provider'] = llm_provider

    return config


# 定义敏感字段路径列表
SENSITIVE_FIELDS = [
    ['cloud115', 'cookies'],
    ['cloud123', 'clientSecret'],
    ['openList', 'password'],
    ['tmdb', 'apiKey'],
    ['telegram', 'botToken'],
    ['emby', 'apiKey'],
    ['proxy', 'password'],
    ['organize', 'ai', 'apiKey'],
]

MASK_PLACEHOLDER = '__MASKED__'

def _mask_sensitive_data(config: dict) -> dict:
    """Mask sensitive data in config dict."""
    masked = copy.deepcopy(config)
    
    for path in SENSITIVE_FIELDS:
        target = masked
        for key in path[:-1]:
            if isinstance(target, dict):
                target = target.get(key)
            else:
                target = None
                break
        
        if isinstance(target, dict) and path[-1] in target:
            val = target[path[-1]]
            if val and isinstance(val, str) and val.strip():
                target[path[-1]] = MASK_PLACEHOLDER
                
    return masked

def _unmask_sensitive_data(new_config: dict, old_config: dict) -> dict:
    """Restore masked data from old config."""
    restored = copy.deepcopy(new_config)
    
    for path in SENSITIVE_FIELDS:
        # 获取新配置中的值
        new_target = restored
        for key in path[:-1]:
            if isinstance(new_target, dict):
                new_target = new_target.get(key)
            else:
                new_target = None
                break
        
        # 获取旧配置中的值
        old_target = old_config
        for key in path[:-1]:
            if isinstance(old_target, dict):
                old_target = old_target.get(key)
            else:
                old_target = None
                break
                
        # 如果新值是占位符，且旧值存在，则恢复旧值
        if (isinstance(new_target, dict) and path[-1] in new_target and 
            new_target[path[-1]] == MASK_PLACEHOLDER):
            
            if (isinstance(old_target, dict) and path[-1] in old_target):
                new_target[path[-1]] = old_target[path[-1]]
            else:
                # 如果旧值不存在（奇怪的情况），则设为空或者保持原样
                new_target[path[-1]] = ''
                
    return restored


@config_bp.route('/config', methods=['GET'])
@optional_auth
def get_config():
    """Get application configuration with optional masking."""
    try:
        config = config_bp.store.get_config()

        # [性能优化] 一次性批量获取所有需要的秘密，避免多次数据库查询
        secrets_cache = {}
        if config_bp.secret_store:
            # 批量获取所有可能需要的 key（只查询一次数据库）
            secret_keys = [
                'cloud115_cookies',
                'cloud123_token',
                'cloud123_cookies', 
                'cloud123_oauth_credentials',
                'cloud123_password_credentials',
                'llm_api_key',
                'llm_base_url',
                'llm_model',
                'llm_provider',
                'tmdb_api_key',
                'emby_api_key',
                'emby_server_url',
                'proxy_password',
                'telegram_bot_token'
            ]
            # 使用批量查询，只创建一次数据库连接
            secrets_cache = config_bp.secret_store.get_secrets_batch(secret_keys)
        
        # Bootstrap SecretStore from persisted config (使用缓存)
        if config_bp.secret_store:
            # 同步115 cookies
            if not secrets_cache.get('cloud115_cookies'):
                cloud115 = config.get('cloud115') if isinstance(config, dict) else None
                if isinstance(cloud115, dict) and isinstance(cloud115.get('cookies'), str) and cloud115.get('cookies').strip():
                    _sync_cloud115_cookies_from_config(config, config_bp.secret_store)
                    secrets_cache['cloud115_cookies'] = config_bp.secret_store.get_secret('cloud115_cookies')
            
            # 同步123云盘凭证
            if not secrets_cache.get('cloud123_oauth_credentials'):
                cloud123 = config.get('cloud123') if isinstance(config, dict) else None
                if isinstance(cloud123, dict):
                    client_id = cloud123.get('clientId', '').strip() if isinstance(cloud123.get('clientId'), str) else ''
                    client_secret = cloud123.get('clientSecret', '').strip() if isinstance(cloud123.get('clientSecret'), str) else ''
                    if client_id and client_secret:
                        _sync_cloud123_credentials_from_config(config, config_bp.secret_store)
            
            # 同步 AI 凭证
            if not secrets_cache.get('llm_api_key'):
                 _sync_ai_credentials_from_config(config, config_bp.secret_store)
        
        # Populate secrets FROM cache TO config response (使用缓存，不再查询数据库)
        if config_bp.secret_store:
            config = _populate_secrets_from_cache(config, secrets_cache)
        
        # Add session health flags (使用缓存)
        config = _add_session_flags_from_cache(config, secrets_cache)
        
        # Mask sensitive data if 2FA is enabled
        if config.get('twoFactorSecret'):
            config = _mask_sensitive_data(config)
        
        return jsonify({
            'success': True,
            'data': config
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to retrieve config: {str(e)}'
        }), 500


@config_bp.route('/config', methods=['PUT', 'POST'])
@optional_auth
def update_config():
    """Update application configuration. Supports both PUT and POST methods."""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'success': False,
            'error': 'Config data is required'
        }), 400
    
    try:
        # 获取当前配置用于恢复被 mask 的数据
        current_config = config_bp.store.get_config()
        
        # 如果新配置中有 masked 数据，尝试还原
        final_config = _unmask_sensitive_data(data, current_config)
        
        # Update config in store (no masking, full round-trip)
        config_bp.store.update_config(final_config)

        # Sync 115 cookies from the config payload into SecretStore for real /api/115 usage
        _sync_cloud115_cookies_from_config(final_config, config_bp.secret_store)
        
        # Sync 123 cloud OAuth credentials into SecretStore
        _sync_cloud123_credentials_from_config(final_config, config_bp.secret_store)
        
        # Sync AI credentials
        _sync_ai_credentials_from_config(final_config, config_bp.secret_store)
        
        # Sync TMDB credentials
        _sync_tmdb_credentials_from_config(final_config, config_bp.secret_store)
        
        # Sync Emby credentials
        _sync_emby_credentials_from_config(final_config, config_bp.secret_store)
        
        # Sync Proxy credentials
        _sync_proxy_credentials_from_config(final_config, config_bp.secret_store)
        
        # Sync Telegram credentials
        _sync_telegram_credentials_from_config(final_config, config_bp.secret_store)
        
        # [Sync QPS Settings]
        try:
            from services.organize_worker import get_organize_worker
            from blueprints import cloud115, cloud123
            
            qps_115 = float(final_config.get('cloud115', {}).get('qps', 1.0))
            qps_123 = float(final_config.get('cloud123', {}).get('qps', 1.0))
            
            # 1. Update Organize Worker
            worker = get_organize_worker()
            if worker:
                worker.set_qps('115', qps_115)
                worker.set_qps('123', qps_123)
            
            # 2. Update Direct Cloud Services
            c115_svc = cloud115.get_service()
            if c115_svc:
                c115_svc.set_qps(qps_115)
                
            c123_svc = cloud123.get_service()
            if c123_svc:
                c123_svc.set_qps(qps_123)
                
        except Exception as qps_err:
            # Don't fail the request if QPS update fails, but log it
            import logging
            logging.getLogger(__name__).warning(f"Failed to sync QPS settings: {qps_err}")

        # Return updated config with session flags
        updated_config = config_bp.store.get_config()
        updated_config = _add_session_flags(updated_config, config_bp.secret_store)
        
        # Mask responsive data if needed
        if updated_config.get('twoFactorSecret'):
            updated_config = _mask_sensitive_data(updated_config)
        
        return jsonify({
            'success': True,
            'data': updated_config
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to update config: {str(e)}'
        }), 500


@config_bp.route('/me', methods=['GET'])
@optional_auth
def get_me():
    """Get current user information (alternative endpoint)."""
    from flask_jwt_extended import get_jwt_identity
    
    try:
        username = get_jwt_identity()
        if not username:
            username = 'admin'  # Default in dev mode
    except:
        username = 'admin'  # Default in dev mode
    
    two_factor_enabled = config_bp.store.is_two_factor_enabled()
    
    return jsonify({
        'success': True,
        'data': {
            'username': username,
            'twoFactorEnabled': two_factor_enabled
        }
    }), 200


@config_bp.route('/user/summary', methods=['GET'])
def user_summary():
    """Frontend compatibility alias for auth status."""
    from blueprints.auth import status as auth_status

    return auth_status()
