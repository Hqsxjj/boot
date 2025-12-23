import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

# 创建两个独立的 Base，分别对应两个数据库
SecretsBase = declarative_base()  # 敏感数据 (secrets.db)
AppDataBase = declarative_base()  # 普通数据 (appdata.db)

# 保持向后兼容
Base = SecretsBase


def get_data_dir():
    """Get data directory path."""
    # Default to 'data' in current working directory if DATA_DIR is not set
    # This ensures persistence works in development (c:\boot\data) and
    # in Docker if the working dir is volume mounted (e.g. /app/data)
    default_dir = os.path.join(os.getcwd(), 'data')
    data_dir = os.environ.get('DATA_DIR', default_dir)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_secrets_db_url():
    """Get secrets database URL (encrypted sensitive data)."""
    database_url = os.environ.get('SECRETS_DATABASE_URL')
    if database_url:
        return database_url
    
    # Fallback to legacy DATABASE_URL for backward compatibility
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        return database_url
    
    data_dir = get_data_dir()
    return f'sqlite:///{data_dir}/secrets.db'


def get_appdata_db_url():
    """Get appdata database URL (non-sensitive application data)."""
    database_url = os.environ.get('APPDATA_DATABASE_URL')
    if database_url:
        return database_url
    
    data_dir = get_data_dir()
    return f'sqlite:///{data_dir}/appdata.db'


# 保持向后兼容
def get_database_url():
    """Get database URL from environment or use default SQLite (legacy)."""
    return get_secrets_db_url()


def _create_engine(database_url):
    """Create SQLAlchemy engine with appropriate settings."""
    if 'sqlite' in database_url:
        return create_engine(
            database_url,
            connect_args={'check_same_thread': False},
            poolclass=StaticPool
        )
    return create_engine(database_url)


def init_secrets_db():
    """Initialize secrets database for encrypted sensitive data."""
    database_url = get_secrets_db_url()
    engine = _create_engine(database_url)
    # Use checkfirst=True to avoid race conditions when multiple workers initialize
    SecretsBase.metadata.create_all(engine, checkfirst=True)
    return engine


def init_appdata_db():
    """Initialize appdata database for non-sensitive application data."""
    database_url = get_appdata_db_url()
    engine = _create_engine(database_url)
    # Use checkfirst=True to avoid race conditions when multiple workers initialize
    AppDataBase.metadata.create_all(engine, checkfirst=True)
    return engine


def init_db():
    """Initialize database and create all tables (legacy, uses secrets db)."""
    return init_secrets_db()


def init_all_databases():
    """Initialize all databases and return both engines."""
    secrets_engine = init_secrets_db()
    appdata_engine = init_appdata_db()
    return secrets_engine, appdata_engine


def get_session_factory(engine):
    """Get SQLAlchemy session factory."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

