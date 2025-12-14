"""
媒体文件名解析服务
基于 MoviePilot 的识别逻辑实现
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)

# 尝试导入中文数字转换库
try:
    import cn2an
    HAS_CN2AN = True
except ImportError:
    HAS_CN2AN = False
    logger.warning("cn2an 库未安装，中文数字转换功能不可用")


class MediaType(Enum):
    """媒体类型"""
    UNKNOWN = "unknown"
    MOVIE = "movie"
    TV = "tv"


@dataclass
class MediaInfo:
    """媒体信息"""
    # 原始文件名
    original_name: str = ""
    # 识别的标题
    title: str = ""
    # 年份
    year: Optional[str] = None
    # 媒体类型
    type: MediaType = MediaType.UNKNOWN
    # 季
    season: Optional[int] = None
    season_end: Optional[int] = None
    # 集
    episode: Optional[int] = None
    episode_end: Optional[int] = None
    # Part/CD
    part: Optional[str] = None
    # 资源类型 (WEB-DL, BluRay等)
    resource_type: Optional[str] = None
    # 分辨率 (1080p, 4K等)
    resolution: Optional[str] = None
    # 视频编码
    video_codec: Optional[str] = None
    # 音频编码
    audio_codec: Optional[str] = None
    # 字幕组
    release_group: Optional[str] = None
    # TMDB ID (如果从文件名中识别到)
    tmdb_id: Optional[int] = None
    
    @property
    def season_str(self) -> str:
        """返回季字符串 如 S01"""
        if self.season is not None:
            if self.season_end and self.season_end != self.season:
                return f"S{self.season:02d}-S{self.season_end:02d}"
            return f"S{self.season:02d}"
        elif self.type == MediaType.TV:
            return "S01"
        return ""
    
    @property
    def episode_str(self) -> str:
        """返回集字符串 如 E01"""
        if self.episode is not None:
            if self.episode_end and self.episode_end != self.episode:
                return f"E{self.episode:02d}-E{self.episode_end:02d}"
            return f"E{self.episode:02d}"
        return ""
    
    def to_dict(self) -> dict:
        return {
            'original_name': self.original_name,
            'title': self.title,
            'year': self.year,
            'type': self.type.value,
            'season': self.season,
            'season_end': self.season_end,
            'episode': self.episode,
            'episode_end': self.episode_end,
            'season_str': self.season_str,
            'episode_str': self.episode_str,
            'part': self.part,
            'resource_type': self.resource_type,
            'resolution': self.resolution,
            'video_codec': self.video_codec,
            'audio_codec': self.audio_codec,
            'release_group': self.release_group,
            'tmdb_id': self.tmdb_id,
        }


class MediaParser:
    """媒体文件名解析器"""
    
    # 资源类型识别字典
    RESOURCE_TYPES = {
        'WEB-DL': [r'web[.\-_]?dl', r'webrip', r'web'],
        'BluRay': [r'blu[.\-_]?ray', r'bdrip', r'bdremux', r'bdmv'],
        'HDTV': [r'hdtv', r'hdtvrip', r'tvrip'],
        'DVDRip': [r'dvdrip', r'dvd'],
        'Remux': [r'remux'],
        'CAM': [r'cam', r'hdcam', r'ts', r'tc', r'hdrip'],
    }
    
    # 分辨率识别字典
    RESOLUTIONS = {
        '4K': [r'2160p', r'4k', r'uhd'],
        '1080p': [r'1080[pi]', r'fhd'],
        '720p': [r'720p', r'hd'],
        '480p': [r'480p', r'sd'],
    }
    
    # 视频编码识别字典
    VIDEO_CODECS = {
        'HEVC': [r'hevc', r'h\.?265', r'x265'],
        'AVC': [r'avc', r'h\.?264', r'x264'],
        'AV1': [r'av1'],
        'VP9': [r'vp9'],
    }
    
    # 音频编码识别字典
    AUDIO_CODECS = {
        'DTS-HD MA': [r'dts[.\-_]?hd[.\-_]?ma', r'dtshd'],
        'TrueHD': [r'truehd', r'atmos'],
        'DTS': [r'dts(?![.\-_]?hd)'],
        'AAC': [r'aac'],
        'FLAC': [r'flac'],
        'AC3': [r'ac3', r'dd5\.?1', r'dolby'],
    }
    
    # 季识别正则
    SEASON_PATTERNS = [
        # S01, S1, Season 1
        r'[Ss](\d{1,2})(?![0-9])',
        r'[Ss]eason[.\s_]*(\d{1,2})',
        # 第x季
        r'第\s*(\d{1,2})\s*季',
        r'第\s*([一二三四五六七八九十]+)\s*季',
    ]
    
    # 集识别正则
    EPISODE_PATTERNS = [
        # E01, E1, EP01
        r'[Ee][Pp]?(\d{1,4})(?![0-9])',
        # 第x集
        r'第\s*(\d{1,4})\s*[集话話期]',
        r'第\s*([一二三四五六七八九十百零]+)\s*[集话話期]',
        # Episode 1
        r'[Ee]pisode[.\s_]*(\d{1,4})',
    ]
    
    # S01E01 格式
    SEASON_EPISODE_PATTERN = r'[Ss](\d{1,2})[Ee](\d{1,4})'
    
    # 年份识别
    YEAR_PATTERN = r'[\[\(\s]?((?:19|20)\d{2})[\]\)\s]?'
    
    # Part/CD 识别
    PART_PATTERNS = [
        r'(CD\d+)',
        r'(Disc\s*\d+)',
        r'(Part\s*\d+)',
        r'(Pt\s*\d+)',
    ]
    
    # TMDB ID 识别 (格式: {tmdb-12345})
    TMDB_ID_PATTERN = r'\{tmdb[.\-_]?(\d+)\}'
    
    def __init__(self):
        pass
    
    def parse(self, filename: str) -> MediaInfo:
        """
        解析文件名，提取媒体信息
        
        Args:
            filename: 文件名（不含路径）
            
        Returns:
            MediaInfo 对象
        """
        info = MediaInfo(original_name=filename)
        
        # 移除文件扩展名
        name = self._remove_extension(filename)
        
        # 提取 TMDB ID
        info.tmdb_id = self._extract_tmdb_id(name)
        if info.tmdb_id:
            name = re.sub(self.TMDB_ID_PATTERN, '', name, flags=re.IGNORECASE)
        
        # 提取年份
        info.year = self._extract_year(name)
        
        # 提取季集信息
        season, season_end, episode, episode_end = self._extract_season_episode(name)
        info.season = season
        info.season_end = season_end
        info.episode = episode
        info.episode_end = episode_end
        
        # 判断媒体类型
        if info.season is not None or info.episode is not None:
            info.type = MediaType.TV
        
        # 提取资源类型
        info.resource_type = self._extract_by_dict(name, self.RESOURCE_TYPES)
        
        # 提取分辨率
        info.resolution = self._extract_by_dict(name, self.RESOLUTIONS)
        
        # 提取视频编码
        info.video_codec = self._extract_by_dict(name, self.VIDEO_CODECS)
        
        # 提取音频编码
        info.audio_codec = self._extract_by_dict(name, self.AUDIO_CODECS)
        
        # 提取 Part/CD
        info.part = self._extract_part(name)
        
        # 提取标题
        info.title = self._extract_title(name, info)
        
        # 如果没有识别到类型，根据标题长度猜测
        if info.type == MediaType.UNKNOWN and info.title:
            # 电影通常有年份
            if info.year:
                info.type = MediaType.MOVIE
        
        return info
    
    def _remove_extension(self, filename: str) -> str:
        """移除文件扩展名"""
        video_exts = ['.mkv', '.mp4', '.avi', '.wmv', '.flv', '.mov', '.m4v', '.ts', '.rmvb']
        name = filename
        for ext in video_exts:
            if name.lower().endswith(ext):
                name = name[:-len(ext)]
                break
        return name
    
    def _extract_tmdb_id(self, name: str) -> Optional[int]:
        """提取 TMDB ID"""
        match = re.search(self.TMDB_ID_PATTERN, name, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except:
                pass
        return None
    
    def _extract_year(self, name: str) -> Optional[str]:
        """提取年份"""
        matches = re.findall(self.YEAR_PATTERN, name)
        if matches:
            # 返回最后一个年份（通常是正确的）
            return matches[-1]
        return None
    
    def _extract_season_episode(self, name: str) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
        """提取季和集信息"""
        season = None
        season_end = None
        episode = None
        episode_end = None
        
        # 尝试 S01E01 格式
        match = re.search(self.SEASON_EPISODE_PATTERN, name, re.IGNORECASE)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            return season, season_end, episode, episode_end
        
        # 尝试其他季格式
        for pattern in self.SEASON_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                season_str = match.group(1)
                season = self._convert_to_int(season_str)
                break
        
        # 尝试其他集格式
        for pattern in self.EPISODE_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                episode_str = match.group(1)
                episode = self._convert_to_int(episode_str)
                break
        
        # 尝试范围格式 E01-E05
        range_match = re.search(r'[Ee](\d{1,4})\s*-\s*[Ee]?(\d{1,4})', name)
        if range_match:
            episode = int(range_match.group(1))
            episode_end = int(range_match.group(2))
        
        return season, season_end, episode, episode_end
    
    def _convert_to_int(self, value: str) -> Optional[int]:
        """将字符串转为整数（支持中文数字）"""
        if not value:
            return None
        
        # 尝试直接转换
        try:
            return int(value)
        except ValueError:
            pass
        
        # 尝试中文数字转换
        if HAS_CN2AN:
            try:
                return int(cn2an.cn2an(value, mode='smart'))
            except:
                pass
        
        return None
    
    def _extract_by_dict(self, name: str, patterns_dict: dict) -> Optional[str]:
        """根据字典提取信息"""
        name_lower = name.lower()
        for key, patterns in patterns_dict.items():
            for pattern in patterns:
                if re.search(pattern, name_lower, re.IGNORECASE):
                    return key
        return None
    
    def _extract_part(self, name: str) -> Optional[str]:
        """提取 Part/CD 信息"""
        for pattern in self.PART_PATTERNS:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extract_title(self, name: str, info: MediaInfo) -> str:
        """提取标题"""
        title = name
        
        # 移除常见分隔符后的内容
        separators = ['.', '_', '-', ' ']
        
        # 移除年份及之后的内容
        if info.year:
            patterns = [
                rf'[\.\s_\-\(\[]{info.year}.*$',
                rf'^.*?{info.year}[\.\s_\-\)\]]',
            ]
            for pattern in patterns:
                match = re.search(pattern, title)
                if match:
                    # 取年份之前的部分
                    idx = title.find(info.year)
                    if idx > 0:
                        title = title[:idx]
                    break
        
        # 移除季集信息及之后的内容
        patterns_to_remove = [
            r'[Ss]\d{1,2}[Ee]\d{1,4}.*$',
            r'[Ss]\d{1,2}.*$',
            r'[Ee][Pp]?\d{1,4}.*$',
            r'第\s*\d+\s*[季集话話期].*$',
            r'第\s*[一二三四五六七八九十]+\s*[季集话話期].*$',
        ]
        
        for pattern in patterns_to_remove:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # 移除资源类型、分辨率等
        for patterns_dict in [self.RESOURCE_TYPES, self.RESOLUTIONS, self.VIDEO_CODECS, self.AUDIO_CODECS]:
            for key, patterns in patterns_dict.items():
                for pattern in patterns:
                    title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # 清理标题
        title = re.sub(r'[\.\-_]+', ' ', title)  # 替换分隔符为空格
        title = re.sub(r'\s+', ' ', title)  # 多空格变单空格
        title = title.strip()
        
        # 移除末尾的常见垃圾
        title = re.sub(r'\s*[\-\.\(\[\{]?\s*$', '', title)
        
        return title


# 单例
_media_parser = None

def get_media_parser() -> MediaParser:
    """获取媒体解析器单例"""
    global _media_parser
    if _media_parser is None:
        _media_parser = MediaParser()
    return _media_parser
