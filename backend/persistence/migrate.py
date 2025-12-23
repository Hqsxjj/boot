"""
数据迁移工具 - 从 JSON/YAML 文件迁移到数据库

使用方法:
    python -m persistence.migrate
"""
import os
import json
import yaml
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_config_yaml_to_db(session_factory, yaml_path: str = '/data/config.yml'):
    """迁移 config.yml 到数据库"""
    from persistence.db_config_store import DbConfigStore
    
    if not os.path.exists(yaml_path):
        logger.info(f"配置文件不存在，跳过迁移: {yaml_path}")
        return
    
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        
        if not config:
            logger.info("配置文件为空，跳过迁移")
            return
        
        db_store = DbConfigStore(session_factory)
        db_store.update_config(config)
        
        logger.info(f"成功迁移配置文件到数据库: {yaml_path}")
        
        # 备份原文件
        backup_path = yaml_path + '.migrated.bak'
        os.rename(yaml_path, backup_path)
        logger.info(f"原文件已备份到: {backup_path}")
        
    except Exception as e:
        logger.error(f"迁移配置文件失败: {e}")


def migrate_appdata_json_to_db(session_factory, secret_store, json_path: str = '/data/appdata.json'):
    """迁移 appdata.json 中的管理员凭证到数据库"""
    if not os.path.exists(json_path):
        logger.info(f"数据文件不存在，跳过迁移: {json_path}")
        return
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        admin_data = data.get('admin', {})
        
        # 迁移密码哈希
        password_hash = admin_data.get('password_hash')
        if password_hash:
            secret_store.set_secret('admin_password_hash', password_hash)
            logger.info("已迁移管理员密码哈希")
        
        # 迁移 2FA 秘钥
        two_factor_secret = admin_data.get('two_factor_secret')
        if two_factor_secret:
            secret_store.set_secret('admin_2fa_secret', two_factor_secret)
            logger.info("已迁移 2FA 秘钥")
        
        # 备份原文件
        backup_path = json_path + '.migrated.bak'
        os.rename(json_path, backup_path)
        logger.info(f"原文件已备份到: {backup_path}")
        
    except Exception as e:
        logger.error(f"迁移管理员数据失败: {e}")


def migrate_subscriptions_to_db(session_factory, data_dir: str = '/data'):
    """迁移订阅数据到数据库"""
    from persistence.db_subscription_store import DbSubscriptionStore
    import uuid
    
    files = [
        ('subscriptions.json', 'subscriptions'),
        ('subscription_history.json', 'history'),
        ('subscription_settings.json', 'settings'),
    ]
    
    db_store = DbSubscriptionStore(session_factory)
    
    for filename, data_type in files:
        file_path = os.path.join(data_dir, filename)
        if not os.path.exists(file_path):
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data_type == 'subscriptions' and isinstance(data, list):
                for sub in data:
                    db_store.add_subscription(
                        keyword=sub.get('keyword', ''),
                        cloud_type=sub.get('cloud_type', '115'),
                        filter_config=sub.get('filter_config', {})
                    )
                logger.info(f"已迁移 {len(data)} 个订阅")
            
            elif data_type == 'settings' and isinstance(data, dict):
                db_store.update_settings(data)
                logger.info("已迁移订阅设置")
            
            # 备份
            backup_path = file_path + '.migrated.bak'
            os.rename(file_path, backup_path)
            logger.info(f"原文件已备份到: {backup_path}")
            
        except Exception as e:
            logger.error(f"迁移 {filename} 失败: {e}")


def migrate_sources_to_db(session_factory, data_dir: str = '/data'):
    """迁移来源数据到数据库"""
    from persistence.db_source_store import DbSourceStore
    
    files = [
        'sources.json',
        'crawled_resources.json',
    ]
    
    db_store = DbSourceStore(session_factory)
    
    for filename in files:
        file_path = os.path.join(data_dir, filename)
        if not os.path.exists(file_path):
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if filename == 'sources.json' and isinstance(data, list):
                for source in data:
                    db_store.add_source(
                        source_type=source.get('type', 'website'),
                        url=source.get('url', ''),
                        name=source.get('name')
                    )
                logger.info(f"已迁移 {len(data)} 个来源")
            
            elif filename == 'crawled_resources.json':
                resources = data.get('resources', []) if isinstance(data, dict) else data
                if resources:
                    # 按来源分组添加
                    by_source = {}
                    for r in resources:
                        sid = r.get('source_id', 'unknown')
                        if sid not in by_source:
                            by_source[sid] = []
                        by_source[sid].append(r)
                    
                    for source_id, source_resources in by_source.items():
                        db_store.add_crawled_resources_batch(source_id, source_resources)
                    
                    logger.info(f"已迁移 {len(resources)} 个抓取资源")
            
            # 备份
            backup_path = file_path + '.migrated.bak'
            os.rename(file_path, backup_path)
            logger.info(f"原文件已备份到: {backup_path}")
            
        except Exception as e:
            logger.error(f"迁移 {filename} 失败: {e}")


def run_all_migrations(appdata_session_factory, secret_store, data_dir: str = '/data'):
    """运行所有迁移"""
    logger.info("=" * 50)
    logger.info("开始数据迁移...")
    logger.info("=" * 50)
    
    # 迁移配置
    config_yaml = os.path.join(data_dir, 'config.yml')
    migrate_config_yaml_to_db(appdata_session_factory, config_yaml)
    
    # 迁移管理员数据
    appdata_json = os.path.join(data_dir, 'appdata.json')
    migrate_appdata_json_to_db(appdata_session_factory, secret_store, appdata_json)
    
    # 迁移订阅
    migrate_subscriptions_to_db(appdata_session_factory, data_dir)
    
    # 迁移来源
    migrate_sources_to_db(appdata_session_factory, data_dir)
    
    logger.info("=" * 50)
    logger.info("数据迁移完成!")
    logger.info("=" * 50)


if __name__ == '__main__':
    """命令行运行迁移"""
    from models.database import init_all_databases, get_session_factory
    from services.secret_store import SecretStore
    
    # 初始化数据库
    secrets_engine, appdata_engine = init_all_databases()
    secrets_session_factory = get_session_factory(secrets_engine)
    appdata_session_factory = get_session_factory(appdata_engine)
    secret_store = SecretStore(secrets_session_factory)
    
    # 运行迁移
    data_dir = os.environ.get('DATA_DIR', '/data')
    run_all_migrations(appdata_session_factory, secret_store, data_dir)
