"""
Emby 封面图生成器服务
用于从 Emby 媒体库获取海报并生成动态封面
"""

import io
import os
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
# 海报布局配置 (动态生成)
# STAGES 将由 generate_layout 方法动态生成
STAGES_CONFIG = {
    # 最远端 (First Poster)
    "start": {"x": 900, "y": 410, "scale": 0.55, "angle": -60, "brightness": 0.4, "opacity": 0.70, "z": 10},
    # 最近端 (Last Poster) - 锚点
    "end":   {"x": 1350, "y": 570, "scale": 1.15, "angle": 0,   "brightness": 1.05, "opacity": 1.00, "z": 130}
}

class CoverGenerator:
    """Emby 封面图生成器"""
    
    
    def __init__(self, emby_url: str = None, api_key: str = None):
        self.emby_url = emby_url
        self.api_key = api_key
        self.proxies = {}
        self.verify_ssl = False
        self.timeout = 20
        
    def set_emby_config(self, emby_url: str, api_key: str, proxies: dict = None, verify_ssl: bool = False):
        """设置 Emby 连接配置"""
        self.emby_url = emby_url.rstrip('/')
        self.api_key = api_key
        self.proxies = proxies or {}
        self.verify_ssl = verify_ssl
        
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """统一请求处理，自动添加代理、SSL配置和默认头"""
        if 'timeout' not in kwargs:
            kwargs['timeout'] = self.timeout
            
        if 'verify' not in kwargs:
            kwargs['verify'] = self.verify_ssl
            
        if 'proxies' not in kwargs and self.proxies:
            kwargs['proxies'] = self.proxies
            
        # 默认 headers
        headers = kwargs.get('headers', {})
        if 'User-Agent' not in headers:
            headers['User-Agent'] = 'Boot-Cover-Generator/1.0'
        kwargs['headers'] = headers
        
        return requests.request(method, url, **kwargs)
        
    def _generate_layout(self, count: int) -> List[dict]:
        """根据海报数量动态生成布局 STAGES"""
        if count < 1: return []
        if count == 1:
            # 只有一张，直接用 end 状态 (最清晰的大图)
            return [STAGES_CONFIG["end"].copy()]
        
        stages = []
        start = STAGES_CONFIG["start"]
        end = STAGES_CONFIG["end"]
        
        for i in range(count):
            # t: 插值系数 0.0 -> 1.0
            t = i / (count - 1)
            
            # 线性插值辅助函数
            def lerp(k):
                return start[k] + (end[k] - start[k]) * t
            
            stage = {
                "x": int(lerp("x")),
                "y": int(lerp("y")),
                "scale": lerp("scale"),
                "angle": lerp("angle"),
                "brightness": lerp("brightness"),
                "opacity": lerp("opacity"),
                "z": int(lerp("z"))
            }
            stages.append(stage)
        return stages
        
    def get_libraries(self) -> List[Dict[str, Any]]:
        """获取 Emby 媒体库列表"""
        if not self.emby_url or not self.api_key:
            return []
            
        try:
            url = f"{self.emby_url}/emby/Library/VirtualFolders"
            params = {"api_key": self.api_key}
            resp = self._make_request('GET', url, params=params)
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
    
    def get_library_posters(self, library_id: str, limit: int = 10, sort_by: str = None) -> List[Image.Image]:
        """获取媒体库中的海报图片 (支持多种排序规则)
        
        Args:
            library_id: 媒体库 ID
            limit: 获取海报数量
            sort_by: 排序规则，格式为 "SortBy,SortOrder" 或 "Random"
                     例如: "DateCreated,Descending", "CommunityRating,Descending", "Random"
        """
        if not self.emby_url or not self.api_key:
            return []
            
        try:
            # 解析排序参数
            if sort_by == "Random":
                sort_field = "Random"
                sort_order = "Ascending"
            elif sort_by and ',' in sort_by:
                parts = sort_by.split(',', 1)
                sort_field = parts[0]
                sort_order = parts[1] if len(parts) > 1 else "Descending"
            else:
                # 默认按最新添加排序
                sort_field = "DateCreated,SortName"
                sort_order = "Descending"
            
            # 获取媒体库中的项目
            # 增加 HasPrimaryImage 过滤确保只获取有海报的项目
            url = f"{self.emby_url}/emby/Items"
            params = {
                "api_key": self.api_key,
                "ParentId": library_id,
                "Limit": limit * 2,  # 获取两倍数量以备某些图片下载失败
                "SortBy": sort_field,
                "SortOrder": sort_order,
                "IncludeItemTypes": "Movie,Series",
                "Recursive": True,
                "Fields": "PrimaryImageTag,ImageTags",
                "ImageTypes": "Primary",
                "HasPrimaryImage": True # 核心：只抓取已经成功刮削有海报的
            }
            resp = self._make_request('GET', url, params=params)
            resp.raise_for_status()
            
            items = resp.json().get("Items", [])
            posters = []
            
            # 使用列表随机化以增加视觉多样性 (如果是大批量墙幕)
            if limit > 10:
                random.shuffle(items)
            
            # --- 本地缓存下载流程 ---
            import shutil
            import uuid
            
            # 创建临时会话目录
            session_id = str(uuid.uuid4())[:8]
            temp_dir = os.path.join(os.environ.get('TEMP', './temp'), 'emby_posters', session_id)
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            downloaded_files = []
            count = 0
            
            logger.info(f"开始下载海报到本地缓存: {temp_dir}")
            
            for item in items:
                if count >= limit:
                    break
                    
                item_id = item.get("Id")
                if not item_id:
                    continue
                    
                try:
                    # 优化下载参数
                    img_url = f"{self.emby_url}/emby/Items/{item_id}/Images/Primary"
                    # maxWidth=400 平衡质量与速度
                    dl_params = {"api_key": self.api_key, "maxWidth": 400, "quality": 80}
                    
                    # 使用 requests Stream 下载
                    # 注意：这里我们直接用 requests，如果是用 self._make_request 可能无法 stream
                    # 但为了简单和兼容，我们这里直接 requests.get
                    with requests.get(img_url, params=dl_params, stream=True, timeout=15, proxies=self.proxies) as r:
                        if r.status_code == 200:
                            file_path = os.path.join(temp_dir, f"{item_id}.jpg")
                            with open(file_path, 'wb') as f:
                                shutil.copyfileobj(r.raw, f)
                            downloaded_files.append(file_path)
                            count += 1
                except Exception as e:
                    logger.warning(f"下载海报失败 {item_id}: {e}")
                    continue
            
            # 加载并自动清理
            posters = []
            for p_path in downloaded_files:
                try:
                    with Image.open(p_path) as img:
                        # 必须深拷贝到内存
                        posters.append(img.convert("RGBA").copy())
                except Exception as e:
                    logger.warning(f"读取缓存海报失败 {p_path}: {e}")
            
            # 清理临时文件
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info("本地临时海报已清理")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")
                
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
            
            img_resp = self._make_request('GET', img_url, params=img_params)
            if img_resp.status_code == 200:
                return Image.open(io.BytesIO(img_resp.content)).convert("RGBA")
            
            # 如果没有 Backdrop，尝试 Thumb (某些库只有Thumb)
            img_url = f"{self.emby_url}/emby/Items/{library_id}/Images/Thumb/0"
            img_resp = self._make_request('GET', img_url, params=img_params)
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
        backdrop_img: Image.Image = None,
        sticker_img: Image.Image = None
    ) -> Image.Image:
        """
        生成静态封面图
        spacing: 堆叠间距系数，默认 1.0
        angle_scale: 旋转角度系数，默认 1.0
        use_backdrop: 是否使用横幅背景
        backdrop_img: 传入的横幅背景图对象
        sticker_img: 传入的水印贴纸图对象
        """
        
        base_colors = []
        
        # === 1. 颜色策略 ===
        # 如果 theme_index == -1，启用"自动混色"模式 (从海报提取颜色)
        if theme_index == -1:
            # 从每张海报提取一个主色调
            for p in posters[:7]: # 最多采7张
                # 缩放到 1x1 获取平均色
                avg = p.resize((1, 1), Image.Resampling.LANCZOS).getpixel((0, 0))
                # 剔除 alpha 如果有
                if isinstance(avg, int): # Grayscale
                    rgb = (avg, avg, avg)
                else:
                    rgb = avg[:3]
                
                # === 增强鲜艳度 (Saturation Boost) ===
                # 创建 1x1 临时图片进行处理
                tmp_p = Image.new("RGB", (1, 1), rgb)
                # 提升饱和度 1.8x
                tmp_p = ImageEnhance.Color(tmp_p).enhance(1.8)
                # 提升亮度 1.1x (避免过于暗沉)
                tmp_p = ImageEnhance.Brightness(tmp_p).enhance(1.1)
                base_colors.append(tmp_p.getpixel((0, 0)))

            # 如果凑不够3个颜色，补一些随机变种
            while len(base_colors) < 3:
                import random
                # 随机生成高饱和度颜色
                base_colors.append((
                    random.randint(50, 250),
                    random.randint(50, 250),
                    random.randint(50, 250)
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
        import math
        from PIL import ImageFilter, ImageOps

        # 缩放系数 (基于 1920x1080 评估)
        sx_ratio = width / 1920.0
        sy_ratio = height / 1080.0
        
        # === 3. 生成布局 (Stages) ===
        stages = self._generate_layout(len(posters))
        
        # === 4. 绘制海报 ===
        # 按 Z 序(从远到近)绘制
        sorted_posters = []
        for i, (p, config) in enumerate(zip(posters, stages)):
            sorted_posters.append((config.get("z", 0), i, p, config))
        
        sorted_posters.sort(key=lambda x: x[0]) # 升序: Z 小的先画(即在底层)
        
        # 基础海报缩放 (基于高度)
        poster_h = int(height * (poster_scale_pct / 100.0))
        
        for _, i, p, config in sorted_posters:
            # 缩放海报
            sw = int(poster_h * 0.67 * config["scale"] * spacing) # 2:3 比例
            sh = int(poster_h * config["scale"])
            
            try:
                poster = p.copy()
            except Exception:
                continue # 万一图片损坏
                
            poster = poster.resize((sw, sh), Image.Resampling.LANCZOS)
            
            # === 海报圆角处理 ===
            corner_radius = int(min(sw, sh) * 0.05)
            mask = Image.new("L", (sw, sh), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.rounded_rectangle([0, 0, sw, sh], radius=corner_radius, fill=255)
            
            # 1. 透明度渐变处理
            opacity = config.get("opacity", 1.0)
            if opacity < 1.0:
                mask_data = mask.getdata()
                new_data = [int(px * opacity) for px in mask_data]
                mask.putdata(new_data)
            
            # 应用遮罩
            poster.putalpha(mask)
            
            # === 海报边缘感 ===
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
            rot_angle = -config["angle"] * angle_scale
            rotated = poster.rotate(rot_angle, expand=True, resample=Image.Resampling.BICUBIC)
            
            # 计算 Pivot 偏移
            rad = math.radians(rot_angle)
            pivot_offset = 0.3 * sh
            
            shift_x = pivot_offset * math.sin(rad)
            shift_y = pivot_offset * (1 - math.cos(rad))
            
            # 坐标缩放
            base_x = (config["x"] + offset_x) * sx_ratio
            base_y = config["y"] * sy_ratio
            
            final_cx = base_x + shift_x
            final_cy = base_y + shift_y
            
            px = int(final_cx - rotated.width / 2)
            py = int(final_cy - rotated.height / 2)
            
            # === 0. 倒影 (Reflection) ===
            if opacity > 0.3:
                try:
                    reflection = rotated.copy().transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                    ref_h = int(reflection.height * 0.6)
                    reflection = reflection.resize((reflection.width, ref_h))
                    
                    ref_mask = Image.new("L", reflection.size, 0)
                    ref_draw = ImageDraw.Draw(ref_mask)
                    for y in range(ref_h):
                        ref_alpha = int(120 * (1 - y / ref_h) * opacity * config["scale"]) 
                        ref_draw.line([(0, y), (reflection.width, y)], fill=ref_alpha)
                        
                    r_r, r_g, r_b, r_a = reflection.split()
                    from PIL import ImageChops
                    r_a = ImageChops.multiply(r_a, ref_mask)
                    reflection.putalpha(r_a)
                    
                    ref_y = py + rotated.height - int(10 * config["scale"] * sy_ratio)
                    img.paste(reflection, (px, ref_y), reflection)
                except Exception:
                    pass
            
            # === 1. 绘制主体 ===
            img.paste(rotated, (px, py), rotated)

        # === 5. 绘制文字 ===
        draw = ImageDraw.Draw(img)
        m_font = None
        s_font = None
        
        # 字体缩放
        scaled_title_size = int(title_size * min(sx_ratio, sy_ratio))
        scaled_subtitle_size = int(45 * min(sx_ratio, sy_ratio))
        
        font_candidates = [
            font_path,
            "C:\\Windows\\Fonts\\msyhbd.ttc",
            "C:\\Windows\\Fonts\\msyh.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "Arial Bold"
        ]
        
        for f_path in font_candidates:
            if not f_path: continue
            try:
                m_font = ImageFont.truetype(f_path, scaled_title_size)
                s_font = ImageFont.truetype(f_path, scaled_subtitle_size)
                break
            except Exception:
                continue
                
        if m_font is None:
            m_font = ImageFont.load_default()
            s_font = ImageFont.load_default()
        
        tx = int(width * 0.08)
        ty = int(height * (v_align_pct / 100))
        
        # 文字投影
        for off in range(1, max(2, int(12 * min(sx_ratio, sy_ratio)))):
            alpha = int(max(0, 240 - off * 18))
            draw.text((tx + off, ty + off), title, font=m_font, fill=(0, 0, 0, alpha))
            
        draw.text((tx, ty), title, font=m_font, fill="white")
        
        # 副标题
        spacing_y = int(scaled_title_size * 0.4) + int(10 * sy_ratio)
        sub_y = ty + scaled_title_size + spacing_y
        
        draw.text((tx + 2, sub_y + 2), subtitle, font=s_font, fill=(0, 0, 0, 80))
        draw.text((tx, sub_y), subtitle, font=s_font, fill=(255, 255, 255, 220))
        
        # 装饰线
        bar_y = sub_y + int(60 * sy_ratio)
        bar_height = max(1, int(4 * sy_ratio))
        bar_width = int(400 * sx_ratio)
        
        gradient_bar = Image.new('RGBA', (bar_width, bar_height), (0, 0, 0, 0))
        bar_draw = ImageDraw.Draw(gradient_bar)
        for x in range(bar_width):
            alpha = int(255 * (1 - (x / bar_width)))
            bar_draw.line([(x, 0), (x, bar_height)], fill=(255, 255, 255, alpha))
        img.paste(gradient_bar, (tx, bar_y), gradient_bar)
        
        # 水印贴纸
        if sticker_img:
            s_max_w = int(300 * sx_ratio)
            s_w, s_h = sticker_img.size
            if s_w > s_max_w:
                s_h = int(s_h * s_max_w / s_w)
                s_w = s_max_w
                sticker_to_draw = sticker_img.resize((s_w, s_h), Image.Resampling.LANCZOS)
            else:
                sticker_to_draw = sticker_img

            sx = width - s_w - int(80 * sx_ratio)
            sy = height - s_h - int(80 * sy_ratio)
            
            if sticker_to_draw.mode != 'RGBA':
                sticker_to_draw = sticker_to_draw.convert('RGBA')
            
            temp_layer = Image.new("RGBA", (width, height), (0,0,0,0))
            temp_layer.paste(sticker_to_draw, (sx, sy))
            img = Image.alpha_composite(img.convert('RGBA'), temp_layer)
        
        return img.convert('RGB')
    
    def generate_animated_cover(
        self,
        posters: List[Image.Image],
        title: str = "电影收藏",
        subtitle: str = "MOVIE COLLECTION",
        theme_index: int = 0,
        frame_count: int = 15,
        duration_ms: int = 100,
        **kwargs
    ) -> bytes:
        """
        优化后的动态 APNG 封面生成
        整合优势：
        1. 使用 apng 库组装（更可靠）
        2. 动态背景流光效果
        3. 直接渲染为目标规格 (400x225)
        """
        output_width = 400
        output_height = 225
        
        # 静态图片处理（少于2张海报时）
        if len(posters) < 2:
            static_img = self.generate_cover(posters, title, subtitle, theme_index, output_width, output_height, **kwargs)
            static_img = static_img.convert("RGBA")
            buffer = io.BytesIO()
            static_img.save(buffer, format="PNG")
            return buffer.getvalue()
        
        frames_bytes = []
        num_posters = len(posters)
        
        logger.info(f"正在生成动画帧... 共 {frame_count} 帧")
        
        # 渲染每一帧
        for frame_idx in range(frame_count):
            # 海报轮换动画
            offset = frame_idx % num_posters
            rotated_posters = posters[offset:] + posters[:offset]
            
            # 动态主题色偏移（每帧略微变化背景色调）
            # 这会让背景产生微妙的流光效果
            dynamic_theme = theme_index
            if theme_index >= 0:
                # 轻微改变主题，产生色彩变化
                # 每5帧切换到下一个主题的变体
                dynamic_theme = (theme_index + (frame_idx // 5)) % len(THEMES)
            
            # 直接按目标分辨率渲染
            frame = self.generate_cover(
                rotated_posters,
                title,
                subtitle,
                dynamic_theme,
                output_width,
                output_height,
                **kwargs
            )
            
            # 保存为 PNG 字节
            frame_rgba = frame.convert("RGBA")
            buf = io.BytesIO()
            frame_rgba.save(buf, format='PNG')
            frames_bytes.append(buf.getvalue())
        
        logger.info("正在合成 APNG...")
        
        # 尝试使用 apng 库（更可靠的 APNG 生成）
        try:
            from apng import APNG
            anim = APNG.from_bytes(frames_bytes, delay=duration_ms)
            apng_buffer = io.BytesIO()
            anim.save(apng_buffer)
            logger.info(f"APNG 生成成功（使用 apng 库），大小: {len(apng_buffer.getvalue())} bytes")
            return apng_buffer.getvalue()
        except ImportError:
            logger.warning("apng 库未安装，回退到 PIL 方式")
        except Exception as e:
            logger.warning(f"apng 库生成失败: {e}，回退到 PIL 方式")
        
        # 回退：使用 PIL 的 save_all 方式
        frames = []
        for fb in frames_bytes:
            frames.append(Image.open(io.BytesIO(fb)))
        
        buffer = io.BytesIO()
        frames[0].save(
            buffer,
            format="PNG",
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            optimize=True
        )
        
        logger.info(f"APNG 生成成功（使用 PIL），大小: {len(buffer.getvalue())} bytes")
        return buffer.getvalue()
    
    def _apply_perspective(self, img: Image.Image) -> Image.Image:
        """应用透视变形，模拟3D倾斜感"""
        return self._apply_perspective_with_intensity(img, 1.0)
    
    def _apply_perspective_with_intensity(self, img: Image.Image, intensity: float = 1.0) -> Image.Image:
        """应用透视变形，可调强度
        
        Args:
            img: 输入图片
            intensity: 透视强度 (0=无变形, 1=默认, 2=强变形)
        """
        import numpy as np
        
        if intensity <= 0:
            return img
        
        w, h = img.size
        # 源点：左上，右上，右下，左下
        src_pts = [(0, 0), (w, 0), (w, h), (0, h)]
        
        # 根据强度计算透视程度
        x_shrink = 0.15 * intensity  # 水平缩进比例
        y_shrink = 0.08 * intensity  # 垂直缩进比例
        
        # 目标点：模拟左侧向远处（Z轴）深缩，右侧保持较大
        dst_pts = [
            (int(w * x_shrink), int(h * y_shrink)),      # 左上缩进
            (w, 0),                                       # 右上不动
            (w, h),                                       # 右下不动
            (int(w * x_shrink), int(h * (1 - y_shrink))) # 左下缩进
        ]
        
        # 计算变换矩阵
        def find_coeffs(pa, pb):
            matrix = []
            for p1, p2 in zip(pa, pb):
                matrix.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0] * p1[0], -p2[0] * p1[1]])
                matrix.append([0, 0, 0, p1[0], p1[1], 1, -p2[1] * p1[0], -p2[1] * p1[1]])
            A = np.matrix(matrix, dtype=float)
            B = np.array(pb).reshape(8)
            res = np.dot(np.linalg.inv(A), B)
            return np.array(res).reshape(8)
        
        coeffs = find_coeffs(dst_pts, src_pts)
        return img.transform((w, h), Image.Transform.PERSPECTIVE, coeffs, Image.Resampling.BICUBIC)
    
    def generate_stack_animated_cover(
        self,
        posters: List[Image.Image],
        title: str = "电影收藏",
        subtitle: str = "MOVIE COLLECTION",
        theme_index: int = 0,
        total_frames: int = 50,
        fps: int = 25,
        output_size: Tuple[int, int] = (400, 225),
        font_path: str = None,
        # === 新增可调参数 ===
        card_scale: float = 1.0,           # 卡片缩放 (0.5-1.5)
        perspective_intensity: float = 1.0, # 透视强度 (0-2)
        z_spacing: float = 1.0,            # Z轴间距系数 (0.5-2)
        x_start: int = 220,                # X轴起始位置
        x_spacing: int = 55,               # X轴间距
        opacity_decay: float = 0.18,       # 透明度衰减 (每层)
        scale_decay: float = 0.12,         # 缩放衰减 (每层)
        bg_color_hex: str = None,          # 自定义背景色 (#RRGGBB)
        title_size: int = 28,              # 主标题字号
        subtitle_size: int = 12,           # 副标题字号
        title_x: int = 15,                 # 文字X位置
        title_y_offset: int = 55,          # 文字距底部偏移
        corner_radius: int = 12            # 卡片圆角半径
    ) -> bytes:
        """
        生成动态堆叠封面（透视3D效果）
        
        Args:
            posters: 海报图片列表
            title: 主标题
            subtitle: 副标题
            theme_index: 主题索引
            total_frames: 总帧数（默认50帧，约2秒）
            fps: 帧率（默认25FPS）
            output_size: 输出尺寸 (宽, 高)
            font_path: 自定义字体路径
            card_scale: 卡片整体缩放 (0.5-1.5)
            perspective_intensity: 透视变形强度 (0=无透视, 1=默认, 2=强透视)
            z_spacing: Z轴层叠紧密度 (1=默认)
            x_start: 最前面卡片的X位置
            x_spacing: 卡片间的X轴间距
            opacity_decay: 每层透明度衰减值
            scale_decay: 每层缩放衰减值
            bg_color_hex: 自定义背景色 (#RRGGBB)
            title_size: 主标题字号
            subtitle_size: 副标题字号
            title_x: 文字X位置
            title_y_offset: 文字距底部偏移
            corner_radius: 卡片圆角半径
            
        Returns:
            APNG 二进制数据
        """
        if len(posters) < 2:
            logger.warning("海报数量不足，无法生成动态堆叠")
            static_img = Image.new("RGBA", output_size, (15, 12, 25, 255))
            buf = io.BytesIO()
            static_img.save(buf, format='PNG')
            return buf.getvalue()
        
        logger.info(f"开始生成动态堆叠封面... 帧数: {total_frames}, FPS: {fps}")
        
        # 背景颜色
        if bg_color_hex:
            bg_color = self._hex_to_rgb(bg_color_hex) + (255,)
        elif theme_index >= 0 and theme_index < len(THEMES):
            bg_hex = THEMES[theme_index]["colors"][0]
            bg_color = self._hex_to_rgb(bg_hex) + (255,)
        else:
            bg_color = (15, 12, 25, 255)
        
        # 预处理海报：统一大小、圆角、透视
        base_card_width, base_card_height = 160, 240
        card_width = int(base_card_width * card_scale)
        card_height = int(base_card_height * card_scale)
        processed_posters = []
        
        for p in posters[:7]:  # 最多使用7张
            try:
                p = p.convert("RGBA")
                p = p.resize((card_width, card_height), Image.Resampling.LANCZOS)
                
                # 添加圆角
                mask = Image.new('L', p.size, 0)
                ImageDraw.Draw(mask).rounded_rectangle((0, 0, p.width, p.height), corner_radius, fill=255)
                p.putalpha(mask)
                
                # 应用透视变形（根据强度）
                if perspective_intensity > 0:
                    p = self._apply_perspective_with_intensity(p, perspective_intensity)
                processed_posters.append(p)
            except Exception as e:
                logger.warning(f"处理海报失败: {e}")
                continue
        
        if len(processed_posters) < 2:
            logger.warning("有效海报数量不足")
            static_img = Image.new("RGBA", output_size, bg_color)
            buf = io.BytesIO()
            static_img.save(buf, format='PNG')
            return buf.getvalue()
        
        frames_bytes = []
        num_posters = len(processed_posters)
        
        # 准备字体
        m_font = None
        s_font = None
        font_candidates = [
            font_path,
            "C:\\Windows\\Fonts\\msyhbd.ttc",
            "C:\\Windows\\Fonts\\msyh.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        
        for f_path in font_candidates:
            if not f_path:
                continue
            try:
                m_font = ImageFont.truetype(f_path, title_size)
                s_font = ImageFont.truetype(f_path, subtitle_size)
                break
            except Exception:
                continue
        
        if m_font is None:
            m_font = ImageFont.load_default()
            s_font = ImageFont.load_default()
        
        # 生成每一帧
        for f in range(total_frames):
            # 创建背景画布
            canvas = Image.new("RGBA", output_size, bg_color)
            progress = f / total_frames
            
            # 绘制海报（从后往前绘制，越后面的越靠前）
            for i in range(num_posters - 1, -1, -1):
                pos = (i - progress) % num_posters
                
                # 计算 Z 轴效果：越往后（pos越大）越小、越靠左、越透明
                z_factor = 1.0 - (pos * scale_decay * z_spacing)
                opacity = 1.0 - (pos * opacity_decay * z_spacing)
                x_pos = int(x_start - pos * x_spacing * z_spacing)  # X轴位置
                
                # 复制并缩放
                img = processed_posters[i].copy()
                nw, nh = int(img.width * z_factor), int(img.height * z_factor)
                if nw < 10 or nh < 10:
                    continue
                img = img.resize((nw, nh), Image.Resampling.LANCZOS)
                
                # 透明度处理
                alpha = img.getchannel('A')
                alpha = ImageEnhance.Brightness(alpha).enhance(max(0.1, opacity))
                img.putalpha(alpha)
                
                # 计算 Y 位置（居中）
                y_pos = (output_size[1] - nh) // 2
                
                # 创建临时层并粘贴
                temp = Image.new("RGBA", output_size, (0, 0, 0, 0))
                temp.paste(img, (x_pos, y_pos))
                canvas = Image.alpha_composite(canvas, temp)
            
            # 添加文字
            draw = ImageDraw.Draw(canvas)
            
            # 主标题 (使用参数化位置)
            text_x = title_x
            text_y = output_size[1] - title_y_offset
            
            # 文字阴影
            draw.text((text_x + 1, text_y + 1), title, font=m_font, fill=(0, 0, 0, 150))
            draw.text((text_x, text_y), title, font=m_font, fill=(255, 255, 255, 255))
            
            # 副标题
            if subtitle:
                sub_y = text_y + 32
                draw.text((text_x + 1, sub_y + 1), subtitle, font=s_font, fill=(0, 0, 0, 100))
                draw.text((text_x, sub_y), subtitle, font=s_font, fill=(180, 180, 180, 220))
            
            # 保存帧
            buf = io.BytesIO()
            canvas.save(buf, format='PNG')
            frames_bytes.append(buf.getvalue())
        
        logger.info(f"帧渲染完成，正在合成 APNG...")
        
        # 计算帧间隔 (毫秒)
        duration_ms = int(1000 / fps)
        
        # 尝试使用 apng 库
        try:
            from apng import APNG
            anim = APNG.from_bytes(frames_bytes, delay=duration_ms)
            apng_buffer = io.BytesIO()
            anim.save(apng_buffer)
            logger.info(f"动态堆叠 APNG 生成成功（apng库），大小: {len(apng_buffer.getvalue())} bytes")
            return apng_buffer.getvalue()
        except ImportError:
            logger.warning("apng 库未安装，回退到 PIL 方式")
        except Exception as e:
            logger.warning(f"apng 库生成失败: {e}，回退到 PIL 方式")
        
        # 回退：使用 PIL
        frames = []
        for fb in frames_bytes:
            frames.append(Image.open(io.BytesIO(fb)))
        
        buffer = io.BytesIO()
        frames[0].save(
            buffer,
            format="PNG",
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            optimize=True
        )
        
        logger.info(f"动态堆叠 APNG 生成成功（PIL），大小: {len(buffer.getvalue())} bytes")
        return buffer.getvalue()
    
    def generate_wall_animated_cover(
        self,
        posters: List[Image.Image],
        title: str = "电影收藏",
        subtitle: str = "MOVIE COLLECTION",
        theme_index: int = 0,
        mode: str = 'tilt',  # 'scroll' 或 'tilt'
        total_frames: int = 40,
        fps: int = 10,
        output_size: Tuple[int, int] = (400, 225),
        font_path: str = None,
        # 可调参数
        saturation: float = 1.4,        # 饱和度 (scroll模式)
        brightness: float = 0.4,        # 亮度 (tilt模式)
        tilt_angle: float = 15,         # 倾斜角度
        scroll_range_x: int = 200,      # X滚动范围
        scroll_range_y: int = 500,      # Y滚动范围 (scroll模式)
        tilt_move: int = 40,            # 移动范围 (tilt模式)
        poster_width: int = 100,        # 海报宽度
        poster_height: int = 150,       # 海报高度
        grid_gap_x: int = 5,            # 网格X间距
        grid_gap_y: int = 5,            # 网格Y间距
        accent_color: Tuple[int, int, int] = (0, 162, 138),  # 胶囊颜色
        title_size: int = 30,
        subtitle_size: int = 14,
        bg_color_hex: str = None
    ) -> bytes:
        """
        生成流体墙幕封面（海报墙网格动画）
        
        Args:
            posters: 海报图片列表
            title: 主标题
            subtitle: 副标题
            theme_index: 主题索引
            mode: 模式 'scroll'(全屏滚动) 或 'tilt'(倾斜带文字)
            total_frames: 总帧数
            fps: 帧率
            output_size: 输出尺寸
            font_path: 字体路径
            saturation: 饱和度
            brightness: 亮度（tilt模式下背景变暗）
            tilt_angle: 倾斜角度
            scroll_range_x: 滚动范围X
            scroll_range_y: 滚动范围Y
            tilt_move: 倾斜模式移动范围
            poster_width: 海报宽度
            poster_height: 海报高度
            grid_gap_x: 网格X间距
            grid_gap_y: 网格Y间距
            accent_color: 副标题胶囊背景色
            title_size: 主标题字号
            subtitle_size: 副标题字号
            bg_color_hex: 自定义背景色
            
        Returns:
            APNG 二进制数据
        """
        if len(posters) < 4:
            logger.warning("海报数量不足，无法生成流体墙幕")
            static_img = Image.new("RGBA", output_size, (15, 15, 15, 255))
            buf = io.BytesIO()
            static_img.save(buf, format='PNG')
            return buf.getvalue()
        
        logger.info(f"开始生成流体墙幕封面... 模式: {mode}, 帧数: {total_frames}")
        
        # 背景颜色
        if bg_color_hex:
            bg_color = self._hex_to_rgb(bg_color_hex) + (255,)
        elif theme_index >= 0 and theme_index < len(THEMES):
            bg_hex = THEMES[theme_index]["colors"][0]
            bg_color = self._hex_to_rgb(bg_hex) + (255,)
        else:
            bg_color = (15, 15, 15, 255)
        
        # 预处理海报：统一大小
        processed_posters = []
        for p in posters:
            try:
                p = p.convert("RGBA")
                p = p.resize((poster_width, poster_height), Image.Resampling.LANCZOS)
                processed_posters.append(p)
            except Exception as e:
                logger.warning(f"处理海报失败: {e}")
                continue
        
        if len(processed_posters) < 4:
            logger.warning("有效海报数量不足")
            static_img = Image.new("RGBA", output_size, bg_color)
            buf = io.BytesIO()
            static_img.save(buf, format='PNG')
            return buf.getvalue()
        
        # 计算网格尺寸
        cell_w = poster_width + grid_gap_x
        cell_h = poster_height + grid_gap_y
        
        # 根据模式生成不同的动画
        if mode == 'scroll':
            frames_bytes = self._generate_scroll_frames(
                processed_posters, output_size, total_frames,
                cell_w, cell_h, bg_color, saturation, scroll_range_x, scroll_range_y
            )
        else:  # tilt 模式
            frames_bytes = self._generate_tilt_frames(
                processed_posters, output_size, total_frames,
                cell_w, cell_h, bg_color, brightness, tilt_angle, tilt_move,
                title, subtitle, font_path, title_size, subtitle_size, accent_color
            )
        
        logger.info(f"帧渲染完成，正在合成 APNG...")
        
        # 计算帧间隔 (毫秒)
        duration_ms = int(1000 / fps)
        
        # 尝试使用 apng 库
        try:
            from apng import APNG
            anim = APNG.from_bytes(frames_bytes, delay=duration_ms)
            apng_buffer = io.BytesIO()
            anim.save(apng_buffer)
            logger.info(f"流体墙幕 APNG 生成成功（apng库），大小: {len(apng_buffer.getvalue())} bytes")
            return apng_buffer.getvalue()
        except ImportError:
            logger.warning("apng 库未安装，回退到 PIL 方式")
        except Exception as e:
            logger.warning(f"apng 库生成失败: {e}，回退到 PIL 方式")
        
        # 回退：使用 PIL
        frames = []
        for fb in frames_bytes:
            frames.append(Image.open(io.BytesIO(fb)))
        
        buffer = io.BytesIO()
        frames[0].save(
            buffer,
            format="PNG",
            save_all=True,
            append_images=frames[1:],
            duration=duration_ms,
            loop=0,
            optimize=True
        )
        
        logger.info(f"流体墙幕 APNG 生成成功（PIL），大小: {len(buffer.getvalue())} bytes")
        return buffer.getvalue()
    
    def _generate_scroll_frames(
        self, posters, output_size, total_frames,
        cell_w, cell_h, bg_color, saturation, scroll_range_x, scroll_range_y
    ) -> List[bytes]:
        """生成滚动模式帧"""
        # 创建大画布（6x6 网格）
        canvas_w = 6 * cell_w + scroll_range_x
        canvas_h = 6 * cell_h + scroll_range_y
        canvas = Image.new('RGBA', (canvas_w, canvas_h), bg_color)
        
        # 铺设海报网格
        for i in range(8):
            for j in range(8):
                idx = (i * 8 + j) % len(posters)
                canvas.paste(posters[idx], (j * cell_w, i * cell_h))
        
        # 调整饱和度
        canvas = ImageEnhance.Color(canvas).enhance(saturation)
        
        frames_bytes = []
        for f in range(total_frames):
            progress = f / total_frames
            off_x = int(scroll_range_x * progress)
            off_y = int(scroll_range_y * progress)
            
            # 裁剪
            frame = canvas.crop((off_x, off_y, off_x + output_size[0], off_y + output_size[1]))
            
            buf = io.BytesIO()
            frame.save(buf, format='PNG')
            frames_bytes.append(buf.getvalue())
        
        return frames_bytes
    
    def _generate_tilt_frames(
        self, posters, output_size, total_frames,
        cell_w, cell_h, bg_color, brightness, tilt_angle, tilt_move,
        title, subtitle, font_path, title_size, subtitle_size, accent_color
    ) -> List[bytes]:
        """生成倾斜UI模式帧"""
        # 创建更大的画布用于旋转
        canvas_size = 900
        canvas = Image.new('RGBA', (canvas_size, canvas_size), bg_color)
        
        # 铺设海报网格（交错排列）
        for i in range(8):
            for j in range(9):
                idx = (i * 9 + j) % len(posters)
                x_offset = j * cell_w + (25 if i % 2 == 0 else 0)
                canvas.paste(posters[idx], (x_offset, i * cell_h))
        
        # 旋转
        canvas = canvas.rotate(tilt_angle, resample=Image.Resampling.BICUBIC, expand=False)
        
        # 压暗
        canvas = ImageEnhance.Brightness(canvas).enhance(brightness)
        
        # 准备字体
        m_font = None
        s_font = None
        font_candidates = [
            font_path,
            "C:\\Windows\\Fonts\\msyhbd.ttc",
            "C:\\Windows\\Fonts\\msyh.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        
        for f_path in font_candidates:
            if not f_path:
                continue
            try:
                m_font = ImageFont.truetype(f_path, title_size)
                s_font = ImageFont.truetype(f_path, subtitle_size)
                break
            except Exception:
                continue
        
        if m_font is None:
            m_font = ImageFont.load_default()
            s_font = ImageFont.load_default()
        
        frames_bytes = []
        crop_start_x = 200
        crop_start_y = 200
        
        for f in range(total_frames):
            progress = f / total_frames
            move = int(tilt_move * progress)
            
            # 裁剪移动的区域
            x1 = crop_start_x + move
            y1 = crop_start_y + move
            x2 = x1 + output_size[0]
            y2 = y1 + output_size[1]
            
            frame = canvas.crop((x1, y1, x2, y2)).convert("RGBA")
            
            # 绘制 UI
            draw = ImageDraw.Draw(frame)
            cx = output_size[0] // 2
            cy = output_size[1] // 2
            
            # 主标题
            draw.text((cx + 1, cy - 19), title, fill=(0, 0, 0, 150), anchor="mm", font=m_font)
            draw.text((cx, cy - 20), title, fill="white", anchor="mm", font=m_font)
            
            # 副标题胶囊
            if subtitle:
                try:
                    tw = draw.textlength(subtitle, font=s_font)
                except:
                    tw = len(subtitle) * subtitle_size * 0.6
                
                pill_x1 = cx - tw / 2 - 10
                pill_y1 = cy + 15
                pill_x2 = cx + tw / 2 + 10
                pill_y2 = cy + 38
                
                draw.rounded_rectangle(
                    [pill_x1, pill_y1, pill_x2, pill_y2],
                    radius=4,
                    fill=accent_color + (255,)
                )
                draw.text((cx, cy + 26), subtitle, fill="white", anchor="mm", font=s_font)
            
            buf = io.BytesIO()
            frame.save(buf, format='PNG')
            frames_bytes.append(buf.getvalue())
        
        return frames_bytes
    
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
        
        # 修正 Content-Type 格式 (Emby 需要 Image/jpeg 或 Image/png 格式)
        if content_type == "image/png":
            emby_content_type = "image/png"
        elif content_type == "image/gif":
            emby_content_type = "image/gif"
        elif content_type == "image/jpeg":
            emby_content_type = "image/jpeg"
        else:
            emby_content_type = "image/png"
        
        # 尝试多种 URL 格式 (有些 Emby 安装需要 /emby 前缀，有些不需要)
        base_url = self.emby_url.rstrip('/')
        url_patterns = [
            f"{base_url}/emby/Items/{library_id}/Images/Primary",  # 带 /emby 前缀（优先）
            f"{base_url}/Items/{library_id}/Images/Primary",  # 不带 /emby 前缀
        ]
        
        # 使用 X-Emby-Token header（更标准的认证方式）
        headers = {
            "Content-Type": emby_content_type,
            "X-Emby-Token": self.api_key
        }
        
        logger.info(f"正在上传封面, 大小: {len(image_data)} bytes, 类型: {emby_content_type}")
        
        for url in url_patterns:
            try:
                logger.info(f"尝试上传到: {url}")
                
                # Emby API 接受 binary body
                resp = self._make_request('POST', url, headers=headers, data=image_data, timeout=60)
                
                # Emby 可能返回 200, 201, 或 204 表示成功
                if resp.status_code in [200, 201, 204]:
                    logger.info(f"封面上传成功: {library_id} (状态码: {resp.status_code})")
                    return True
                else:
                    logger.warning(f"封面上传尝试失败: {url} HTTP {resp.status_code} - {resp.text[:200] if resp.text else '无响应内容'}")
                    
            except requests.Timeout:
                logger.warning(f"封面上传超时: {url}")
            except requests.ConnectionError as e:
                logger.warning(f"封面上传连接失败: {url} - {e}")
            except Exception as e:
                logger.warning(f"封面上传异常: {url} - {e}")
        
        logger.error(f"封面上传失败: {library_id} (所有 URL 格式均失败)")
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
