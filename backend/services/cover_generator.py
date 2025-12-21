"""
Emby 封面图生成器服务
用于从 Emby 媒体库获取海报并生成动态封面
"""

import io
import base64
import logging
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import requests

logger = logging.getLogger(__name__)

# 主题配色
THEMES = [
    {"name": "经典蓝", "colors": ("#3db1e0", "#2980b9", "#1c3d5a")},
    {"name": "深邃红", "colors": ("#e74c3c", "#c0392b", "#7b241c")},
    {"name": "翡翠绿", "colors": ("#2ecc71", "#27ae60", "#1b5e20")},
    {"name": "琥珀金", "colors": ("#f1c40f", "#f39c12", "#b7950b")},
    {"name": "皇家紫", "colors": ("#9b59b6", "#8e44ad", "#4a235a")},
    {"name": "暗夜黑", "colors": ("#2c3e50", "#34495e", "#000000")},
    {"name": "晨曦粉", "colors": ("#FFD194", "#70E1F5", "#FFD194")},
    {"name": "青翠林", "colors": ("#00b09b", "#96c93d", "#00b09b")},
    {"name": "梦幻紫", "colors": ("#834d9b", "#d04ed6", "#834d9b")},
    {"name": "蓝调调", "colors": ("#74ebd5", "#acb6e5", "#74ebd5")},
    {"name": "银月霜", "colors": ("#bdc3c7", "#2c3e50", "#bdc3c7")},
    {"name": "暖阳橘", "colors": ("#e65c00", "#f9d423", "#e65c00")},
]

# 海报布局阶段 (模拟 3D 堆叠效果)
STAGES = [
    {"x": 960,  "y": 440, "scale": 0.70, "angle": -28, "brightness": 0.5, "z": 20},
    {"x": 1050, "y": 470, "scale": 0.80, "angle": -18, "brightness": 0.7, "z": 30},
    {"x": 1150, "y": 500, "scale": 0.90, "angle": -8,  "brightness": 0.8, "z": 40},
    {"x": 1280, "y": 530, "scale": 1.00, "angle": 0,   "brightness": 0.9, "z": 50},
    {"x": 1450, "y": 560, "scale": 1.10, "angle": 10,  "brightness": 1.0, "z": 100},
]


class CoverGenerator:
    """Emby 封面图生成器"""
    
    def __init__(self, emby_url: str = None, api_key: str = None):
        self.emby_url = emby_url
        self.api_key = api_key
        
    def set_emby_config(self, emby_url: str, api_key: str):
        """设置 Emby 连接配置"""
        self.emby_url = emby_url.rstrip('/')
        self.api_key = api_key
        
    def get_libraries(self) -> List[Dict[str, Any]]:
        """获取 Emby 媒体库列表"""
        if not self.emby_url or not self.api_key:
            return []
            
        try:
            url = f"{self.emby_url}/emby/Library/VirtualFolders"
            params = {"api_key": self.api_key}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            
            libraries = []
            for lib in resp.json():
                libraries.append({
                    "id": lib.get("ItemId", ""),
                    "name": lib.get("Name", ""),
                    "type": lib.get("CollectionType", ""),
                    "path": lib.get("Locations", [""])[0] if lib.get("Locations") else ""
                })
            return libraries
        except Exception as e:
            logger.error(f"获取媒体库列表失败: {e}")
            return []
    
    def get_library_posters(self, library_id: str, limit: int = 10) -> List[Image.Image]:
        """获取媒体库中的海报图片"""
        if not self.emby_url or not self.api_key:
            return []
            
        try:
            # 获取媒体库中的项目
            url = f"{self.emby_url}/emby/Items"
            params = {
                "api_key": self.api_key,
                "ParentId": library_id,
                "Limit": limit,
                "SortBy": "DateCreated,SortName",
                "SortOrder": "Descending",
                "ImageTypes": "Primary",
                "Recursive": True,
                "IncludeItemTypes": "Movie,Series"
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            
            items = resp.json().get("Items", [])
            posters = []
            
            for item in items[:limit]:
                item_id = item.get("Id")
                if not item_id:
                    continue
                    
                # 获取海报图片
                img_url = f"{self.emby_url}/emby/Items/{item_id}/Images/Primary"
                img_params = {"api_key": self.api_key, "maxWidth": 400}
                
                try:
                    img_resp = requests.get(img_url, params=img_params, timeout=10)
                    if img_resp.status_code == 200:
                        img = Image.open(io.BytesIO(img_resp.content)).convert("RGBA")
                        posters.append(img)
                except Exception as e:
                    logger.warning(f"获取海报失败: {item_id} - {e}")
                    
            return posters
        except Exception as e:
            logger.error(f"获取媒体库海报失败: {e}")
            return []
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """将十六进制颜色转换为 RGB"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _draw_gradient_background(self, draw: ImageDraw.Draw, width: int, height: int, 
                                   color1: str, color2: str):
        """绘制渐变背景"""
        c1 = self._hex_to_rgb(color1)
        c2 = self._hex_to_rgb(color2)
        
        for y in range(height):
            ratio = y / height
            r = int(c1[0] + (c2[0] - c1[0]) * ratio)
            g = int(c1[1] + (c2[1] - c1[1]) * ratio)
            b = int(c1[2] + (c2[2] - c1[2]) * ratio)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    def generate_cover(
        self,
        posters: List[Image.Image],
        title: str = "电影收藏",
        subtitle: str = "MOVIE COLLECTION",
        theme_index: int = 0,
        width: int = 1920,
        height: int = 1080,
        title_size: int = 130,
        offset_x: int = 200,
        poster_scale_pct: int = 30,
        v_align_pct: int = 22,
        font_path: str = None
    ) -> Image.Image:
        """
        生成静态封面图
        
        Args:
            posters: 海报图片列表
            title: 主标题
            subtitle: 副标题
            theme_index: 主题索引
            width: 输出宽度
            height: 输出高度
            title_size: 标题字号
            offset_x: 海报水平偏移
            poster_scale_pct: 海报缩放比例
            v_align_pct: 标题垂直对齐比例
            font_path: 自定义字体路径
            
        Returns:
            生成的封面图片
        """
        theme = THEMES[theme_index % len(THEMES)]
        
        # 创建画布
        img = Image.new("RGBA", (width, height), theme["colors"][0])
        draw = ImageDraw.Draw(img)
        
        # 绘制渐变背景
        self._draw_gradient_background(draw, width, height, theme["colors"][0], theme["colors"][-1])
        
        # 绘制海报组
        p_base_w = int(width * (poster_scale_pct / 100))
        p_base_h = int(p_base_w * 1.5)
        
        for i, config in enumerate(STAGES):
            if i >= len(posters):
                break
                
            poster = posters[i].copy()
            
            # 缩放
            sw, sh = int(p_base_w * config["scale"]), int(p_base_h * config["scale"])
            poster = poster.resize((sw, sh), Image.Resampling.LANCZOS)
            
            # 亮度调整
            if config["brightness"] < 1.0:
                enhancer = ImageEnhance.Brightness(poster)
                poster = enhancer.enhance(config["brightness"])
            
            # 旋转
            rotated = poster.rotate(config["angle"], expand=True, resample=Image.Resampling.BICUBIC)
            
            # 位置
            px = int(config["x"] + offset_x - rotated.width / 2)
            py = int(config["y"] - rotated.height / 2)
            
            # 绘制阴影
            shadow = Image.new("RGBA", rotated.size, (0, 0, 0, 120))
            img.paste(shadow, (px + 20, py + 20), shadow)
            
            # 粘贴海报
            img.paste(rotated, (px, py), rotated)
        
        # 绘制文字
        try:
            m_font = ImageFont.truetype(font_path or "arial.ttf", title_size)
            s_font = ImageFont.truetype(font_path or "arial.ttf", 45)
        except:
            m_font = ImageFont.load_default()
            s_font = ImageFont.load_default()
        
        tx = int(width * 0.08)
        ty = int(height * (v_align_pct / 100))
        
        # 主标题投影
        draw.text((tx + 6, ty + 6), title, font=m_font, fill=(0, 0, 0, 180))
        draw.text((tx, ty), title, font=m_font, fill="white")
        
        # 副标题
        draw.text((tx, ty + title_size + 25), subtitle, font=s_font, fill=(255, 255, 255, 200))
        
        # 装饰条
        bar_y = ty + title_size + 100
        draw.rectangle([tx, bar_y, tx + 180, bar_y + 8], fill="white")
        
        return img
    
    def generate_animated_cover(
        self,
        posters: List[Image.Image],
        title: str = "电影收藏",
        subtitle: str = "MOVIE COLLECTION",
        theme_index: int = 0,
        width: int = 1920,
        height: int = 1080,
        frame_count: int = 20,
        duration_ms: int = 100,
        **kwargs
    ) -> bytes:
        """
        生成动态 GIF 封面
        
        通过在帧之间轮换海报位置来创建动态效果
        
        Args:
            posters: 海报图片列表
            title: 主标题
            subtitle: 副标题
            theme_index: 主题索引
            width: 输出宽度
            height: 输出高度
            frame_count: 帧数
            duration_ms: 每帧持续时间(毫秒)
            **kwargs: 传递给 generate_cover 的其他参数
            
        Returns:
            GIF 图片的二进制数据
        """
        if len(posters) < 2:
            # 海报太少，返回静态图
            static_img = self.generate_cover(posters, title, subtitle, theme_index, width, height, **kwargs)
            buffer = io.BytesIO()
            static_img.save(buffer, format="PNG")
            return buffer.getvalue()
        
        frames = []
        num_posters = len(posters)
        
        # 使用较小分辨率生成 GIF 以减小文件大小
        gif_width = min(width, 960)
        gif_height = int(gif_width * height / width)
        
        for frame_idx in range(frame_count):
            # 每帧轮换海报顺序
            offset = frame_idx % num_posters
            rotated_posters = posters[offset:] + posters[:offset]
            
            frame = self.generate_cover(
                rotated_posters,
                title,
                subtitle,
                theme_index,
                gif_width,
                gif_height,
                **kwargs
            )
            
            # 转换为 RGB (GIF 不支持 RGBA)
            frame_rgb = frame.convert("P", palette=Image.ADAPTIVE, colors=256)
            frames.append(frame_rgb)
        
        # 保存为 GIF
        buffer = io.BytesIO()
        frames[0].save(
            buffer,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0
        )
        
        return buffer.getvalue()
    
    def cover_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """将图片转换为 base64 字符串"""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        mime = "image/png" if format.upper() == "PNG" else "image/gif"
        return f"data:{mime};base64,{b64}"
    
    def bytes_to_base64(self, data: bytes, mime: str = "image/gif") -> str:
        """将二进制数据转换为 data URL"""
        b64 = base64.b64encode(data).decode('utf-8')
        return f"data:{mime};base64,{b64}"


# 全局实例
_cover_generator: Optional[CoverGenerator] = None


def get_cover_generator() -> CoverGenerator:
    """获取封面生成器实例"""
    global _cover_generator
    if _cover_generator is None:
        _cover_generator = CoverGenerator()
    return _cover_generator
