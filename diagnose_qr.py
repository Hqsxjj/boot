
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("diagnose")

def test_qr_download():
    # 模拟一个 UID（虽然无效，但测试 API 连通性）
    uid = "1234567890"
    target_app = "tv"
    url = f"https://qrcodeapi.115.com/api/1.0/{target_app}/1.0/qrcode?uid={uid}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://115.com/"
    }

    try:
        print(f"Requesting: {url}")
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {resp.status_code}")
        print(f"Headers: {resp.headers}")
        print(f"Content-Length: {len(resp.content)}")
        print(f"Content-Type: {resp.headers.get('Content-Type')}")
        
        if len(resp.content) > 0:
            print(f"First 20 bytes: {resp.content[:20]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_qr_download()
