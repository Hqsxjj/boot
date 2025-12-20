import uvicorn
import logging
import json
import os
import time
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# --- 初始化 ---
app = FastAPI()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 端口配置
PORT = 18080

# 配置跨域 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_FILE = "config.json"

# --- 数据模型 (对应前端结构) ---

class NotificationConfig(BaseModel):
    forwardToTelegram: bool = False
    playbackReportingFreq: str = "daily" # daily, weekly, monthly

class MissingEpisodesConfig(BaseModel):
    cronSchedule: str = "0 0 * * *"

class EmbyConfigDetail(BaseModel):
    serverUrl: str = ""
    apiKey: str = ""
    refreshAfterOrganize: bool = False
    notifications: NotificationConfig = NotificationConfig()
    missingEpisodes: MissingEpisodesConfig = MissingEpisodesConfig()

class AppConfig(BaseModel):
    emby: EmbyConfigDetail
    # 这里预留给其他模块（如 115）
    # p115: Dict[str, Any] = {} 

# --- 核心逻辑 ---

class MediaChecker:
    def __init__(self, config):
        self.config = config

    def check_connection(self):
        """测试 Emby 连接并返回延迟"""
        url = self.config.get('emby', {}).get('serverUrl')
        api_key = self.config.get('emby', {}).get('apiKey')
        
        if not url or not api_key:
            return {"success": False, "latency": 0, "msg": "未配置地址或密钥"}

        # 去掉结尾斜杠
        url = url.rstrip('/')
        
        # 判断是否需要跳过 SSL 验证（HTTPS 自签名证书）
        verify_ssl = not url.startswith('https://')
        
        try:
            start_time = time.time()
            # 请求 Emby 系统信息接口，跳过 SSL 验证以支持自签名证书
            resp = requests.get(
                f"{url}/emby/System/Info", 
                params={"api_key": api_key}, 
                timeout=10,
                verify=verify_ssl
            )
            latency = int((time.time() - start_time) * 1000)
            
            if resp.status_code == 200:
                return {"success": True, "latency": latency, "serverName": resp.json().get("ServerName", "Emby")}
            elif resp.status_code == 401:
                return {"success": False, "latency": latency, "msg": "API Key 无效"}
            else:
                return {"success": False, "latency": latency, "msg": f"HTTP {resp.status_code}"}
        except requests.Timeout:
            return {"success": False, "latency": 0, "msg": "连接超时"}
        except Exception as e:
            error_str = str(e).lower()
            if 'ssl' in error_str or 'certificate' in error_str:
                return {"success": False, "latency": 0, "msg": "SSL 证书错误"}
            return {"success": False, "latency": 0, "msg": f"连接失败: {str(e)[:50]}"}

    def get_missing_episodes(self):
        """(模拟) 缺集检测逻辑"""
        # 实际逻辑应调用 TMDB 和 Emby API
        time.sleep(1) # 模拟耗时
        return [
            { "id": 1, "name": "西部世界 (Westworld)", "season": 4, "totalEp": 8, "localEp": 6, "missing": "7, 8", "poster": "https://image.tmdb.org/t/p/w200/80i5tai0IqGvB6o2t8b78F2dJ1e.jpg" },
            { "id": 2, "name": "曼达洛人 (The Mandalorian)", "season": 3, "totalEp": 8, "localEp": 7, "missing": "8", "poster": "https://image.tmdb.org/t/p/w200/eU1i6eHXlzMOlEq0ku1Rzq7Y4wA.jpg" },
            { "id": 3, "name": "最后生还者 (The Last of Us)", "season": 1, "totalEp": 9, "localEp": 5, "missing": "6, 7, 8, 9", "poster": "https://image.tmdb.org/t/p/w200/uKvVjHNqB5VmOrdxqAt2F7J78Tw.jpg" },
        ]

# --- 全局状态管理 ---
current_config = {}
scheduler = BackgroundScheduler()
scheduler.start()

def load_config():
    global current_config
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                current_config = json.load(f)
        except:
            pass # 加载失败使用默认
    
    # 确保结构完整
    if "emby" not in current_config:
        current_config["emby"] = EmbyConfigDetail().dict()

def save_config_file():
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(current_config, f, indent=2, ensure_ascii=False)

def update_job():
    scheduler.remove_all_jobs()
    cron = current_config.get('emby', {}).get('missingEpisodes', {}).get('cronSchedule', "0 0 * * *")
    try:
        trigger = CronTrigger.from_crontab(cron)
        scheduler.add_job(run_scan_job, trigger)
        logger.info(f"Cron 更新: {cron}")
    except:
        logger.error(f"Cron 格式错误: {cron}")

def run_scan_job():
    logger.info("执行定时任务：缺集扫描...")
    # 这里可以添加发送通知的代码

# --- API 路由 ---

@app.on_event("startup")
async def startup():
    load_config()
    update_job()
    logger.info(f"服务已启动: http://localhost:{PORT}")

@app.get("/api/config")
async def get_config():
    return current_config

@app.post("/api/config")
async def save_config(config: AppConfig):
    global current_config
    current_config = config.dict()
    save_config_file()
    update_job()
    return {"status": "success"}

# 1. 连接测试接口 (对应前端 "服务器连接" 面板)
@app.post("/api/emby/test-connection")
async def test_connection():
    checker = MediaChecker(current_config)
    result = checker.check_connection()
    return result

# 2. 缺集扫描接口 (对应前端 "立即检测" 按钮)
@app.post("/api/emby/scan-missing")
async def scan_missing():
    checker = MediaChecker(current_config)
    data = checker.get_missing_episodes()
    return {"status": "success", "data": data}

# 3. Webhook 接收接口 (对应前端 "Webhook 回调地址")
@app.post("/api/webhook/115bot")
async def webhook_receiver(request: Request):
    """
    接收 Emby 发送的 Webhook 事件
    """
    try:
        data = await request.json()
        event_type = data.get("Event", "Unknown")
        logger.info(f"收到 Emby Webhook: {event_type}")
        
        # 检查是否开启了转发通知
        if current_config.get('emby', {}).get('notifications', {}).get('forwardToTelegram'):
             logger.info("-> 准备转发消息到 Telegram (逻辑待实现)...")
             
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Webhook 处理失败: {e}")
        return {"status": "error"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)