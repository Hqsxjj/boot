"""
封面定时生成调度器
定期根据保存的预设自动生成并上传媒体库封面
"""

import threading
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class ScheduleInterval(Enum):
    """定时间隔枚举"""
    HOURS_6 = "6h"
    HOURS_12 = "12h"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    DISABLED = "disabled"
    
    @classmethod
    def get_seconds(cls, interval: str) -> int:
        """获取间隔对应的秒数"""
        mapping = {
            "6h": 6 * 3600,
            "12h": 12 * 3600,
            "daily": 24 * 3600,
            "weekly": 7 * 24 * 3600,
            "monthly": 30 * 24 * 3600,
            "disabled": 0
        }
        return mapping.get(interval, 0)


# 海报排序规则
POSTER_SORT_OPTIONS = [
    {"id": "DateCreated,Descending", "name": "最新添加", "description": "按入库时间降序"},
    {"id": "DateCreated,Ascending", "name": "最早添加", "description": "按入库时间升序"},
    {"id": "SortName,Ascending", "name": "名称 A-Z", "description": "按名称字母顺序"},
    {"id": "SortName,Descending", "name": "名称 Z-A", "description": "按名称逆序"},
    {"id": "CommunityRating,Descending", "name": "评分最高", "description": "按评分降序"},
    {"id": "CommunityRating,Ascending", "name": "评分最低", "description": "按评分升序"},
    {"id": "PremiereDate,Descending", "name": "最新发行", "description": "按首播/上映日期降序"},
    {"id": "PremiereDate,Ascending", "name": "最早发行", "description": "按首播/上映日期升序"},
    {"id": "Random", "name": "随机", "description": "随机选择海报"},
    {"id": "PlayCount,Descending", "name": "最多播放", "description": "按播放次数降序"},
]


class CoverPreset:
    """封面生成预设"""
    
    def __init__(self, preset_id: str, name: str, config: Dict[str, Any]):
        self.preset_id = preset_id
        self.name = name
        self.library_ids: List[str] = config.get('libraryIds', [])
        self.poster_sort: str = config.get('posterSort', 'DateCreated,Descending')
        self.theme_index: int = config.get('themeIndex', -1)
        self.cover_format: str = config.get('format', 'png')
        self.poster_count: int = config.get('posterCount', 3)
        self.title_size: int = config.get('titleSize', 192)
        self.offset_x: int = config.get('offsetX', 40)
        self.poster_scale: int = config.get('posterScale', 30)
        self.v_align: int = config.get('vAlign', 60)
        self.spacing: float = config.get('spacing', 3.0)
        self.angle_scale: float = config.get('angleScale', 1.0)
        self.use_backdrop: bool = config.get('useBackdrop', False)
        self.generator_mode: str = config.get('generatorMode', 'classic')
        self.schedule_interval: str = config.get('scheduleInterval', 'disabled')
        self.last_run: Optional[datetime] = None
        self.created_at: datetime = datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            'presetId': self.preset_id,
            'name': self.name,
            'libraryIds': self.library_ids,
            'posterSort': self.poster_sort,
            'themeIndex': self.theme_index,
            'format': self.cover_format,
            'posterCount': self.poster_count,
            'titleSize': self.title_size,
            'offsetX': self.offset_x,
            'posterScale': self.poster_scale,
            'vAlign': self.v_align,
            'spacing': self.spacing,
            'angleScale': self.angle_scale,
            'useBackdrop': self.use_backdrop,
            'generatorMode': self.generator_mode,
            'scheduleInterval': self.schedule_interval,
            'lastRun': self.last_run.isoformat() if self.last_run else None,
            'createdAt': self.created_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CoverPreset':
        preset = cls(
            preset_id=data.get('presetId', ''),
            name=data.get('name', ''),
            config=data
        )
        if data.get('lastRun'):
            try:
                preset.last_run = datetime.fromisoformat(data['lastRun'])
            except:
                pass
        if data.get('createdAt'):
            try:
                preset.created_at = datetime.fromisoformat(data['createdAt'])
            except:
                pass
        return preset


class CoverScheduler:
    """封面定时生成调度器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._presets: Dict[str, CoverPreset] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._store = None
        self._cover_generator = None
        
    def init(self, store, cover_generator):
        """初始化调度器"""
        self._store = store
        self._cover_generator = cover_generator
        self._load_presets()
        
    def _load_presets(self):
        """从配置加载预设"""
        if not self._store:
            return
        try:
            config = self._store.get_config()
            presets_data = config.get('coverScheduler', {}).get('presets', [])
            with self._lock:
                self._presets.clear()
                for data in presets_data:
                    preset = CoverPreset.from_dict(data)
                    self._presets[preset.preset_id] = preset
            logger.info(f"已加载 {len(self._presets)} 个封面预设")
        except Exception as e:
            logger.error(f"加载封面预设失败: {e}")
    
    def _save_presets(self):
        """保存预设到配置"""
        if not self._store:
            return
        try:
            with self._lock:
                presets_data = [p.to_dict() for p in self._presets.values()]
            
            config = self._store.get_config()
            if 'coverScheduler' not in config:
                config['coverScheduler'] = {}
            config['coverScheduler']['presets'] = presets_data
            self._store.save_config(config)
            logger.info(f"已保存 {len(presets_data)} 个封面预设")
        except Exception as e:
            logger.error(f"保存封面预设失败: {e}")
    
    def add_preset(self, name: str, config: Dict[str, Any]) -> CoverPreset:
        """添加新预设"""
        import uuid
        preset_id = str(uuid.uuid4())[:8]
        preset = CoverPreset(preset_id, name, config)
        
        with self._lock:
            self._presets[preset_id] = preset
        
        self._save_presets()
        logger.info(f"已添加封面预设: {name} ({preset_id})")
        return preset
    
    def update_preset(self, preset_id: str, config: Dict[str, Any]) -> Optional[CoverPreset]:
        """更新预设"""
        with self._lock:
            if preset_id not in self._presets:
                return None
            old_preset = self._presets[preset_id]
            new_preset = CoverPreset(preset_id, config.get('name', old_preset.name), config)
            new_preset.created_at = old_preset.created_at
            new_preset.last_run = old_preset.last_run
            self._presets[preset_id] = new_preset
        
        self._save_presets()
        logger.info(f"已更新封面预设: {preset_id}")
        return new_preset
    
    def delete_preset(self, preset_id: str) -> bool:
        """删除预设"""
        with self._lock:
            if preset_id not in self._presets:
                return False
            del self._presets[preset_id]
        
        self._save_presets()
        logger.info(f"已删除封面预设: {preset_id}")
        return True
    
    def get_presets(self) -> List[Dict[str, Any]]:
        """获取所有预设"""
        with self._lock:
            return [p.to_dict() for p in self._presets.values()]
    
    def get_preset(self, preset_id: str) -> Optional[Dict[str, Any]]:
        """获取指定预设"""
        with self._lock:
            preset = self._presets.get(preset_id)
            return preset.to_dict() if preset else None
    
    def run_preset(self, preset_id: str) -> Dict[str, Any]:
        """立即执行预设"""
        with self._lock:
            preset = self._presets.get(preset_id)
            if not preset:
                return {'success': False, 'error': '预设不存在'}
        
        try:
            result = self._execute_preset(preset)
            preset.last_run = datetime.now()
            self._save_presets()
            return result
        except Exception as e:
            logger.error(f"执行预设失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _execute_preset(self, preset: CoverPreset) -> Dict[str, Any]:
        """执行预设生成封面"""
        if not self._cover_generator or not self._store:
            return {'success': False, 'error': '服务未初始化'}
        
        results = []
        success_count = 0
        
        for lib_id in preset.library_ids:
            try:
                # 获取海报 (使用排序规则)
                posters = self._cover_generator.get_library_posters(
                    lib_id, 
                    limit=preset.poster_count * 2,
                    sort_by=preset.poster_sort
                )
                
                if not posters:
                    results.append({'id': lib_id, 'success': False, 'msg': '无可用海报'})
                    continue
                
                # 生成封面
                gen_kwargs = {
                    'theme_index': preset.theme_index,
                    'title_size': preset.title_size,
                    'offset_x': preset.offset_x,
                    'poster_scale': preset.poster_scale / 100.0,
                    'v_align': preset.v_align / 100.0,
                    'card_spacing': preset.spacing,
                    'angle_scale': preset.angle_scale,
                }
                
                if preset.cover_format == 'gif':
                    image_data = self._cover_generator.generate_animated_cover(
                        posters[:preset.poster_count],
                        frame_count=preset.poster_count * 4,
                        duration_ms=150,
                        **gen_kwargs
                    )
                else:
                    img = self._cover_generator.generate_cover(
                        posters[:preset.poster_count],
                        **gen_kwargs
                    )
                    import io
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    image_data = buffer.getvalue()
                
                # 上传到 Emby
                content_type = 'image/png'
                if self._cover_generator.upload_cover(lib_id, image_data, content_type):
                    # 4. 刷新 Emby 项目以清除缓存
                    try:
                        from services.emby_service import get_emby_service
                        emby_service = get_emby_service(self._store)
                        if emby_service:
                            emby_service.refresh_item(lib_id)
                    except Exception as e:
                        logger.warning(f"刷新库 {lib_id} 缓存失败: {e}")
                    
                    success_count += 1
                    results.append({'id': lib_id, 'success': True})
                else:
                    results.append({'id': lib_id, 'success': False, 'msg': '上传失败'})
                    
            except Exception as e:
                logger.error(f"处理库 {lib_id} 失败: {e}")
                results.append({'id': lib_id, 'success': False, 'msg': str(e)})
        
        return {
            'success': True,
            'processed': len(preset.library_ids),
            'successCount': success_count,
            'details': results
        }
    
    def start(self):
        """启动定时调度"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._thread.start()
        logger.info("封面定时调度器已启动")
    
    def stop(self):
        """停止定时调度"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("封面定时调度器已停止")
    
    def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            try:
                self._check_and_run_scheduled()
            except Exception as e:
                logger.error(f"调度循环错误: {e}")
            
            # 每分钟检查一次
            time.sleep(60)
    
    def _check_and_run_scheduled(self):
        """检查并执行到期的预设"""
        now = datetime.now()
        
        with self._lock:
            presets_to_run = []
            for preset in self._presets.values():
                if preset.schedule_interval == 'disabled':
                    continue
                
                interval_seconds = ScheduleInterval.get_seconds(preset.schedule_interval)
                if interval_seconds == 0:
                    continue
                
                # 检查是否到期
                if preset.last_run is None:
                    presets_to_run.append(preset)
                else:
                    next_run = preset.last_run + timedelta(seconds=interval_seconds)
                    if now >= next_run:
                        presets_to_run.append(preset)
        
        # 在锁外执行，避免长时间持锁
        for preset in presets_to_run:
            logger.info(f"执行定时任务: {preset.name}")
            try:
                self._execute_preset(preset)
                preset.last_run = now
            except Exception as e:
                logger.error(f"定时任务执行失败: {preset.name} - {e}")
        
        if presets_to_run:
            self._save_presets()


# 全局单例
_scheduler: Optional[CoverScheduler] = None


def get_cover_scheduler() -> CoverScheduler:
    """获取封面调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = CoverScheduler()
    return _scheduler


def get_poster_sort_options() -> List[Dict[str, str]]:
    """获取海报排序选项列表"""
    return POSTER_SORT_OPTIONS
