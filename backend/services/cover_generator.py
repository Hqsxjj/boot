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


# 主题配色 (Premium Gradients)
# 采用更具质感的色彩组合，模拟流媒体平台大片风格
THEMES = [
    # 冷色系
    {"name": "深海极光", "colors": ("#0f2027", "#203a43", "#2c5364")}, # Dark Teal
    {"name": "午夜霓虹", "colors": ("#141E30", "#243B55", "#6c5ce7")}, # Dark Blue & Purple
    {"name": "赛博朋克", "colors": ("#2b1055", "#7597de", "#2b1055")}, # Purple & Blue
    {"name": "北欧冰川", "colors": ("#2980b9", "#6dd5fa", "#ffffff")}, # Ice Blue (Bright)
    
    # 暖色系
    {"name": "暮色之城", "colors": ("#4b134f", "#c94b4b", "#4b134f")}, # Deep Red/Purple
    {"name": "落日余晖", "colors": ("#ee0979", "#ff6a00", "#ee0979")}, # Orange/Pink
    {"name": "黑金奢华", "colors": ("#141e30", "#cbb4d4", "#203a43")}, # Dark & Goldish
    {"name": "火山熔岩", "colors": ("#93291E", "#ED213A", "#93291E")}, # Deep Red

    # 中性/艺术
    {"name": "水墨烟雨", "colors": ("#232526", "#414345", "#232526")}, # Grey/Black
    {"name": "甚至绿意", "colors": ("#134E5E", "#71B280", "#134E5E")}, # Forest
    {"name": "皇家丝绒", "colors": ("#360033", "#0b8793", "#360033")}, # Velvet
    {"name": "迷幻紫晶", "colors": ("#614385", "#516395", "#614385")}, # Amethyst
]

# 海报布局阶段 (模拟 3D 堆叠效果 - 增强版)
# 加大远近差异，增强立体透视感
STAGES = [
    {"x": 880,  "y": 410, "scale": 0.60, "angle": -40, "brightness": 0.4, "opacity": 0.3, "z": 10},
    {"x": 1000, "y": 450, "scale": 0.72, "angle": -30, "brightness": 0.6, "opacity": 0.6, "z": 30},
    {"x": 1140, "y": 490, "scale": 0.85, "angle": -20, "brightness": 0.85, "opacity": 0.85, "z": 60},
    {"x": 1300, "y": 530, "scale": 1.00, "angle": -10,   "brightness": 1.0, "opacity": 1.0,  "z": 100},
    {"x": 1480, "y": 570, "scale": 1.15, "angle": 0,  "brightness": 1.05, "opacity": 1.0, "z": 120},
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
            resp = requests.get(url, params=params, timeout=10, verify=False)
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
            resp = requests.get(url, params=params, timeout=10, verify=False)
            resp.raise_for_status()
            
            items = resp.json().get("Items", [])
            posters = []
            
            for item in items[:limit]:
                item_id = item.get("Id")
                if not item_id:
                    continue
                    
                # 获取海报图片
                img_url = f"{self.emby_url}/emby/Items/{item_id}/Images/Primary"
                # 用户要求更高清，提升 maxWidth 从 400 到 1000
                img_params = {"api_key": self.api_key, "maxWidth": 1000}
                
                try:
                    img_resp = requests.get(img_url, params=img_params, timeout=10, verify=False)
                    if img_resp.status_code == 200:
                        img = Image.open(io.BytesIO(img_resp.content)).convert("RGBA")
                        posters.append(img)
                except Exception as e:
                    logger.warning(f"获取海报失败: {item_id} - {e}")
                    
            return posters
        except Exception as e:
            logger.error(f"获取媒体库海报失败: {e}")
            return []

    def get_library_backdrop(self, library_id: str) -> Optional[Image.Image]:
        """获取媒体库的背景图 (Backdrop/Art/Thumb)"""
        if not self.emby_url or not self.api_key:
            return None
            
        try:
            # 尝试获取 Backdrop 0
            img_url = f"{self.emby_url}/emby/Items/{library_id}/Images/Backdrop/0"
            img_params = {"api_key": self.api_key, "maxWidth": 2000} # 高清
            
            img_resp = requests.get(img_url, params=img_params, timeout=10, verify=False)
            if img_resp.status_code == 200:
                return Image.open(io.BytesIO(img_resp.content)).convert("RGBA")
            
            # 如果没有 Backdrop，尝试 Thumb (某些库只有Thumb)
            img_url = f"{self.emby_url}/emby/Items/{library_id}/Images/Thumb/0"
            img_resp = requests.get(img_url, params=img_params, timeout=10, verify=False)
            if img_resp.status_code == 200:
                return Image.open(io.BytesIO(img_resp.content)).convert("RGBA")
                
            return None
        except Exception as e:
            logger.warning(f"获取媒体库背景失败: {library_id} - {e}")
            return None

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """将十六进制颜色转换为 RGB"""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _add_noise(self, img: Image.Image, intensity: int = 20) -> Image.Image:
        """添加噪点纹理"""
        width, height = img.size
        # 创建噪点层
        noise = Image.effect_noise((width, height), intensity)
        # 将噪点转换为 RGBA
        noise = noise.convert("RGBA")
        
        # 叠加噪点 (Overlay 模式或者简单的 alpha blend)
        # 方案：创建一张纯黑图，用 noise 作为 alpha
        # 这是一个简单的实现：
        overlay = Image.blend(img, noise.convert("RGBA"), 0.05) # 5% 噪点混合
        return overlay

    def _draw_mesh_gradient(self, width: int, height: int, colors: List[Tuple[int, int, int]]) -> Image.Image:
        """
        绘制高级弥散光背景 (Advanced Mesh Gradient)
        增加光斑数量、随机性和噪点质感。
        """
        # 1. 基础分辨率画布
        # 稍微提高分辨率以免过度模糊丢失细节
        small_w, small_h = width // 4, height // 4
        base = Image.new("RGB", (small_w, small_h), colors[0])
        draw = ImageDraw.Draw(base)
        
        # 2. 生成多层光斑
        # 我们使用更多的光斑，且颜色在主题色中循环
        if len(colors) < 3:
            colors = list(colors)
            while len(colors) < 3:
                colors.append(colors[0])
                
        # 随机分布的光斑
        blobs = []
        for i in range(8): # 8个光斑
            # x, y, color_idx, size_ratio
            blobs.append((
                random.uniform(0, 1.0),
                random.uniform(0, 1.0),
                random.randint(0, len(colors)-1),
                random.uniform(0.4, 0.9)
            ))
            
        for rx, ry, c_idx, s_ratio in blobs:
            cx, cy = int(rx * small_w), int(ry * small_h)
            color = colors[c_idx]
            
            # 基本半径
            radius = int(min(small_w, small_h) * s_ratio)
            
            # 绘制
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)
            
        # 3. 强力高斯模糊 (First Pass)
        base = base.filter(ImageFilter.GaussianBlur(radius=min(small_w, small_h) // 4))
        
        # 4. 再次绘制一些强调色光斑 (Highlight)
        # 使得画面有层次感 (Defocus)
        highlight_color = colors[1] # 通常是比较亮的颜色
        cx, cy = int(random.uniform(0.2, 0.8) * small_w), int(random.uniform(0.2, 0.8) * small_h)
        radius = int(min(small_w, small_h) * 0.4)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=highlight_color)
        
        # 5. 最终模糊
        base = base.filter(ImageFilter.GaussianBlur(radius=min(small_w, small_h) // 3))
        
        # 6. 放大
        img = base.resize((width, height), Image.Resampling.BICUBIC).convert("RGBA")
        
        # 7. 添加噪点质感 (Film Grain)
        img = self._add_noise(img, intensity=30)
        
        return img

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
        custom_theme_color: str = None,
        spacing: float = 1.0,
        angle_scale: float = 1.0,
        use_backdrop: bool = False,
        backdrop_img: Image.Image = None
    ) -> Image.Image:
        """
        生成静态封面图
        spacing: 堆叠间距系数，默认 1.0
        angle_scale: 旋转角度系数，默认 1.0
        use_backdrop: 是否使用横幅背景
        backdrop_img: 传入的横幅背景图对象
        """
        
        base_colors = []
        
        # === 1. 颜色策略 ===
        # 如果 theme_index == -1，启用"自动混色"模式 (从海报提取颜色)
        if theme_index == -1:
            # 从每张海报提取一个主色调
            for p in posters[:5]: # 最多采5张
                # 缩放到 1x1 获取平均色
                avg = p.resize((1, 1), Image.Resampling.LANCZOS).getpixel((0, 0))
                # 剔除 alpha 如果有
                if isinstance(avg, int): # Grayscale
                    base_colors.append((avg, avg, avg))
                else:
                    base_colors.append(avg[:3])
            
            # 如果凑不够3个颜色，补一些随机变种
            while len(base_colors) < 3:
                import random
                base_colors.append((
                    random.randint(50, 200),
                    random.randint(50, 200),
                    random.randint(50, 200)
                ))
        else:
            # 使用预设主题
            theme = THEMES[theme_index % len(THEMES)]
            base_colors = [self._hex_to_rgb(c) for c in theme["colors"]]
        
        # === 2. 绘制背景 ===
        img = None
        
        if use_backdrop and backdrop_img:
            # 模式 A: 使用 Emby 横幅背景
            # 裁剪并模糊
            bg = backdrop_img.copy()
            # 居中裁剪到 16:9
            bg_w, bg_h = bg.size
            target_ratio = width / height
            curr_ratio = bg_w / bg_h
            
            if curr_ratio > target_ratio:
                # 图片太宽，裁两边
                new_w = int(bg_h * target_ratio)
                left = (bg_w - new_w) // 2
                bg = bg.crop((left, 0, left + new_w, bg_h))
            else:
                # 图片太高，裁上下
                new_h = int(bg_w / target_ratio)
                top = (bg_h - new_h) // 2
                bg = bg.crop((0, top, bg_w, top + new_h))
                
            bg = bg.resize((width, height), Image.Resampling.LANCZOS)
            
            # 高斯模糊
            bg = bg.filter(ImageFilter.GaussianBlur(radius=40))
            
            # 压暗处理 (Overlay 一个半透明黑色层)
            darken = Image.new("RGBA", (width, height), (0, 0, 0, 100)) # 40% 黑色
            
            # 如果也是自动混色，可以再叠一层淡淡的 Mesh Gradient 做色调统一
            if theme_index == -1:
                 # 极淡的彩色光晕 (alpha 40)
                 mesh = self._draw_mesh_gradient(width, height, base_colors)
                 mesh.putalpha(80) # 30% 混合
                 bg = bg.convert("RGBA")
                 bg = Image.alpha_composite(bg, mesh)
            
            bg = bg.convert("RGBA")
            bg = Image.alpha_composite(bg, darken)
            img = bg.convert("RGB") # 转回 RGB
            
        else:
            # 模式 B: 纯 Mesh Gradient 背景
            img = self._draw_mesh_gradient(width, height, base_colors)
            
        # 创建 Draw 对象用于后续绘制
        draw = ImageDraw.Draw(img)

        # === 3. 玻璃材质层 (第二层级) ===
        # 在背景之上，内容之下，加一层淡淡的玻璃质感
        # 创建一个覆盖大部分区域的圆角矩形，模拟玻璃面板
        glass_margin = 60
        glass_layer = Image.new("RGBA", (width, height), (0,0,0,0))
        glass_draw = ImageDraw.Draw(glass_layer)
        
        # 玻璃板区域
        g_box = [glass_margin, glass_margin, width - glass_margin, height - glass_margin]
        
        # 决定玻璃板色调
        if theme_index == -1 and len(base_colors) > 0:
            accent_rgb = base_colors[0] # 取色板第一个颜色
        elif 'theme' in locals():
             accent_rgb = self._hex_to_rgb(theme["colors"][1])
        else:
             accent_rgb = (255, 255, 255)

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
            
            # --- 间距调整 ---
            # 焦点海报的 x 坐标 (z=100 的那个) 假设在 1300 左右
            # 我们以 1300 为中心进行缩放
            center_x = 1300
            current_x = config["x"]
            # 应用间距系数:
            # new_dist = old_dist * spacing
            final_stage_x = center_x + (current_x - center_x) * spacing
            
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
            opacity = config.get("opacity", 1.0)
            if opacity < 1.0:
                mask_data = mask.getdata()
                new_data = [int(p * opacity) for p in mask_data]
                mask.putdata(new_data)
            
            # 应用遮罩
            poster.putalpha(mask)
            
            # === 海报玻璃边缘感 ===
            border_layer = Image.new("RGBA", (sw, sh), (0,0,0,0))
            border_draw = ImageDraw.Draw(border_layer)
            border_alpha = int(100 * opacity)
            border_draw.rounded_rectangle([0, 0, sw-1, sh-1], radius=corner_radius, outline=(255, 255, 255, border_alpha), width=2)
            
            poster = Image.alpha_composite(poster, border_layer)

            # 亮度调整
            if config["brightness"] < 1.0:
                enhancer = ImageEnhance.Brightness(poster)
                poster = enhancer.enhance(config["brightness"])
            
            # 旋转处理
            # 应用角度系数
            rot_angle = -config["angle"] * angle_scale

            # 注意: 旋转带 Alpha 通道的图像，expand=True 会自动处理透明背景
            rotated = poster.rotate(rot_angle, expand=True, resample=Image.Resampling.BICUBIC)
            
            # 计算 Pivot 偏移 (Center 80%)
            rad = math.radians(rot_angle)
            pivot_offset = 0.3 * sh # 从中心向下偏移 30% 高度
            
            shift_x = pivot_offset * math.sin(rad)
            shift_y = pivot_offset * (1 - math.cos(rad))
            
            base_x = final_stage_x + offset_x
            base_y = config["y"]
            
            final_cx = base_x + shift_x
            final_cy = base_y + shift_y
            
            px = int(final_cx - rotated.width / 2)
            py = int(final_cy - rotated.height / 2)
            
            # 兼容性处理: 如果 rotated 尺寸超过画布，进行裁剪或调整
            # 简单方式: 直接 paste (PIL 会自动处理边界)
            
            # === 0. 倒影 (Reflection) ===
            # 仅对不完全透明的海报生成倒影
            if opacity > 0.3:
                try:
                    reflection = rotated.copy().transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                    # 挤压倒影 (垂直方向压缩，使透视更自然)
                    ref_h = int(reflection.height * 0.6)
                    reflection = reflection.resize((reflection.width, ref_h))
                    
                    # 渐变蒙版
                    ref_mask = Image.new("L", reflection.size, 0)
                    ref_draw = ImageDraw.Draw(ref_mask)
                    # 垂直线性渐变 (上部不透明 -> 下部透明)
                    for y in range(ref_h):
                        ref_alpha = int(120 * (1 - y / ref_h) * opacity * config["scale"]) 
                        ref_draw.line([(0, y), (reflection.width, y)], fill=ref_alpha)
                        
                    # 应用蒙版
                    r_r, r_g, r_b, r_a = reflection.split()
                    from PIL import ImageChops
                    r_a = ImageChops.multiply(r_a, ref_mask)
                    reflection.putalpha(r_a)
                    
                    # 绘制倒影 (位置稍微向下一点)
                    # Z越小(越远)，倒影离得越近视觉上
                    ref_y = py + rotated.height - int(10 * config["scale"])
                    img.paste(reflection, (px, ref_y), reflection)
                except Exception:
                    pass
            
            # === 1. 阴影 (Shadow) with Depth ===
            if config.get("z", 0) > 0:
                shadow = Image.new("RGBA", rotated.size, (0, 0, 0, 0))
                # 颜色随深度变淡 (但Z越大离观众越近，阴影应该更深/更清晰？不，这取决于光源)
                # 假设光源在正前方：物体越近，阴影越散、越远
                # 传统UI阴影：物体浮起越高(Z大)，阴影越模糊、位移越大、透明度越低
                
                # Z: 20(远) -> 100(近)
                z_factor = config["z"] / 100.0
                
                shadow_alpha = int(180 * (config["opacity"] + 0.1))
                shadow_alpha = min(shadow_alpha, 200)
                
                shadow.paste((0,0,0,shadow_alpha), (0,0), rotated)
                
                # 模糊半径
                blur_r = int(10 + config["z"] * 0.25)
                shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur_r))
                
                # 偏移量
                off_d = int(5 + config["z"] * 0.35)
                sx = px + off_d
                sy = py + off_d + 15
                
                img.paste(shadow, (sx, sy), shadow)
            
            # 粘贴海报 (使用 alpha_composite 或 paste mask)
            # 这里的 rotated 已经是 RGBA，直接 paste 即可利用其 alpha 通道进行混合
            img.paste(rotated, (px, py), rotated)
            
            # === 2. 镜面高光 (Specular Highlight) ===
            # (已整合到玻璃边缘效果和整体光照中，此处无需额外叠加复杂图层，保持画面整洁)

        
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
