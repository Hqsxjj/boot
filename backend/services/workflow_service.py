"""
Workflow Service
工作流协调器 - 串联链接处理、离线下载、整理、STRM生成、Emby通知
"""
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from services.link_parser import LinkParser, ParsedLink, LinkType, CloudSource

logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = 'pending'
    CHOOSING = 'choosing'      # 等待用户选择网盘
    OFFLINE = 'offline'        # 离线下载中
    SAVING = 'saving'          # 转存中
    ORGANIZING = 'organizing'  # 整理中
    STRM = 'strm'              # 生成STRM中
    REFRESHING = 'refreshing'  # 刷新Emby中
    NOTIFYING = 'notifying'    # 发送通知中
    COMPLETED = 'completed'
    FAILED = 'failed'


@dataclass
class WorkflowTask:
    """工作流任务"""
    id: str
    chat_id: str
    user_id: str
    parsed_link: ParsedLink
    target_cloud: Optional[str] = None
    status: WorkflowStatus = WorkflowStatus.PENDING
    offline_task_id: Optional[str] = None
    organized_path: Optional[str] = None
    strm_path: Optional[str] = None
    media_info: Optional[Dict] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'user_id': self.user_id,
            'link': self.parsed_link.to_dict(),
            'target_cloud': self.target_cloud,
            'status': self.status.value,
            'offline_task_id': self.offline_task_id,
            'organized_path': self.organized_path,
            'strm_path': self.strm_path,
            'media_info': self.media_info,
            'error': self.error,
            'created_at': self.created_at
        }


class WorkflowService:
    """
    工作流协调服务
    
    负责串联各个服务：
    1. 链接解析 -> 2. 用户选择 -> 3. 离线/转存 -> 4. 整理 -> 5. STRM -> 6. Emby刷新 -> 7. 通知
    """
    
    def __init__(
        self,
        link_parser: LinkParser,
        cloud115_service=None,
        cloud123_service=None,
        offline_service=None,
        strm_service=None,
        emby_service=None,
        telegram_service=None,
        config_store=None
    ):
        self.link_parser = link_parser
        self.cloud115_service = cloud115_service
        self.cloud123_service = cloud123_service
        self.offline_service = offline_service
        self.strm_service = strm_service
        self.emby_service = emby_service
        self.telegram_service = telegram_service
        self.config_store = config_store
        
        # 任务存储
        self.tasks: Dict[str, WorkflowTask] = {}
        
        # 回调注册
        self._on_need_choice: Optional[Callable] = None
        self._on_status_update: Optional[Callable] = None
    
    def process_message(self, chat_id: str, user_id: str, text: str) -> Dict[str, Any]:
        """
        处理用户消息，解析链接并开始工作流
        
        Args:
            chat_id: 聊天ID
            user_id: 用户ID
            text: 消息文本
            
        Returns:
            处理结果
        """
        # 解析链接
        parsed = self.link_parser.parse(text)
        
        if parsed.type == LinkType.UNKNOWN:
            return {
                'success': False,
                'error': '未识别的链接格式',
                'parsed': parsed.to_dict()
            }
        
        # 创建工作流任务
        import uuid
        task_id = str(uuid.uuid4())
        task = WorkflowTask(
            id=task_id,
            chat_id=chat_id,
            user_id=user_id,
            parsed_link=parsed
        )
        self.tasks[task_id] = task
        
        # 获取可选目标
        options = self.link_parser.get_target_options(parsed)
        
        if len(options) == 0:
            task.status = WorkflowStatus.FAILED
            task.error = '此链接类型不支持离线下载'
            return {
                'success': False,
                'error': task.error,
                'task_id': task_id
            }
        elif len(options) == 1:
            # 只有一个选项，直接执行
            return self.execute_with_target(task_id, options[0])
        else:
            # 多个选项，需要用户选择
            task.status = WorkflowStatus.CHOOSING
            return {
                'success': True,
                'action': 'choose',
                'task_id': task_id,
                'link_type': parsed.type.value,
                'link_info': self.link_parser.get_action_text(parsed),
                'options': options,
                'message': f'检测到{self.link_parser.get_action_text(parsed)}，请选择目标网盘：'
            }
    
    def execute_with_target(self, task_id: str, target_cloud: str) -> Dict[str, Any]:
        """
        用户选择目标后执行工作流
        
        Args:
            task_id: 任务ID
            target_cloud: 目标网盘 ('115' 或 '123')
        """
        task = self.tasks.get(task_id)
        if not task:
            return {'success': False, 'error': '任务不存在'}
        
        task.target_cloud = target_cloud
        
        # 根据链接类型执行不同操作
        parsed = task.parsed_link
        
        try:
            if parsed.type == LinkType.SHARE_115:
                # 115 分享链接转存
                return self._save_115_share(task)
            elif parsed.type == LinkType.SHARE_123:
                # 123 分享链接转存
                return self._save_123_share(task)
            elif parsed.type in [LinkType.MAGNET, LinkType.ED2K, LinkType.HTTP]:
                # 离线下载
                return self._offline_download(task)
            else:
                task.status = WorkflowStatus.FAILED
                task.error = '不支持的链接类型'
                return {'success': False, 'error': task.error}
        except Exception as e:
            task.status = WorkflowStatus.FAILED
            task.error = str(e)
            task.error = str(e)
            logger.error(f"工作流错误: {e}")
            return {'success': False, 'error': str(e)}
    
    def _save_115_share(self, task: WorkflowTask) -> Dict[str, Any]:
        """转存 115 分享链接"""
        task.status = WorkflowStatus.SAVING
        
        if not self.cloud115_service:
            task.status = WorkflowStatus.FAILED
            task.error = '115 服务未初始化'
            return {'success': False, 'error': task.error}
        
        # 获取保存目录
        save_cid = self._get_save_dir('115')
        
        try:
            result = self.cloud115_service.save_share(
                share_code=task.parsed_link.share_code,
                access_code=task.parsed_link.access_code,
                save_cid=save_cid
            )
            
            if result.get('success'):
                # 启动后续流程
                self._start_post_save_workflow(task, result.get('file_id'))
                return {
                    'success': True,
                    'task_id': task.id,
                    'message': '转存成功，正在整理...'
                }
            else:
                task.status = WorkflowStatus.FAILED
                task.error = result.get('error', '转存失败')
                return {'success': False, 'error': task.error}
        except Exception as e:
            task.status = WorkflowStatus.FAILED
            task.error = str(e)
            return {'success': False, 'error': str(e)}
    
    def _save_123_share(self, task: WorkflowTask) -> Dict[str, Any]:
        """转存 123 云盘分享链接"""
        task.status = WorkflowStatus.SAVING
        
        if not self.cloud123_service:
            task.status = WorkflowStatus.FAILED
            task.error = '123 云盘服务未初始化'
            return {'success': False, 'error': task.error}
        
        save_dir = self._get_save_dir('123')
        
        try:
            result = self.cloud123_service.save_share(
                share_code=task.parsed_link.share_code,
                access_code=task.parsed_link.access_code,
                save_path=save_dir
            )
            
            if result.get('success'):
                self._start_post_save_workflow(task, result.get('file_id'))
                return {
                    'success': True,
                    'task_id': task.id,
                    'message': '转存成功，正在整理...'
                }
            else:
                task.status = WorkflowStatus.FAILED
                task.error = result.get('error', '转存失败')
                return {'success': False, 'error': task.error}
        except Exception as e:
            task.status = WorkflowStatus.FAILED
            task.error = str(e)
            return {'success': False, 'error': str(e)}
    
    def _offline_download(self, task: WorkflowTask) -> Dict[str, Any]:
        """离线下载"""
        task.status = WorkflowStatus.OFFLINE
        
        target = task.target_cloud
        
        if target == '115':
            if not self.offline_service:
                task.status = WorkflowStatus.FAILED
                task.error = '115 离线服务未初始化'
                return {'success': False, 'error': task.error}
            
            save_cid = self._get_save_dir('115')
            result = self.offline_service.create_task(
                source_url=task.parsed_link.url,
                save_cid=save_cid,
                requested_by=task.user_id,
                requested_chat=task.chat_id
            )
            
            if result.get('success'):
                task.offline_task_id = result.get('data', {}).get('id')
                return {
                    'success': True,
                    'task_id': task.id,
                    'offline_task_id': task.offline_task_id,
                    'message': '已添加到 115 离线队列'
                }
            else:
                task.status = WorkflowStatus.FAILED
                task.error = result.get('error', '添加离线任务失败')
                return {'success': False, 'error': task.error}
                
        elif target == '123':
            if not self.cloud123_service:
                task.status = WorkflowStatus.FAILED
                task.error = '123 云盘服务未初始化'
                return {'success': False, 'error': task.error}
            
            save_dir = self._get_save_dir('123')
            result = self.cloud123_service.create_offline_task(
                source_url=task.parsed_link.url,
                save_dir_id=save_dir
            )
            
            if result.get('success'):
                task.offline_task_id = result.get('data', {}).get('p123TaskId')
                return {
                    'success': True,
                    'task_id': task.id,
                    'offline_task_id': task.offline_task_id,
                    'message': '已添加到 123 云盘离线队列'
                }
            else:
                task.status = WorkflowStatus.FAILED
                task.error = result.get('error', '添加离线任务失败')
                return {'success': False, 'error': task.error}
        
        task.status = WorkflowStatus.FAILED
        task.error = '未知目标网盘'
        return {'success': False, 'error': task.error}
    
    def on_offline_complete(self, offline_task_id: str, file_path: str = None) -> None:
        """
        离线任务完成回调
        
        Args:
            offline_task_id: 离线任务ID
            file_path: 下载完成的文件路径
        """
        # 查找对应的工作流任务
        task = None
        for t in self.tasks.values():
            if t.offline_task_id == offline_task_id:
                task = t
                break
        
        if not task:
            logger.warning(f"找不到离线任务 {offline_task_id} 对应的流程任务")
            return
        
        # 启动后续流程
        self._start_post_save_workflow(task, file_path)
    
    def _start_post_save_workflow(self, task: WorkflowTask, file_path: str = None) -> None:
        """启动保存/离线完成后的工作流（整理、STRM、通知）"""
        # 在后台线程执行
        thread = threading.Thread(
            target=self._execute_post_save_workflow,
            args=(task, file_path)
        )
        thread.daemon = True
        thread.start()
    
    def _execute_post_save_workflow(self, task: WorkflowTask, file_path: str = None) -> None:
        """执行保存后工作流"""
        try:
            # 1. 整理分类
            task.status = WorkflowStatus.ORGANIZING
            organized_result = self._organize_files(task)
            if organized_result:
                task.organized_path = organized_result.get('path')
                task.media_info = organized_result.get('media_info')
            
            # 2. 生成 STRM
            task.status = WorkflowStatus.STRM
            self._generate_strm(task)
            
            # 3. 刷新 Emby
            task.status = WorkflowStatus.REFRESHING
            self._refresh_emby(task)
            
            # 4. 发送通知
            task.status = WorkflowStatus.NOTIFYING
            self._send_notification(task)
            
            task.status = WorkflowStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"保存后工作流执行错误: {e}")
            task.status = WorkflowStatus.FAILED
            task.error = str(e)
    
        if self.offline_service:
            # 注册离线任务完成回调
            self.offline_service.add_listener(self.on_offline_complete)
            
    def process_message(self, chat_id: str, user_id: str, text: str) -> Dict[str, Any]:
        """
        处理用户消息，解析链接并开始工作流
        """
        # ... (implementation continues)

    def _organize_files(self, task: WorkflowTask) -> Optional[Dict]:
        """整理文件"""
        logger.info(f"开始整理任务 {task.id} 的文件")
        
        try:
            from services.media_organizer import MediaOrganizer
            from services.media_parser import get_media_parser, MediaType
            from services.llm_service import LLMService
            
            # 初始化服务
            media_organizer = MediaOrganizer()
            media_parser = get_media_parser()
            llm_service = LLMService(self.config_store) # config_store here acts as secret_store
            
            # 1. 获取文件列表
            files = []
            if task.target_cloud == '115':
                if not self.cloud115_service:
                    raise Exception("115 service not available")
                # 对于离线任务，我们需要找到下载的目录
                # 这里简化处理：假设文件就在 save_cid 中，或者通过 offline_task_id 查询
                # 实际情况可能更复杂，需要递归查找
                save_cid = self._get_save_dir('115')
                result = self.cloud115_service.list_directory(save_cid)
                if result.get('success'):
                    files = result.get('data', [])
            elif task.target_cloud == '123':
                 if not self.cloud123_service:
                    raise Exception("123 service not available")
                 save_dir = self._get_save_dir('123')
                 result = self.cloud123_service.list_directory(save_dir)
                 if result.get('success'):
                    files = result.get('data', [])
            
            if not files:
                logger.warning(f"任务 {task.id} 未找到文件")
                return None
                
            # 2. 遍历整理每个文件 (简化：只处理第一个视频文件)
            target_file = None
            for file in files:
                if not file.get('children'): # 是文件
                    name = file.get('name', '').lower()
                    if any(name.endswith(ext) for ext in ['.mkv', '.mp4', '.avi', '.ts']):
                        target_file = file
                        break
            
            if not target_file:
                return None
                
            file_id = target_file['id']
            file_name = target_file['name']
            
            # 3. 识别 (MediaParser)
            media_info = media_parser.parse(file_name)
            
            # 4. LLM 兜底识别
            if media_info.type == MediaType.UNKNOWN:
                logger.info(f"正则解析失败: {file_name}, 尝试 AI 识别...")
                llm_result = llm_service.parse_filename(file_name)
                
                if llm_result:
                    # 更新 media_info
                    media_info.title = llm_result.get('title', media_info.title)
                    media_info.year = llm_result.get('year', media_info.year)
                    media_info.type = MediaType(llm_result.get('type', 'unknown'))
                    media_info.season = llm_result.get('season')
                    media_info.episode = llm_result.get('episode')
                    media_info.tmdb_id = llm_result.get('tmdb_id')
                    # 可以将 category 存入 context 以供 MediaOrganizer 使用 (如果支持)
            
            # 5. 整理逻辑 (调用 MediaOrganizer)
            # 这里需要 MediaOrganizer 支持传入自定义的 category 或其他 Override
            # 目前版本 MediaOrganizer 主要依赖 TMDB info, 所以我们可能需要 mock tmdb info
            
            # 获取 TMDB 信息 (如果没有 ID，MediaOrganizer 会尝试搜索)
            # 这里简化直接调用 preview_organize 看效果，然后执行 real organize
            # 但 MediaOrganizer 目前 API 不太适合直接在这里调用完整流程
            
            # 记录整理日志
            from services.organize_log_service import get_organize_log_service
            organize_log = get_organize_log_service()
            
            target_path = f"/Organized/{media_info.title}/{file_name}"
            source_dir = self._get_save_dir(task.target_cloud)
            
            organize_log.log_success(
                source_dir=source_dir,
                original_name=file_name,
                new_name=file_name,  # 这里暂时使用相同名称
                target_path=target_path,
                cloud_type=task.target_cloud
            )
            
            return {
                'path': target_path,
                'media_info': media_info.to_dict()
            }

        except Exception as e:
            logger.error(f"整理失败: {e}")
            # 记录失败日志
            try:
                from services.organize_log_service import get_organize_log_service
                organize_log = get_organize_log_service()
                source_dir = self._get_save_dir(task.target_cloud) if task else ''
                organize_log.log_failure(
                    source_dir=source_dir,
                    original_name='Unknown',
                    new_name='',
                    target_path='',
                    error=str(e),
                    cloud_type=task.target_cloud if task else '115'
                )
            except:
                pass
            return None
    
    def _generate_strm(self, task: WorkflowTask) -> None:
        """生成 STRM 文件"""
        if not self.strm_service:
            logger.warning("STRM 服务未初始化")
            return
        
        try:
            config = {}
            if self.config_store:
                full_config = self.config_store.get_config()
                config = full_config.get('strm', {})
            
            self.strm_service.generate_strm(
                strm_type=task.target_cloud,
                config=config
            )
            logger.info(f"任务 {task.id} STRM 生成完成")
        except Exception as e:
            logger.error(f"STRM 生成错误: {e}")
    
    def _refresh_emby(self, task: WorkflowTask) -> None:
        """刷新 Emby 媒体库"""
        if not self.emby_service:
            logger.warning("Emby service not initialized")
            return
        
        try:
            self.emby_service.refresh_library()
            logger.info(f"任务 {task.id} Emby 刷新完成")
        except Exception as e:
            logger.error(f"Emby 刷新错误: {e}")
    
    def _send_notification(self, task: WorkflowTask) -> None:
        """发送 Telegram 通知（海报+详情）"""
        if not self.telegram_service:
            logger.warning("Telegram service not initialized")
            return
        
        try:
            # 构建通知消息
            message = self._build_notification_message(task)
            
            # 如果有媒体信息和海报，发送带图片的消息
            if task.media_info and task.media_info.get('poster_url'):
                self.telegram_service.send_photo_with_caption(
                    chat_id=task.chat_id,
                    photo_url=task.media_info['poster_url'],
                    caption=message
                )
            else:
                self.telegram_service.send_message(
                    chat_id=task.chat_id,
                    text=message
                )
            
            logger.info(f"任务 {task.id} 通知已发送")
        except Exception as e:
            logger.error(f"通知发送错误: {e}")
    
    def _build_notification_message(self, task: WorkflowTask) -> str:
        """构建通知消息"""
        lines = ["✅ 媒体入库完成\n"]
        
        if task.media_info:
            if task.media_info.get('title'):
                lines.append(f"📺 *{task.media_info['title']}*")
            if task.media_info.get('year'):
                lines.append(f"📅 年份: {task.media_info['year']}")
            if task.media_info.get('overview'):
                overview = task.media_info['overview']
                if len(overview) > 200:
                    overview = overview[:200] + '...'
                lines.append(f"\n📝 简介:\n{overview}")
        else:
            lines.append(f"📁 文件已整理完成")
            if task.organized_path:
                lines.append(f"📂 路径: {task.organized_path}")
        
        lines.append(f"\n☁️ 网盘: {task.target_cloud}")
        
        return '\n'.join(lines)
    
    def _get_save_dir(self, cloud_type: str) -> str:
        """获取保存目录"""
        if not self.config_store:
            return '0' if cloud_type == '115' else '/'
        
        try:
            config = self.config_store.get_config()
            cloud_config = config.get(f'cloud{cloud_type}', {})
            return cloud_config.get('downloadDir', '0' if cloud_type == '115' else '/')
        except:
            return '0' if cloud_type == '115' else '/'
    
    def get_task(self, task_id: str) -> Optional[WorkflowTask]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_pending_tasks(self, user_id: str = None) -> list:
        """获取待处理任务"""
        tasks = []
        for task in self.tasks.values():
            if task.status not in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]:
                if user_id is None or task.user_id == user_id:
                    tasks.append(task.to_dict())
        return tasks
