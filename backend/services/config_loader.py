"""
配置加载器
从 YAML 文件加载识别规则和分类配置
"""
import os
import yaml
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# 配置文件目录
CONFIG_DIR = Path(__file__).parent.parent / 'config'

# 缓存
_recognition_rules: Optional[Dict] = None
_category_config: Optional[Dict] = None


def load_yaml_file(filepath: Path) -> Dict[str, Any]:
    """加载 YAML 文件"""
    try:
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        else:
            logger.warning(f"Config file not found: {filepath}")
            return {}
    except Exception as e:
        logger.error(f"Failed to load YAML file {filepath}: {e}")
        return {}


def get_recognition_rules(reload: bool = False) -> Dict[str, Any]:
    """
    获取识别规则配置
    
    包含：
    - custom_words: 自定义识别词列表
    - season_patterns: 季识别正则
    - episode_patterns: 集识别正则
    - resource_types: 资源类型映射
    - resolutions: 分辨率映射
    - video_codecs: 视频编码映射
    - audio_codecs: 音频编码映射
    - rename_templates: 重命名模板
    """
    global _recognition_rules
    
    if _recognition_rules is None or reload:
        filepath = CONFIG_DIR / 'recognition_rules.yml'
        _recognition_rules = load_yaml_file(filepath)
        logger.info(f"Loaded recognition rules from {filepath}")
    
    return _recognition_rules


def get_category_config(reload: bool = False) -> Dict[str, Any]:
    """
    获取分类配置
    
    包含：
    - movie_categories: 电影类别映射
    - tv_categories: 电视剧类别映射
    - region_categories: 地区分类映射
    - anime_region_categories: 动漫地区细分
    - defaults: 默认分类
    - classification_rules: 分类优先级规则
    """
    global _category_config
    
    if _category_config is None or reload:
        filepath = CONFIG_DIR / 'category_config.yml'
        _category_config = load_yaml_file(filepath)
        logger.info(f"Loaded category config from {filepath}")
    
    return _category_config


def get_movie_categories() -> Dict[str, str]:
    """获取电影类别映射"""
    config = get_category_config()
    return config.get('movie_categories', {})


def get_tv_categories() -> Dict[str, str]:
    """获取电视剧类别映射"""
    config = get_category_config()
    return config.get('tv_categories', {})


def get_region_categories() -> Dict[str, str]:
    """获取地区分类映射"""
    config = get_category_config()
    return config.get('region_categories', {})


def get_anime_region_categories() -> Dict[str, str]:
    """获取动漫地区细分映射"""
    config = get_category_config()
    return config.get('anime_region_categories', {})


def get_default_category(media_type: str) -> str:
    """获取默认分类"""
    config = get_category_config()
    defaults = config.get('defaults', {})
    return defaults.get(media_type, '其他')


def get_custom_words() -> List[str]:
    """获取自定义识别词列表"""
    rules = get_recognition_rules()
    return rules.get('custom_words', [])


def get_resource_types() -> Dict[str, List[str]]:
    """获取资源类型映射"""
    rules = get_recognition_rules()
    return rules.get('resource_types', {})


def get_resolutions() -> Dict[str, List[str]]:
    """获取分辨率映射"""
    rules = get_recognition_rules()
    return rules.get('resolutions', {})


def get_video_codecs() -> Dict[str, List[str]]:
    """获取视频编码映射"""
    rules = get_recognition_rules()
    return rules.get('video_codecs', {})


def get_audio_codecs() -> Dict[str, List[str]]:
    """获取音频编码映射"""
    rules = get_recognition_rules()
    return rules.get('audio_codecs', {})


def get_rename_templates() -> Dict[str, Dict[str, str]]:
    """获取重命名模板"""
    rules = get_recognition_rules()
    return rules.get('rename_templates', {})


def get_advanced_rules() -> Dict[str, Any]:
    """获取高级分类规则"""
    config = get_category_config()
    return config.get('advanced_rules', {})


def reload_all_configs():
    """重新加载所有配置"""
    get_recognition_rules(reload=True)
    get_category_config(reload=True)
    logger.info("All configs reloaded")
