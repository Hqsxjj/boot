"""
缺集检测调度器
支持定时自动扫描和 Telegram 通知
"""
import threading
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from croniter import croniter

logger = logging.getLogger(__name__)


class MissingScanScheduler:
    """缺集检测定时调度器"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self._store = None
        self._emby_service = None
        self._telegram_bot = None
        self._subscription_service = None  # 新增：订阅服务
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_scan: Optional[datetime] = None
        self._next_scan: Optional[datetime] = None
        self._cron_expression: str = ""
        self._auto_subscribe: bool = False  # 新增：是否自动追剧
        self._auto_subscribe_cloud: str = "115"  # 新增：默认网盘
        
    def init(self, store, emby_service, telegram_bot=None, subscription_service=None):
        """初始化调度器"""
        self._store = store
        self._emby_service = emby_service
        self._telegram_bot = telegram_bot
        self._subscription_service = subscription_service
        self._load_config()
        logger.info("缺集检测调度器初始化完成")
    
    def _load_config(self):
        """从配置加载 Cron 表达式和自动追剧设置"""
        if not self._store:
            return
        try:
            config = self._store.get_config()
            emby_config = config.get('emby', {})
            missing_config = emby_config.get('missingEpisodes', {})
            self._cron_expression = missing_config.get('cronSchedule', '')
            self._auto_subscribe = missing_config.get('autoSubscribe', False)
            self._auto_subscribe_cloud = missing_config.get('autoSubscribeCloud', '115')
            
            if self._cron_expression:
                self._calculate_next_scan()
                logger.info(f"已加载 Cron 表达式: {self._cron_expression}, 下次扫描: {self._next_scan}")
            
            if self._auto_subscribe:
                logger.info(f"自动追剧已启用，目标网盘: {self._auto_subscribe_cloud}")
        except Exception as e:
            logger.error(f"加载缺集检测配置失败: {e}")
    
    def _calculate_next_scan(self):
        """计算下次扫描时间"""
        if not self._cron_expression:
            self._next_scan = None
            return
        
        try:
            cron = croniter(self._cron_expression, datetime.now())
            self._next_scan = cron.get_next(datetime)
        except Exception as e:
            logger.error(f"解析 Cron 表达式失败: {e}")
            self._next_scan = None
    
    def update_schedule(self, cron_expression: str):
        """更新定时计划"""
        self._cron_expression = cron_expression
        self._calculate_next_scan()
        
        if cron_expression:
            logger.info(f"更新缺集检测计划: {cron_expression}, 下次: {self._next_scan}")
        else:
            logger.info("缺集检测定时计划已禁用")
    
    def update_auto_subscribe(self, enabled: bool, cloud_type: str = "115"):
        """更新自动追剧设置"""
        self._auto_subscribe = enabled
        self._auto_subscribe_cloud = cloud_type
        logger.info(f"自动追剧设置: {'启用' if enabled else '禁用'}, 网盘: {cloud_type}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取调度状态"""
        return {
            'running': self._running,
            'cronExpression': self._cron_expression,
            'lastScan': self._last_scan.isoformat() if self._last_scan else None,
            'nextScan': self._next_scan.isoformat() if self._next_scan else None,
            'autoSubscribe': self._auto_subscribe,
            'autoSubscribeCloud': self._auto_subscribe_cloud
        }
    
    def start(self):
        """启动定时调度"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        logger.info("缺集检测调度器已启动")
    
    def stop(self):
        """停止定时调度"""
        self._running = False
        logger.info("缺集检测调度器已停止")
    
    def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            try:
                self._check_and_run_scheduled()
            except Exception as e:
                logger.error(f"调度检查异常: {e}")
            time.sleep(60)  # 每分钟检查一次
    
    def _check_and_run_scheduled(self):
        """检查并执行到期的扫描"""
        if not self._next_scan or not self._cron_expression:
            return
        
        if datetime.now() >= self._next_scan:
            logger.info("定时缺集扫描触发")
            self.run_scan(notify=True)
            self._calculate_next_scan()
    
    def run_scan(self, notify: bool = True) -> Dict[str, Any]:
        """
        执行缺集扫描
        
        Args:
            notify: 是否发送 Telegram 通知
        """
        if not self._emby_service:
            return {'success': False, 'error': '服务未初始化'}
        
        self._last_scan = datetime.now()
        
        try:
            # 调用扫描服务
            logger.info("开始执行缺集扫描...")
            result = self._emby_service.scan_missing_episodes()
            
            if result.get('success'):
                missing_data = result.get('data', [])
                
                # 发送 Telegram 通知
                if notify and self._telegram_bot and missing_data:
                    self._send_telegram_notification(missing_data)
                
                # 自动追剧：为每个缺集剧集创建订阅
                if self._auto_subscribe and self._subscription_service and missing_data:
                    self._create_auto_subscriptions(missing_data)
                
                return {'success': True, 'count': len(missing_data)}
            else:
                return {'success': False, 'error': result.get('error', '扫描失败')}
                
        except Exception as e:
            logger.error(f"缺集扫描异常: {e}")
            return {'success': False, 'error': str(e)}
    
    def _create_auto_subscriptions(self, missing_data: List[Dict]):
        """
        为缺集剧集自动创建订阅
        
        Args:
            missing_data: 缺集数据列表
        """
        if not self._subscription_service:
            return
        
        try:
            # 按剧集去重（一个剧可能有多季缺集）
            series_set = set()
            for item in missing_data:
                name = item.get('name', '')
                if name and name not in series_set:
                    series_set.add(name)
            
            created_count = 0
            for series_name in series_set:
                try:
                    # 创建订阅（使用剧集名作为关键词）
                    self._subscription_service.add_subscription(
                        keyword=series_name,
                        cloud_type=self._auto_subscribe_cloud,
                        filter_config={
                            'includeKeywords': [],
                            'excludeKeywords': ['预告', '花絮', 'OST', '原声'],
                            'autoDownload': True
                        }
                    )
                    created_count += 1
                    logger.info(f"✓ 自动创建订阅: {series_name}")
                except Exception as e:
                    logger.warning(f"创建订阅失败 [{series_name}]: {e}")
            
            logger.info(f"自动追剧完成: 创建 {created_count}/{len(series_set)} 个订阅")
            
        except Exception as e:
            logger.error(f"自动追剧异常: {e}")
    
    def _send_telegram_notification(self, missing_data: List[Dict]):
        """
        发送缺集检测结果到 Telegram
        
        消息格式:
        📺 缺集检测报告
        
        发现 X 个剧集有缺失集数:
        
        • 西部世界 S01: 缺 2 集 (E05,E08)
        • 权力的游戏 S03: 缺 3 集 (E01,E02,E04)
        ...
        """
        if not self._telegram_bot:
            return
        
        try:
            channel_id = self._telegram_bot.get_notification_channel()
            if not channel_id:
                logger.warning("未配置 Telegram 通知频道")
                return
            
            # 构建消息
            lines = ["📺 *缺集检测报告*\n"]
            lines.append(f"发现 *{len(missing_data)}* 个剧集季有缺失:\n")
            
            # 按剧集分组
            series_map = {}
            for item in missing_data:
                name = item.get('name', '未知')
                if name not in series_map:
                    series_map[name] = []
                series_map[name].append(item)
            
            # 格式化每个剧集
            for name, seasons in list(series_map.items())[:10]:  # 最多显示10个
                for s in seasons:
                    season = s.get('season', 0)
                    missing_eps = s.get('missing', s.get('missingEpisodes', ''))
                    count = s.get('missingCount', len(missing_eps.split(',')) if missing_eps else 0)
                    
                    # 截断过长的缺集列表
                    if len(missing_eps) > 20:
                        missing_eps = missing_eps[:17] + "..."
                    
                    lines.append(f"• *{name}* S{season:02d}: 缺 {count} 集 ({missing_eps})")
            
            if len(series_map) > 10:
                lines.append(f"\n...还有 {len(series_map) - 10} 个剧集")
            
            lines.append(f"\n⏰ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            
            message = "\n".join(lines)
            
            # 发送消息
            self._telegram_bot.send_message(channel_id, message, parse_mode='Markdown')
            logger.info("缺集检测报告已发送到 Telegram")
            
        except Exception as e:
            logger.error(f"发送 Telegram 通知失败: {e}")


# 全局单例
_scheduler: Optional[MissingScanScheduler] = None


def get_missing_scan_scheduler() -> MissingScanScheduler:
    """获取缺集检测调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = MissingScanScheduler()
    return _scheduler
