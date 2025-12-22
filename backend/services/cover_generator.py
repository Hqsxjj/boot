"""
Emby 封面图生成器服务
用于从 Emby 媒体库获取海报并生成动态封面
"""

import io
import base64
import logging
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import requests
import random

logger = logging.getLogger(__name__)

# 主题配色 (增强版: 定义基调色，生成时会加入变体)
THEMES = [
    {"name": "经典蓝", "colors": ("#3db1e0", "#2980b9", "#1c3d5a")},
    {"name": "深邃红", "colors": ("#e74c3c", "#c0392b", "#7b241c")},
    {"name": "翡翠绿", "colors": ("#2ecc71", "#27ae60", "#1b5e20")},
    {"name": "琥珀金", "colors": ("#f1c40f", "#f39c12", "#b7950b")},
    {"name": "皇家紫", "colors": ("#9b59b6", "#8e44ad", "#4a235a")},
    {"name": "暗夜黑", "colors": ("#2c3e50", "#34495e", "#1a1a1a")},
    {"name": "晨曦粉", "colors": ("#FFD194", "#70E1F5", "#FFD194")}, # 特殊：撞色
    {"name": "青翠林", "colors": ("#00b09b", "#96c93d", "#00b09b")},
    {"name": "梦幻紫", "colors": ("#834d9b", "#d04ed6", "#834d9b")},
    {"name": "蓝调调", "colors": ("#74ebd5", "#acb6e5", "#74ebd5")},
    {"name": "银月霜", "colors": ("#bdc3c7", "#2c3e50", "#bdc3c7")},
    {"name": "暖阳橘", "colors": ("#e65c00", "#f9d423", "#e65c00")},
]

# ... STAGES ...

class CoverGenerator:
    # ... __init__ ...

    # ... set_emby_config, get_libraries, get_library_posters ...

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """将十六进制颜色转换为 RGB"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _draw_mesh_gradient(self, width: int, height: int, colors: List[Tuple[int, int, int]]) -> Image.Image:
        """
        绘制弥散光混色背景 (Mesh Gradient)
        使用低分辨率绘制大色块然后高斯模糊，产生柔和自然的混色效果。
        """
        # 低分辨率画布 (提高性能 + 自然模糊)
        small_w, small_h = width // 8, height // 8
        base = Image.new("RGB", (small_w, small_h), colors[0])
        draw = ImageDraw.Draw(base)
        
        # 在不同位置绘制大圆色块
        # 坐标归一化: (x_ratio, y_ratio, color_index)
        blobs = [
            (0.0, 0.0, 0),    # 左上: 主色
            (1.0, 1.0, 1),    # 右下: 辅色 (深色)
            (0.8, 0.2, 2),    # 右上: 提亮色
            (0.2, 0.8, 2),    # 左下: 提亮色 (平衡)
            (0.5, 0.5, 0),    # 中心: 主色呼应
        ]
        
        if len(colors) < 3:
            # 如果颜色不足3种，重复使用
            colors = list(colors)
            while len(colors) < 3:
                colors.append(colors[0])
        
        for rx, ry, c_idx in blobs:
            cx, cy = int(rx * small_w), int(ry * small_h)
            color = colors[c_idx % len(colors)]
            
            # 半径随机一点，增加自然感
            radius = min(small_w, small_h) * 0.6
            
            # 使用半透明绘制以便叠加混合
            # PIL Draw.ellipse 不支持 alpha blend on RGB directly easily without new layer
            # 这里简单直接覆盖，靠后面的模糊来混合
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)
            
        # 强力高斯模糊，产生弥散效果
        blur_radius = min(small_w, small_h) // 3
        base = base.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # 放大回原尺寸，使用双三次插值保证平滑
        return base.resize((width, height), Image.Resampling.BICUBIC).convert("RGBA")

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
        font_path: str = None,
        custom_theme_color: str = None
    ) -> Image.Image:
        """
        生成静态封面图
        """
        # 如果指定了自定义主题索引 (处理随机化逻辑外部传入)
        if theme_index < 0:
            import random
            theme_index = random.randint(0, len(THEMES) - 1)
            
        theme = THEMES[theme_index % len(THEMES)]
        
        # 准备颜色
        base_colors = [self._hex_to_rgb(c) for c in theme["colors"]]
        
        # 绘制弥散光背景 (Mesh Gradient)
        img = self._draw_mesh_gradient(width, height, base_colors)
        
        # 创建 Draw 对象用于后续绘制
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
            resp = requests.post(url, params=params, headers=headers, data=image_data, timeout=30, verify=False)
            
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
