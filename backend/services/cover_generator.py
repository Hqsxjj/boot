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
# 海报布局阶段 (模拟 3D 堆叠效果)
STAGES = [
    {"x": 960,  "y": 440, "scale": 0.70, "angle": -28, "brightness": 0.5, "opacity": 0.4, "z": 20},
    {"x": 1050, "y": 470, "scale": 0.80, "angle": -18, "brightness": 0.7, "opacity": 0.6, "z": 30},
    {"x": 1150, "y": 500, "scale": 0.90, "angle": -8,  "brightness": 0.8, "opacity": 0.8, "z": 40},
    {"x": 1280, "y": 530, "scale": 1.00, "angle": 0,   "brightness": 0.9, "opacity": 0.95, "z": 50},
    {"x": 1450, "y": 560, "scale": 1.10, "angle": 10,  "brightness": 1.0, "opacity": 1.0,  "z": 100},
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
        
        # === 背景混合色 (Ambient Light / Mesh Gradient 模拟) ===
        # 在背景左上角和右下角添加淡淡的混合光斑，使背景不那么单调
        # 使用中间色 theme["colors"][1]
        mix_color = self._hex_to_rgb(theme["colors"][1])
        
        # 创建一个混合层
        mix_layer = Image.new("RGBA", (width, height), (0,0,0,0))
        mix_draw = ImageDraw.Draw(mix_layer)
        
        # 光斑 1: 左上角，巨大，柔和
        # 使用径向渐变模拟 (这里用多层半透明圆模拟模糊)
        import random
        # 稍微随机一点位置，增加自然感
        cx1, cy1 = random.randint(0, width//3), random.randint(0, height//3)
        radius1 = 800
        for r in range(radius1, 0, -20):
            alpha = int(40 * (1 - r/radius1)) # 边缘透明，中心 40 alpha
            mix_draw.ellipse([cx1-r, cy1-r, cx1+r, cy1+r], fill=mix_color + (alpha,))
            
        # 光斑 2: 右下角，互补或同色
        cx2, cy2 = random.randint(width*2//3, width), random.randint(height*2//3, height)
        radius2 = 600
        for r in range(radius2, 0, -20):
            alpha = int(30 * (1 - r/radius2))
            mix_draw.ellipse([cx2-r, cy2-r, cx2+r, cy2+r], fill=mix_color + (alpha,))
            
        # 叠加混合层
        img = Image.alpha_composite(img, mix_layer)
        draw = ImageDraw.Draw(img)

        # === 2. 玻璃材质层 (第二层级) ===
        # 在背景之上，内容之下，加一层淡淡的玻璃质感
        # 创建一个覆盖大部分区域的圆角矩形，模拟玻璃面板
        glass_margin = 60
        glass_layer = Image.new("RGBA", (width, height), (0,0,0,0))
        glass_draw = ImageDraw.Draw(glass_layer)
        
        # 玻璃板区域
        # 玻璃板区域
        g_box = [glass_margin, glass_margin, width - glass_margin, height - glass_margin]
        
        # 提取主题强调色 (使用中间色 theme["colors"][1])
        accent_rgb = self._hex_to_rgb(theme["colors"][1])
        
        # 填充: 主题色淡混 (alpha 15) + 白色微混
        # 这里的 fill 只是底色，为了更通透，我们使用极淡的主题色
        glass_fill = accent_rgb + (15,)
        
        glass_draw.rounded_rectangle(g_box, radius=40, fill=glass_fill)
        # 描边: 稍亮的白色 (15% 不透明度)
        glass_draw.rounded_rectangle(g_box, radius=40, outline=(255, 255, 255, 30), width=2)
        
        # 叠加玻璃层
        img = Image.alpha_composite(img, glass_layer)
        # 重新获取 draw 对象因为 img 已经被替换
        draw = ImageDraw.Draw(img)
        
        # 绘制海报组
        p_base_w = int(width * (poster_scale_pct / 100))
        p_base_h = int(p_base_w * 1.5)
        
        import math
        from PIL import ImageFilter, ImageOps

        for i, config in enumerate(STAGES):
            if i >= len(posters):
                break
                
            poster = posters[i].copy()
            
            # 缩放
            sw, sh = int(p_base_w * config["scale"]), int(p_base_h * config["scale"])
            poster = poster.resize((sw, sh), Image.Resampling.LANCZOS)
            
            # === 海报圆角处理 ===
            # 创建圆角遮罩
            corner_radius = int(min(sw, sh) * 0.05) # 5% 的圆角
            mask = Image.new("L", (sw, sh), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, sw, sh], radius=corner_radius, fill=255)
            
            # 1. 透明度渐变处理
            # 遮罩的 alpha 值决定了最终图片的 alpha
            # 如果配置中有 opacity，则将遮罩的 alpha 值乘以此系数
            opacity = config.get("opacity", 1.0)
            if opacity < 1.0:
                # 获取 mask 数据
                mask_data = mask.getdata()
                # 重新计算 alpha
                new_data = [int(p * opacity) for p in mask_data]
                mask.putdata(new_data)
            
            # 应用遮罩 (此时 mask 已经被调整过 alpha)
            poster.putalpha(mask)
            
            # === 海报玻璃边缘感 ===
            # 在海报上叠加一个内发光/描边效果
            border_layer = Image.new("RGBA", (sw, sh), (0,0,0,0))
            border_draw = ImageDraw.Draw(border_layer)
            # 外部描边 (白色半透明) - 透明度也需要随整体 opacity 调整
            border_alpha = int(100 * opacity)
            border_draw.rounded_rectangle([0, 0, sw-1, sh-1], radius=corner_radius, outline=(255, 255, 255, border_alpha), width=2)
            
            poster = Image.alpha_composite(poster, border_layer)

            # 亮度调整
            if config["brightness"] < 1.0:
                enhancer = ImageEnhance.Brightness(poster)
                poster = enhancer.enhance(config["brightness"])
            
            # 旋转处理
            rot_angle = -config["angle"]
            # 注意: 旋转带 Alpha 通道的图像，expand=True 会自动处理透明背景
            rotated = poster.rotate(rot_angle, expand=True, resample=Image.Resampling.BICUBIC)
            
            # 计算 Pivot 偏移 (Center 80%)
            rad = math.radians(rot_angle)
            pivot_offset = 0.3 * sh # 从中心向下偏移 30% 高度
            
            shift_x = pivot_offset * math.sin(rad)
            shift_y = pivot_offset * (1 - math.cos(rad))
            
            base_x = config["x"] + offset_x
            base_y = config["y"]
            
            final_cx = base_x + shift_x
            final_cy = base_y + shift_y
            
            px = int(final_cx - rotated.width / 2)
            py = int(final_cy - rotated.height / 2)
            
            # 兼容性处理: 如果 rotated 尺寸超过画布，进行裁剪或调整
            # 简单方式: 直接 paste (PIL 会自动处理边界)
            
            # 绘制阴影 (带高斯模糊)
            if config.get("z", 0) > 0:
                shadow = Image.new("RGBA", rotated.size, (0, 0, 0, 0))
                # 创建阴影 mask，使用 alpha 通道
                shadow.paste((0,0,0,150), (0,0), rotated)
                # 模糊
                shadow = shadow.filter(ImageFilter.GaussianBlur(radius=15))
                
                # 阴影偏移
                sx = px + 10
                sy = py + 20
                img.paste(shadow, (sx, sy), shadow)
            
            # 粘贴海报 (使用 alpha_composite 或 paste mask)
            # 这里的 rotated 已经是 RGBA，直接 paste 即可利用其 alpha 通道进行混合
            img.paste(rotated, (px, py), rotated)
        
        # 字体加载逻辑 - 优先使用粗体
        font_candidates = [
            font_path, # 用户自定义
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", # Debian/Ubuntu Noto CJK Bold
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "msyhbd.ttf", # 微软雅黑粗体
            "msyh.ttf", 
            "simhei.ttf", 
            "PingFang.ttc", 
            "STHeiti Light.ttc", 
            "arialbd.ttf", # Arial Bold
            "arial.ttf", 
            "DejaVuSans-Bold.ttf"
        ]
        
        m_font = None
        s_font = None
        
        for f_path in font_candidates:
            if not f_path:
                continue
            try:
                m_font = ImageFont.truetype(f_path, title_size)
                s_font = ImageFont.truetype(f_path, 45) # 副标题固定 45
                logger.debug(f"成功加载字体: {f_path}")
                break
            except Exception:
                continue
                
        if m_font is None:
            logger.warning("未能加载任何系统字体，使用默认字体 (可能很小)")
            m_font = ImageFont.load_default()
            s_font = ImageFont.load_default()
        
        tx = int(width * 0.08)
        ty = int(height * (v_align_pct / 100))
        
        # === 文字 3D 立体阴影效果 ===
        # 使用多层投影模拟立体感
        # === 文字效果 (扁平化) ===
        
        # 1. 主标题
        # 移除 3D 阴影，仅保留一个柔和的投影以保证可读性
        draw.text((tx + 2, ty + 2), title, font=m_font, fill=(0, 0, 0, 100))
        draw.text((tx, ty), title, font=m_font, fill="white")
        
        # 2. 副标题
        # 调整间距
        spacing = int(title_size * 0.4) + 10 
        sub_y = ty + title_size + spacing
        
        # 简单的投影
        draw.text((tx + 2, sub_y + 2), subtitle, font=s_font, fill=(0, 0, 0, 80))
        draw.text((tx, sub_y), subtitle, font=s_font, fill=(255, 255, 255, 220))
        
        # 3. 装饰底线 (由实到虚)
        bar_y = sub_y + 60  # 在副标题下方
        bar_height = 4
        bar_width = 400
        
        # 创建渐变 Mask
        gradient_bar = Image.new('RGBA', (bar_width, bar_height), (0, 0, 0, 0))
        bar_draw = ImageDraw.Draw(gradient_bar)
        
        # 绘制渐变
        for x in range(bar_width):
            alpha = int(255 * (1 - (x / bar_width))) # 从左到右透明度降低 255 -> 0
            bar_draw.line([(x, 0), (x, bar_height)], fill=(255, 255, 255, alpha))
            
        # 粘贴渐变线条
        img.paste(gradient_bar, (tx, bar_y), gradient_bar)
        
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
            # 海报太少，返回单帧 GIF (保持格式一致)
            static_img = self.generate_cover(posters, title, subtitle, theme_index, width, height, **kwargs)
            # 缩小到 GIF 尺寸
            gif_width = min(width, 960)
            gif_height = int(gif_width * height / width)
            static_img = static_img.resize((gif_width, gif_height), Image.Resampling.LANCZOS)
            # 转换为 P 模式 (GIF 要求)
            static_img = static_img.convert("P", palette=Image.ADAPTIVE, colors=256)
            buffer = io.BytesIO()
            static_img.save(buffer, format="GIF")
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
            
            # 渲染全分辨率帧以保持布局一致性 (STAGES 坐标基于 1920x1080)
            full_frame = self.generate_cover(
                rotated_posters,
                title,
                subtitle,
                theme_index,
                width,
                height,
                **kwargs
            )
            
            # 缩放到 GIF 尺寸
            frame = full_frame.resize((gif_width, gif_height), Image.Resampling.LANCZOS)
            
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
    
    def upload_cover(self, library_id: str, image_data: bytes, content_type: str = "image/png") -> bool:
        """
        上传封面到 Emby 服务器
        
        Args:
            library_id: 媒体库 ID
            image_data: 图片二进制数据
            content_type: 图片类型 (image/png 或 image/gif)
            
        Returns:
            是否成功
        """
        if not self.emby_url or not self.api_key:
            logger.error("封面上传失败: Emby URL 或 API Key 未配置")
            return False
            
        try:
            url = f"{self.emby_url}/emby/Items/{library_id}/Images/Primary"
            params = {"api_key": self.api_key}
            headers = {"Content-Type": content_type}
            
            logger.info(f"正在上传封面到 {url}, 大小: {len(image_data)} bytes, 类型: {content_type}")
            
            # Emby API 接受 binary body
            resp = requests.post(url, params=params, headers=headers, data=image_data, timeout=30)
            
            # Emby 可能返回 200, 201, 或 204 表示成功
            if resp.status_code in [200, 201, 204]:
                logger.info(f"封面上传成功: {library_id} (状态码: {resp.status_code})")
                return True
            else:
                logger.error(f"封面上传失败: {library_id} HTTP {resp.status_code} - {resp.text[:200] if resp.text else '无响应内容'}")
                return False
                
        except requests.Timeout:
            logger.error(f"封面上传超时: {library_id}")
            return False
        except requests.ConnectionError as e:
            logger.error(f"封面上传连接失败: {library_id} - {e}")
            return False
        except Exception as e:
            logger.error(f"封面上传异常: {library_id} - {e}")
            return False
    
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
