# utils/logger.py
# 应用日志系统 - 支持文件持久化、敏感数据脱敏、中文格式化

import os
import re
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


# === 敏感数据脱敏模式 ===
SENSITIVE_PATTERNS = [
    # API Keys (长字符串)
    (r'(["\']?(?:api[_-]?key|apikey|token|secret|password|pwd|cookie)["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]{8,})', r'\1***已脱敏***'),
    # JWT Token
    (r'(Bearer\s+)([a-zA-Z0-9._\-]+)', r'\1***TOKEN***'),
    # Cookie 值
    (r'(UID=|CID=|SEID=|acw_tc=)([a-zA-Z0-9_\-]+)', r'\1***'),
    # 邮箱
    (r'([a-zA-Z0-9._%+-]+)@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', r'***@\2'),
    # 手机号
    (r'(\d{3})\d{4}(\d{4})', r'\1****\2'),
]


def mask_sensitive_data(message: str) -> str:
    """对日志消息中的敏感数据进行脱敏处理"""
    result = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


# === 中文日志级别映射 ===
LEVEL_NAMES_CN = {
    'DEBUG': '调试',
    'INFO': '信息',
    'WARNING': '警告',
    'ERROR': '错误',
    'CRITICAL': '严重',
}


class ChineseFormatter(logging.Formatter):
    """中文格式化器，支持敏感数据脱敏"""
    
    def __init__(self, fmt=None, datefmt=None, mask_sensitive=True):
        super().__init__(fmt, datefmt)
        self.mask_sensitive = mask_sensitive
    
    def format(self, record):
        # 中文日志级别
        record.levelname_cn = LEVEL_NAMES_CN.get(record.levelname, record.levelname)
        
        # 模块名中文化
        module_names = {
            'app': '应用',
            'api': '接口',
            'tasks': '任务',
            'cloud': '云盘',
            'auth': '认证',
            'config': '配置',
            'emby': 'Emby',
            'strm': 'STRM',
            'bot': '机器人',
        }
        record.name_cn = module_names.get(record.name, record.name)
        
        # 格式化消息
        formatted = super().format(record)
        
        # 敏感数据脱敏
        if self.mask_sensitive:
            formatted = mask_sensitive_data(formatted)
        
        return formatted


def get_log_dir():
    """获取日志目录路径"""
    data_dir = os.environ.get('DATA_DIR')
    if not data_dir:
        # Try to find 'data' in current directory or backend directory
        if os.path.isdir('data'):
            data_dir = 'data'
        elif os.path.isdir('backend/data'):
            data_dir = 'backend/data'
        else:
            data_dir = '/data'
            
    log_dir = os.path.join(data_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def setup_logger(
    name: str = 'app',
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    mask_sensitive: bool = True
) -> logging.Logger:
    """
    配置应用日志器
    
    Args:
        name: 日志器名称
        level: 日志级别
        max_bytes: 单个日志文件最大大小
        backup_count: 保留的备份文件数量
        mask_sensitive: 是否对敏感数据脱敏
        
    Returns:
        配置好的日志器实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 中文格式化 - 控制台
    console_fmt = '%(asctime)s │ %(levelname_cn)-4s │ %(name_cn)-6s │ %(message)s'
    console_formatter = ChineseFormatter(console_fmt, datefmt='%H:%M:%S', mask_sensitive=mask_sensitive)
    
    # 中文格式化 - 文件
    file_fmt = '%(asctime)s │ %(levelname_cn)-4s │ %(name_cn)-6s │ %(message)s'
    file_formatter = ChineseFormatter(file_fmt, datefmt='%Y-%m-%d %H:%M:%S', mask_sensitive=mask_sensitive)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器
    try:
        log_dir = get_log_dir()
        log_file = os.path.join(log_dir, f'{name}.log')
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f'创建文件日志处理器失败: {e}')
    
    return logger


# === 预配置日志器 ===

def get_app_logger():
    """获取主应用日志器"""
    return setup_logger('app')


def get_api_logger():
    """获取接口请求日志器"""
    return setup_logger('api', level=logging.DEBUG)


def get_task_logger():
    """获取后台任务日志器"""
    return setup_logger('tasks')


def get_cloud_logger():
    """获取云盘服务日志器"""
    return setup_logger('cloud')


# === 任务日志辅助函数 ===

class TaskLogger:
    """任务执行日志器 - 记录任务启动、进度和结果"""
    
    def __init__(self, task_type: str, task_id: str = None):
        self.logger = get_task_logger()
        self.task_type = task_type
        self.task_id = task_id or datetime.now().strftime('%Y%m%d%H%M%S')
        self.start_time = None
    
    def start(self, description: str = None):
        """记录任务启动"""
        self.start_time = datetime.now()
        msg = f'[{self.task_type}] 任务开始 (ID: {self.task_id})'
        if description:
            msg += f' - {description}'
        self.logger.info(msg)
    
    def progress(self, current: int, total: int, message: str = None):
        """记录任务进度"""
        percent = int(current / total * 100) if total > 0 else 0
        bar = '█' * (percent // 5) + '░' * (20 - percent // 5)
        msg = f'[{self.task_type}] 进度: {bar} {percent}% ({current}/{total})'
        if message:
            msg += f' - {message}'
        self.logger.info(msg)
    
    def success(self, result: str = None):
        """记录任务成功"""
        elapsed = ''
        if self.start_time:
            delta = datetime.now() - self.start_time
            elapsed = f' (耗时: {delta.total_seconds():.2f}秒)'
        msg = f'[{self.task_type}] ✅ 任务完成{elapsed}'
        if result:
            msg += f' - {result}'
        self.logger.info(msg)
    
    def failure(self, error: str):
        """记录任务失败"""
        elapsed = ''
        if self.start_time:
            delta = datetime.now() - self.start_time
            elapsed = f' (耗时: {delta.total_seconds():.2f}秒)'
        self.logger.error(f'[{self.task_type}] ❌ 任务失败{elapsed} - {error}')
    
    def warning(self, message: str):
        """记录任务警告"""
        self.logger.warning(f'[{self.task_type}] ⚠️ {message}')
    
    def info(self, message: str):
        """记录任务信息"""
        self.logger.info(f'[{self.task_type}] {message}')


# === 操作日志辅助函数 ===

def log_operation(module: str, action: str, target: str = None, result: str = None, error: str = None):
    """
    记录用户操作日志
    
    Args:
        module: 模块名称 (如: 115网盘, Emby, 配置)
        action: 操作名称 (如: 登录, 保存, 刷新)
        target: 操作目标
        result: 操作结果
        error: 错误信息
    """
    logger = get_app_logger()
    
    msg = f'【{module}】{action}'
    if target:
        msg += f' -> {target}'
    
    if error:
        logger.error(f'{msg} ❌ 失败: {error}')
    elif result:
        logger.info(f'{msg} ✅ {result}')
    else:
        logger.info(msg)


def log_api_request(method: str, path: str, status: int, duration_ms: int = None, user: str = None):
    """记录 API 请求日志"""
    logger = get_api_logger()
    
    status_emoji = '✅' if 200 <= status < 300 else '⚠️' if 300 <= status < 500 else '❌'
    
    msg = f'{method} {path} {status_emoji} {status}'
    if duration_ms:
        msg += f' ({duration_ms}ms)'
    if user:
        msg += f' 用户: {user}'
    
    if status >= 500:
        logger.error(msg)
    elif status >= 400:
        logger.warning(msg)
    else:
        logger.info(msg)


# 默认日志器实例
app_logger = get_app_logger()


# === 任务日志装饰器 ===

def log_task(task_type: str, description: str = None):
    """
    装饰器：自动记录任务开始和结束
    
    用法:
        @log_task('离线下载', '创建下载任务')
        def create_offline_task(url, save_path):
            ...
    """
    import functools
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            task_logger = TaskLogger(task_type)
            task_logger.start(description or func.__name__)
            
            try:
                result = func(*args, **kwargs)
                
                # 判断结果是否成功
                if isinstance(result, dict):
                    if result.get('success') == False:
                        task_logger.failure(result.get('error', '未知错误'))
                    else:
                        task_logger.success(str(result.get('data', ''))[:100])
                else:
                    task_logger.success()
                
                return result
            except Exception as e:
                task_logger.failure(str(e))
                raise
        
        return wrapper
    return decorator


from contextlib import contextmanager

@contextmanager
def task_context(task_type: str, description: str = None):
    """
    上下文管理器：记录任务开始和结束
    
    用法:
        with task_context('115网盘', '列出目录'):
            result = cloud115_service.list_directory(cid)
    """
    task_logger = TaskLogger(task_type)
    task_logger.start(description)
    
    try:
        yield task_logger
        task_logger.success()
    except Exception as e:
        task_logger.failure(str(e))
        raise
