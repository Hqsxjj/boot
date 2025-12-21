"""
诊断 115 二维码生成问题
直接测试 StandardClientHolder.start_qrcode 方法
"""

import sys
import os

# 添加 backend 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from p115_bridge import StandardClientHolder

def test_qr_generation():
    print("=" * 60)
    print("测试 115 二维码生成")
    print("=" * 60)
    
    holder = StandardClientHolder(secret_store=None)
    result = holder.start_qrcode(app="tv")
    
    print(f"\n返回结果:")
    print(f"  state: {result.get('state')}")
    print(f"  uid: {result.get('uid')}")
    print(f"  msg: {result.get('msg')}")
    
    qrcode = result.get('qrcode', '')
    if qrcode:
        print(f"\n二维码数据:")
        print(f"  长度: {len(qrcode)}")
        print(f"  前缀: {qrcode[:50]}...")
        
        # 检查是否有 data URL 前缀
        if qrcode.startswith('data:image'):
            print(f"  ✅ 正确! 有 data URL 前缀")
        else:
            print(f"  ❌ 错误! 没有 data URL 前缀")
            print(f"  前 100 字符: {qrcode[:100]}")
    else:
        print(f"\n❌ 没有返回二维码数据")

if __name__ == "__main__":
    test_qr_generation()
