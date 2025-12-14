"""
媒体整理服务
负责根据 TMDB 信息重命名和移动文件
支持二级分类（类别映射、目录匹配）
配置从 YAML 文件加载，可随时修改
"""
import os
import logging
from typing import Optional, Dict, Any, List
from jinja2 import Template, Environment, BaseLoader

from services.media_parser import MediaInfo, MediaType
from services.config_loader import (
    get_movie_categories,
    get_tv_categories,
    get_region_categories,
    get_anime_region_categories,
    get_default_category,
    get_rename_templates,
)

logger = logging.getLogger(__name__)


# ==================== 配置获取函数 ====================

def _get_movie_category_mapping() -> Dict[str, str]:
    """获取电影类别映射（从 YAML 加载）"""
    mapping = get_movie_categories()
    if not mapping:
        # 回退到默认值
        return {
            'Action': '动作电影',
            'Adventure': '冒险电影',
            'Animation': '动画电影',
            'Comedy': '喜剧电影',
            'Crime': '犯罪电影',
            'Documentary': '纪录片',
            'Drama': '剧情电影',
            'Family': '家庭电影',
            'Fantasy': '奇幻电影',
            'History': '历史电影',
            'Horror': '恐怖电影',
            'Music': '音乐电影',
            'Mystery': '悬疑电影',
            'Romance': '爱情电影',
            'Science Fiction': '科幻电影',
            'Thriller': '惊悚电影',
            'War': '战争电影',
            'Western': '西部电影',
            'TV Movie': '电视电影',
        }
    return mapping


def _get_tv_category_mapping() -> Dict[str, str]:
    """获取电视剧类别映射（从 YAML 加载）"""
    mapping = get_tv_categories()
    if not mapping:
        return {
            'Animation': '动漫',
            'Documentary': '纪录片',
            'Reality': '真人秀',
            'Talk': '脱口秀',
            'News': '新闻',
            'Soap': '肥皂剧',
            'Kids': '儿童',
            'Action & Adventure': '动作冒险剧',
            'Comedy': '喜剧',
            'Crime': '犯罪剧',
            'Drama': '剧情',
            'Family': '家庭剧',
            'Mystery': '悬疑剧',
            'Sci-Fi & Fantasy': '科幻奇幻剧',
            'War & Politics': '战争政治剧',
            'Western': '西部剧',
        }
    return mapping


def _get_region_category_mapping() -> Dict[str, str]:
    """获取地区分类映射（从 YAML 加载）"""
    mapping = get_region_categories()
    if not mapping:
        return {
            'CN': '国产剧', 'HK': '港台剧', 'TW': '港台剧',
            'JP': '日韩剧', 'KR': '日韩剧',
            'US': '欧美剧', 'GB': '欧美剧', 'CA': '欧美剧',
            'AU': '欧美剧', 'FR': '欧美剧', 'DE': '欧美剧',
        }
    return mapping


def _get_anime_region_mapping() -> Dict[str, str]:
    """获取动漫地区细分映射（从 YAML 加载）"""
    mapping = get_anime_region_categories()
    if not mapping:
        return {'JP': '日本动漫', 'CN': '国产动漫', 'US': '欧美动画'}
    return mapping


# 默认分类
DEFAULT_MOVIE_CATEGORY = '其他电影'
DEFAULT_TV_CATEGORY = '其他剧集'


# ==================== 默认模板 ====================

# 默认重命名模板
DEFAULT_MOVIE_TEMPLATE = "{{title}}{% if year %} ({{year}}){% endif %}"
DEFAULT_TV_TEMPLATE = "{{title}}{% if year %} ({{year}}){% endif %}/Season {{season_num}}/{{title}} - {{season}}{{episode}}"

# 带二级分类的目录模板
DEFAULT_MOVIE_DIR_TEMPLATE = "电影/{{category}}/{{title}}{% if year %} ({{year}}){% endif %}"
DEFAULT_TV_DIR_TEMPLATE = "电视剧/{{category}}/{{title}}{% if year %} ({{year}}){% endif %}/Season {{season_num}}"

# 无二级分类的简单模板
SIMPLE_MOVIE_DIR_TEMPLATE = "电影/{{title}}{% if year %} ({{year}}){% endif %}"
SIMPLE_TV_DIR_TEMPLATE = "电视剧/{{title}}{% if year %} ({{year}}){% endif %}/Season {{season_num}}"


class MediaOrganizer:
    """媒体整理器"""

    
    def __init__(self, config_store=None, cloud115_service=None, cloud123_service=None):
        self.config_store = config_store
        self.cloud115_service = cloud115_service
        self.cloud123_service = cloud123_service
        
        # Jinja2 环境
        self.jinja_env = Environment(loader=BaseLoader())
    
    def _get_config_value(self, section: str, key: str, default=None):
        """Helper to get config value from store or return default"""
        if self.config_store:
            try:
                config = self.config_store.get_config()
                return config.get('organize', {}).get(section, {}).get(key, default)
            except:
                pass
        return default

    def generate_new_name(
        self,
        media_info: MediaInfo,
        tmdb_info: Optional[Dict] = None,
        template: Optional[str] = None,
        include_extension: bool = True,
        original_extension: str = ".mkv"
    ) -> str:
        """
        根据模板生成新文件名
        """
        # 确定模板 (优先使用 ConfigStore)
        if not template:
            if self.config_store:
                try:
                    config = self.config_store.get_config()
                    rename_config = config.get('organize', {}).get('rename', {})
                    if media_info.type == MediaType.TV:
                        template = rename_config.get('seriesTemplate')
                    else:
                        template = rename_config.get('movieTemplate')
                except Exception as e:
                    logger.warning(f"Failed to get template from config store: {e}")

            # Fallback to YAML if still no template
            if not template:
                templates = get_rename_templates()
                if media_info.type == MediaType.TV:
                    template = templates.get('tv', {}).get('filename', DEFAULT_TV_TEMPLATE)
                else:
                    template = templates.get('movie', {}).get('filename', DEFAULT_MOVIE_TEMPLATE)
        
        # 构建模板变量
        variables = self._build_template_variables(media_info, tmdb_info)
        
        try:
            # 渲染模板
            jinja_template = self.jinja_env.from_string(template)
            new_name = jinja_template.render(**variables)
            
            # 清理文件名中的非法字符
            new_name = self._sanitize_filename(new_name)
            
            # 添加扩展名
            if include_extension:
                new_name += original_extension
            
            return new_name
            
        except Exception as e:
            logger.error(f"Generate new name failed: {e}")
            return media_info.original_name
    
    def generate_target_path(
        self,
        media_info: MediaInfo,
        tmdb_info: Optional[Dict] = None,
        base_dir: str = "",
        dir_template: Optional[str] = None
    ) -> str:
        """
        生成目标目录路径
        """
        if not dir_template:
            # ConfigStore doesn't strictly have dir templates in the simplify UI yet, 
            # but we should check if they were added or fallback to YAML
            templates = get_rename_templates()
            # 优先使用配置中的目录模板
            if media_info.type == MediaType.TV:
                dir_template = templates.get('tv', {}).get('directory', DEFAULT_TV_DIR_TEMPLATE)
            else:
                dir_template = templates.get('movie', {}).get('directory', DEFAULT_MOVIE_DIR_TEMPLATE)
        
        variables = self._build_template_variables(media_info, tmdb_info)
        
        try:
            jinja_template = self.jinja_env.from_string(dir_template)
            target_dir = jinja_template.render(**variables)
            target_dir = self._sanitize_path(target_dir)
            
            # 检查是否需要强制附加 TMDB ID (Frontend Feature)
            # 逻辑：如果启用了 addTmdbIdToFolder，且路径中还没包含 ID，则附加之
            add_tmdb_id = self._get_config_value('rename', 'addTmdbIdToFolder', False)
            tmdb_id = variables.get('tmdb_id')
            
            if add_tmdb_id and tmdb_id:
                id_suffix = f" {{tmdb-{tmdb_id}}}"
                # 简单判断：如果路径结尾不是 ID 格式，且也没包含该 ID，则附加
                # 注意：这只是针对最末级文件夹添加后缀
                if str(tmdb_id) not in target_dir and not target_dir.endswith('}'):
                    target_dir += id_suffix

            if base_dir:
                target_dir = os.path.join(base_dir, target_dir)
            
            return target_dir
            
        except Exception as e:
            logger.error(f"Generate target path failed: {e}")
            return base_dir
    
    def _build_template_variables(self, media_info: MediaInfo, tmdb_info: Optional[Dict] = None) -> Dict[str, Any]:
        """构建模板变量"""
        # 基础变量来自解析结果
        variables = {
            'title': media_info.title or 'Unknown',
            'original_title': media_info.title,
            'year': media_info.year,
            'season': media_info.season_str,
            'season_num': media_info.season or 1,
            'episode': media_info.episode_str,
            'episode_num': media_info.episode,
            'part': media_info.part or '',
            'resource_type': media_info.resource_type or '',
            'resolution': media_info.resolution or '',
            'video_codec': media_info.video_codec or '',
            'audio_codec': media_info.audio_codec or '',
            'release_group': media_info.release_group or '',
            'tmdb_id': media_info.tmdb_id,
            'category': DEFAULT_MOVIE_CATEGORY if media_info.type != MediaType.TV else DEFAULT_TV_CATEGORY,
        }
        
        # 如果有 TMDB 信息，覆盖标题和年份，并计算二级分类
        if tmdb_info:
            variables['title'] = tmdb_info.get('title') or variables['title']
            variables['original_title'] = tmdb_info.get('original_title') or variables['original_title']
            variables['year'] = tmdb_info.get('year') or variables['year']
            variables['tmdb_id'] = tmdb_info.get('id') or variables['tmdb_id']
            variables['overview'] = tmdb_info.get('overview', '')
            
            genres = tmdb_info.get('genres', [])
            variables['genres'] = ', '.join(genres) if isinstance(genres, list) else genres
            
            # 计算二级分类
            variables['category'] = self._get_category(media_info.type, tmdb_info)
        
        return variables
    
    def _get_category(self, media_type: MediaType, tmdb_info: Dict) -> str:
        """
        根据 TMDB 信息计算二级分类
        优先使用 ConfigStore (Frontend Rules)，回退到 config_loader (YAML)
        """
        # 1. 尝试使用 ConfigStore 中的动态规则 (Frontend UI Rules)
        if self.config_store:
            try:
                config = self.config_store.get_config()
                organize_config = config.get('organize', {})
                
                # 获取对应类型的规则列表
                rules = []
                if media_type == MediaType.MOVIE:
                    rules = organize_config.get('movieRules', [])
                else:
                    rules = organize_config.get('tvRules', [])
                
                # 遍历规则进行匹配
                if rules and isinstance(rules, list):
                    # 预处理 TMDB 信息
                    tmdb_genres = tmdb_info.get('genres', [])
                    if isinstance(tmdb_genres, str): tmdb_genres = [g.strip() for g in tmdb_genres.split(',')]
                    
                    tmdb_genre_ids = tmdb_info.get('genre_ids', [])
                    if isinstance(tmdb_genre_ids, list): tmdb_genre_ids = [str(g) for g in tmdb_genre_ids]
                    elif isinstance(tmdb_genre_ids, str): tmdb_genre_ids = [g.strip() for g in tmdb_genre_ids.split(',')]
                    
                    tmdb_countries = tmdb_info.get('origin_country', [])
                    if isinstance(tmdb_countries, str): tmdb_countries = [tmdb_countries]
                    
                    tmdb_lang = tmdb_info.get('original_language', '')

                    for rule in rules:
                        conditions = rule.get('conditions', {})
                        # 检查所有条件
                        match = True
                        
                        # A. Genre Check
                        if 'genre_ids' in conditions and conditions['genre_ids']:
                            target_ids = conditions['genre_ids'].split(',')
                            # 只要包含其中一个
                            if not any(gid in tmdb_genre_ids for gid in target_ids):
                                match = False
                        
                        # B. Country Check
                        if match and 'origin_country' in conditions and conditions['origin_country']:
                            cond_val = conditions['origin_country']
                            is_exclude = cond_val.startswith('!')
                            target_countries = cond_val.replace('!', '').split(',')
                            
                            has_match = any(c in tmdb_countries for c in target_countries)
                            
                            if is_exclude and has_match: match = False
                            elif not is_exclude and not has_match: match = False
                        
                        # C. Language Check
                        if match and 'original_language' in conditions and conditions['original_language']:
                            cond_val = conditions['original_language']
                            is_exclude = cond_val.startswith('!')
                            target_langs = cond_val.replace('!', '').split(',')
                            
                            has_match = tmdb_lang in target_langs
                            
                            if is_exclude and has_match: match = False
                            elif not is_exclude and not has_match: match = False

                        if match:
                            return rule.get('name', 'Unknown')

            except Exception as e:
                logger.warning(f"Error matching rules from ConfigStore: {e}")

        # 2. 回退到 YAML 高级规则 (config_loader)
        from services.config_loader import get_advanced_rules
        
        genres = tmdb_info.get('genres', [])
        # 统一转为列表
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(',')]
            
        genre_ids = tmdb_info.get('genre_ids', [])
        # 确保 genre_ids 是字符串列表
        if isinstance(genre_ids, list):
            genre_ids = [str(g) for g in genre_ids]
        elif isinstance(genre_ids, str):
            genre_ids = [g.strip() for g in genre_ids.split(',')]
        
        origin_country = tmdb_info.get('origin_country', [])
        if isinstance(origin_country, str):
            origin_country = [origin_country]
            
        original_language = tmdb_info.get('original_language', '')

        # 尝试使用高级规则匹配
        advanced_rules = get_advanced_rules()
        rules = advanced_rules.get('movie' if media_type == MediaType.MOVIE else 'tv', {})
        
        for category, conditions in rules.items():
            # 检查 genre_ids
            if 'genre_ids' in conditions and genre_ids:
                target_ids = conditions['genre_ids'].split(',')
                # 只要任何一个 ID 匹配
                if any(gid in genre_ids for gid in target_ids):
                    # 检查 origin_country
                    if 'origin_country' in conditions and origin_country:
                        target_countries = conditions['origin_country'].split(',')
                        if not any(c in origin_country for c in target_countries):
                            continue
                    return category
            
            # 检查 origin_country (如果没有 genre_ids 限制)
            elif 'origin_country' in conditions and origin_country:
                target_countries = conditions['origin_country'].split(',')
                if any(c in origin_country for c in target_countries):
                    return category
                    
            # 检查 original_language
            elif 'original_language' in conditions and original_language:
                target_langs = conditions['original_language'].split(',')
                if original_language in target_langs:
                    return category
                    
            # 默认分类
            elif conditions.get('default'):
                return category

        # 3. 回退到旧的映射逻辑 (兼容性)
        if media_type == MediaType.MOVIE:
            categories = _get_movie_category_mapping()
            # 按类型匹配
            for genre in genres:
                if genre in categories:
                    return categories[genre]
            return DEFAULT_MOVIE_CATEGORY
        else:
            categories = _get_tv_category_mapping()
            regions = _get_region_category_mapping()
            
            # 按地区
            for country in origin_country:
                if country in regions:
                    return regions[country]
            # 按类型
            for genre in genres:
                if genre in categories:
                    return categories[genre]
            
            return DEFAULT_TV_CATEGORY
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名中的非法字符"""
        # Windows 非法字符
        illegal_chars = ['<', '>', ':', '"', '|', '?', '*', '\\', '/']
        for char in illegal_chars:
            filename = filename.replace(char, '')
        
        # 移除多余空格
        filename = ' '.join(filename.split())
        
        return filename.strip()
    
    def _sanitize_path(self, path: str) -> str:
        """清理路径中的非法字符（保留分隔符）"""
        # 按分隔符拆分，清理每个部分
        parts = path.replace('\\', '/').split('/')
        cleaned_parts = []
        for part in parts:
            if part:
                cleaned_parts.append(self._sanitize_filename(part))
        return '/'.join(cleaned_parts)
    
    def organize_file(
        self,
        cloud_type: str,
        file_id: str,
        new_name: str,
        target_dir: Optional[str] = None,
        create_dir: bool = True
    ) -> Dict[str, Any]:
        """
        整理文件（重命名并移动）
        
        Args:
            cloud_type: '115' 或 '123'
            file_id: 文件ID
            new_name: 新文件名
            target_dir: 目标目录（可选）
            create_dir: 是否创建目录
            
        Returns:
            操作结果
        """
        try:
            if cloud_type == '115':
                return self._organize_115(file_id, new_name, target_dir, create_dir)
            elif cloud_type == '123':
                return self._organize_123(file_id, new_name, target_dir, create_dir)
            else:
                return {'success': False, 'error': f'不支持的云盘类型: {cloud_type}'}
        except Exception as e:
            logger.error(f"Organize file failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _ensure_115_directory(self, path: str) -> Optional[str]:
        """
        确保 115 目录存在，返回最终 CID
        """
        if not path:
            return '0'
            
        parts = [p for p in path.replace('\\', '/').split('/') if p]
        current_cid = '0'
        
        for part in parts:
            # 列出当前目录寻找是否已存在
            result = self.cloud115_service.list_directory(current_cid)
            found_cid = None
            
            if result.get('success'):
                for item in result.get('data', []):
                    if item['name'] == part and item['children']: # children=True 表示是文件夹
                        found_cid = item['id']
                        break
            
            if found_cid:
                current_cid = found_cid
            else:
                # 创建目录
                create_result = self.cloud115_service.create_directory(current_cid, part)
                if create_result.get('success'):
                    current_cid = create_result['data']['id']
                else:
                    logger.error(f"Failed to create directory {part} in {current_cid}: {create_result.get('error')}")
                    return None
                    
        return current_cid

    def _ensure_123_directory(self, path: str) -> Optional[str]:
        """
        确保 123 目录存在，返回最终 DirID
        """
        if not path:
            return '0'
            
        parts = [p for p in path.replace('\\', '/').split('/') if p]
        current_id = '0'
        
        for part in parts:
            # 列出当前目录
            result = self.cloud123_service.list_directory(current_id)
            found_id = None
            
            if result.get('success'):
                for item in result.get('data', []):
                    if item['name'] == part and item['children']:
                        found_id = item['id']
                        break
            
            if found_id:
                current_id = found_id
            else:
                # 创建目录
                create_result = self.cloud123_service.create_directory(current_id, part)
                if create_result.get('success'):
                    current_id = create_result['data']['id']
                else:
                    logger.error(f"Failed to create directory {part} in {current_id}: {create_result.get('error')}")
                    return None
                    
        return current_id

    def _organize_115(self, file_id: str, new_name: str, target_dir: Optional[str], create_dir: bool) -> Dict[str, Any]:
        """整理 115 网盘文件"""
        if not self.cloud115_service:
            return {'success': False, 'error': '115 服务未初始化'}
        
        # 1. 重命名文件 (如果名字不同)
        # 注意：如果不需要重命名，可以跳过，但通常为了规范化都会重命名
        rename_result = self.cloud115_service.rename_file(file_id, new_name)
        if not rename_result.get('success'):
            return rename_result
        
        # 2. 如果指定了目标目录，移动文件
        if target_dir:
            target_cid = self._ensure_115_directory(target_dir)
            if not target_cid:
                return {'success': False, 'error': f'无法创建或找到目标目录: {target_dir}'}
            
            move_result = self.cloud115_service.move_file(file_id, target_cid)
            if not move_result.get('success'):
                return {'success': False, 'error': f'移动文件失败: {move_result.get("error")}'}
        
        return {'success': True, 'message': '整理完成', 'new_name': new_name}
    
    def _organize_123(self, file_id: str, new_name: str, target_dir: Optional[str], create_dir: bool) -> Dict[str, Any]:
        """整理 123 云盘文件"""
        if not self.cloud123_service:
            return {'success': False, 'error': '123 服务未初始化'}
        
        # 1. 重命名文件
        rename_result = self.cloud123_service.rename_file(file_id, new_name)
        if not rename_result.get('success'):
            return rename_result
        
        # 2. 如果指定了目标目录，移动文件
        if target_dir:
            target_id = self._ensure_123_directory(target_dir)
            if not target_id:
                return {'success': False, 'error': f'无法创建或找到目标目录: {target_dir}'}
                
            move_result = self.cloud123_service.move_file(file_id, target_id)
            if not move_result.get('success'):
                return {'success': False, 'error': f'移动文件失败: {move_result.get("error")}'}
        
        return {'success': True, 'message': '整理完成', 'new_name': new_name}
    
    def preview_organize(
        self,
        media_info: MediaInfo,
        tmdb_info: Optional[Dict] = None,
        original_extension: str = ".mkv",
        name_template: Optional[str] = None,
        dir_template: Optional[str] = None,
        base_dir: str = ""
    ) -> Dict[str, Any]:
        """
        预览整理结果（不执行实际操作）
        
        Args:
            media_info: 解析的媒体信息
            tmdb_info: TMDB 信息
            original_extension: 原始扩展名
            name_template: 文件名模板
            dir_template: 目录模板
            base_dir: 基础目录
            
        Returns:
            预览结果
        """
        new_name = self.generate_new_name(
            media_info, tmdb_info, name_template, 
            include_extension=True, original_extension=original_extension
        )
        
        target_path = self.generate_target_path(
            media_info, tmdb_info, base_dir, dir_template
        )
        
        full_path = os.path.join(target_path, new_name) if target_path else new_name
        
        return {
            'success': True,
            'data': {
                'original_name': media_info.original_name,
                'new_name': new_name,
                'target_dir': target_path,
                'full_path': full_path.replace('\\', '/'),
                'media_info': media_info.to_dict(),
                'tmdb_info': tmdb_info,
            }
        }


# 单例
_media_organizer = None

def get_media_organizer(config_store=None, cloud115_service=None, cloud123_service=None) -> MediaOrganizer:
    """获取媒体整理器单例"""
    global _media_organizer
    if _media_organizer is None:
        _media_organizer = MediaOrganizer(config_store, cloud115_service, cloud123_service)
    return _media_organizer
