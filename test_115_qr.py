"""测试 115 原生客户端"""
import sys
sys.path.insert(0, "backend")

from services.p115_open_client import P115CookieClient, P115OpenClient

print("=" * 50)
print("测试 P115CookieClient")
print("=" * 50)

try:
    client = P115CookieClient()
    result = client.generate_qrcode("tv")
    
    if result.get("success"):
        uid = result.get("uid", "")
        print(f"✓ 二维码生成成功!")
        print(f"  UID: {uid[:16]}...")
        print(f"  Time: {result.get('time')}")
        print(f"  Sign: {result.get('sign', '')[:16]}...")
        print(f"  QR Image: {'有' if result.get('qrcode') else '无'}")
    else:
        print(f"✗ 二维码生成失败: {result.get('error')}")
except Exception as e:
    print(f"✗ 异常: {e}")

print()
print("=" * 50)
print("测试 P115OpenClient")
print("=" * 50)

try:
    open_client = P115OpenClient(app_id="100197531")
    result = open_client.generate_qrcode()
    
    if result.get("success"):
        uid = result.get("uid", "")
        print(f"✓ Open 二维码生成成功!")
        print(f"  UID: {uid[:16]}...")
        print(f"  QR Image: {'有' if result.get('qrcode') else '无'}")
    else:
        print(f"✗ 二维码生成失败: {result.get('error')}")
except Exception as e:
    print(f"✗ 异常: {e}")
