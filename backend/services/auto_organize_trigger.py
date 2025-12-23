"""
自动整理触发服务

当以下事件发生时自动触发整理工作流：
1. 离线下载完成
2. 转存分享成功
3. 资源搜索转存成功

整理失败的文件会被移动到"待手动整理"文件夹
"""
import logging
import threading
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AutoOrganizeTrigger:
    """
    自动整理触发器 - 单例模式
    
    监听各种下载/转存完成事件，自动触发整理流程
    """
    
    _instance = None
    _lock = threading.Lock()
    
    # 待手动整理的文件夹名称
    MANUAL_FOLDER_NAME = '待手动整理'
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self._enabled = True
        self._cloud115_service = None
        self._cloud123_service = None
        self._media_organizer = None
        self._config_store = None
        
        # 事件回调列表
        self._on_organize_callbacks: List[Callable] = []
        
        logger.info('AutoOrganizeTrigger 初始化完成')
    
    def set_services(self, cloud115_service=None, cloud123_service=None, 
                     media_organizer=None, config_store=None):
        """设置依赖的服务"""
        if cloud115_service:
            self._cloud115_service = cloud115_service
        if cloud123_service:
            self._cloud123_service = cloud123_service
        if media_organizer:
            self._media_organizer = media_organizer
        if config_store:
            self._config_store = config_store
    
    def is_enabled(self) -> bool:
        """检查自动整理是否启用"""
        if not self._config_store:
            return self._enabled
        
        try:
            config = self._config_store.get_config()
            return config.get('organize', {}).get('enabled', True)
        except:
            return self._enabled
    
    def set_enabled(self, enabled: bool):
        """设置启用状态"""
        self._enabled = enabled
    
    def add_callback(self, callback: Callable):
        """添加整理事件回调"""
        self._on_organize_callbacks.append(callback)
    
    def _notify_callbacks(self, event_type: str, data: Dict[str, Any]):
        """通知所有回调"""
        for callback in self._on_organize_callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.warning(f'整理回调执行失败: {e}')
    
    def trigger_from_offline_download(
        self,
        cloud_type: str,
        file_id: str,
        file_name: str,
        source_dir: str,
        task_id: str = None
    ) -> Dict[str, Any]:
        """
        离线下载完成后触发整理
        
        Args:
            cloud_type: '115' 或 '123'
            file_id: 文件ID
            file_name: 文件名
            source_dir: 文件所在目录
            task_id: 离线任务ID
        
        Returns:
            整理结果
        """
        if not self.is_enabled():
            logger.debug('自动整理已禁用，跳过触发')
            return {'success': True, 'skipped': True, 'reason': '自动整理已禁用'}
        
        logger.info(f'离线下载完成，触发整理: {file_name} ({cloud_type})')
        
        return self._do_organize(
            cloud_type=cloud_type,
            file_id=file_id,
            file_name=file_name,
            source_dir=source_dir,
            trigger_type='offline_download'
        )
    
    def trigger_from_share_save(
        self,
        cloud_type: str,
        file_ids: List[str],
        file_names: List[str],
        target_dir: str,
        share_code: str = None
    ) -> Dict[str, Any]:
        """
        转存分享成功后触发整理
        
        Args:
            cloud_type: '115' 或 '123'
            file_ids: 文件ID列表
            file_names: 文件名列表
            target_dir: 保存目录
            share_code: 分享码
        
        Returns:
            整理结果
        """
        if not self.is_enabled():
            logger.debug('自动整理已禁用，跳过触发')
            return {'success': True, 'skipped': True, 'reason': '自动整理已禁用'}
        
        logger.info(f'转存成功，触发整理: {len(file_ids)} 个文件 ({cloud_type})')
        
        results = []
        for file_id, file_name in zip(file_ids, file_names):
            result = self._do_organize(
                cloud_type=cloud_type,
                file_id=file_id,
                file_name=file_name,
                source_dir=target_dir,
                trigger_type='share_save'
            )
            results.append(result)
        
        success_count = sum(1 for r in results if r.get('success'))
        failed_count = len(results) - success_count
        
        return {
            'success': failed_count == 0,
            'total': len(results),
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results
        }
    
    def _do_organize(
        self,
        cloud_type: str,
        file_id: str,
        file_name: str,
        source_dir: str,
        trigger_type: str
    ) -> Dict[str, Any]:
        """
        执行单个文件的整理
        
        Args:
            cloud_type: 云盘类型
            file_id: 文件ID
            file_name: 原始文件名
            source_dir: 源目录
            trigger_type: 触发类型
        
        Returns:
            整理结果
        """
        from services.organize_log_service import get_organize_log_service
        organize_log = get_organize_log_service()
        
        try:
            if not self._media_organizer:
                error = '媒体整理器未初始化'
                organize_log.log_failure(
                    source_dir=source_dir,
                    original_name=file_name,
                    new_name='',
                    target_path='',
                    error=error,
                    cloud_type=cloud_type
                )
                return {'success': False, 'error': error}
            
            # 调用媒体整理器处理文件
            result = self._media_organizer.organize_single_file(
                cloud_type=cloud_type,
                file_id=file_id,
                file_name=file_name,
                source_dir=source_dir
            )
            
            if result.get('success'):
                # 记录成功日志
                organize_log.log_success(
                    source_dir=source_dir,
                    original_name=file_name,
                    new_name=result.get('new_name', file_name),
                    target_path=result.get('target_path', ''),
                    cloud_type=cloud_type
                )
                
                # 通知回调
                self._notify_callbacks('organize_success', {
                    'file_name': file_name,
                    'new_name': result.get('new_name'),
                    'target_path': result.get('target_path'),
                    'cloud_type': cloud_type,
                    'trigger_type': trigger_type
                })
                
                return result
            else:
                # 记录失败日志
                error = result.get('error', '整理失败')
                organize_log.log_failure(
                    source_dir=source_dir,
                    original_name=file_name,
                    new_name=result.get('new_name', ''),
                    target_path='',
                    error=error,
                    cloud_type=cloud_type
                )
                
                # 移动到待手动整理文件夹
                self._move_to_manual_folder(
                    cloud_type=cloud_type,
                    file_id=file_id,
                    source_dir=source_dir
                )
                
                return result
                
        except Exception as e:
            error = str(e)
            logger.error(f'自动整理异常: {error}')
            
            organize_log.log_failure(
                source_dir=source_dir,
                original_name=file_name,
                new_name='',
                target_path='',
                error=error,
                cloud_type=cloud_type
            )
            
            # 尝试移动到待手动整理文件夹
            try:
                self._move_to_manual_folder(
                    cloud_type=cloud_type,
                    file_id=file_id,
                    source_dir=source_dir
                )
            except:
                pass
            
            return {'success': False, 'error': error}
    
    def _move_to_manual_folder(
        self,
        cloud_type: str,
        file_id: str,
        source_dir: str
    ):
        """将失败的文件移动到待手动整理文件夹"""
        try:
            if cloud_type == '115' and self._cloud115_service:
                # 在源目录下创建待手动整理文件夹
                result = self._cloud115_service.create_directory(
                    parent_cid=source_dir,
                    name=self.MANUAL_FOLDER_NAME
                )
                
                if result.get('success'):
                    manual_cid = result.get('data', {}).get('id')
                    if manual_cid:
                        # 移动文件
                        self._cloud115_service.move_file(file_id, manual_cid)
                        logger.info(f'文件已移动到待手动整理文件夹: {file_id}')
                        
            elif cloud_type == '123' and self._cloud123_service:
                result = self._cloud123_service.create_directory(
                    parent_id=source_dir,
                    name=self.MANUAL_FOLDER_NAME
                )
                
                if result.get('success'):
                    manual_id = result.get('data', {}).get('id')
                    if manual_id:
                        self._cloud123_service.move_file(file_id, manual_id)
                        logger.info(f'文件已移动到待手动整理文件夹: {file_id}')
                        
        except Exception as e:
            logger.warning(f'移动到待手动整理文件夹失败: {e}')


# 全局单例
_auto_organize_trigger: Optional[AutoOrganizeTrigger] = None


def get_auto_organize_trigger() -> AutoOrganizeTrigger:
    """获取自动整理触发器单例"""
    global _auto_organize_trigger
    if _auto_organize_trigger is None:
        _auto_organize_trigger = AutoOrganizeTrigger()
    return _auto_organize_trigger
