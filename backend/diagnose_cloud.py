#!/usr/bin/env python
"""
诊断脚本 - 测试云盘服务和SecretStore是否正常工作
"""
import os
import sys
import json

# 添加后端目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def main():
    print("=" * 60)
    print("云盘服务诊断脚本")
    print("=" * 60)
    
    # 1. 测试数据库初始化
    print("\n[1] 测试数据库初始化...")
    try:
        from models.database import init_all_databases, get_session_factory
        secrets_engine, appdata_engine = init_all_databases()
        secrets_session_factory = get_session_factory(secrets_engine)
        print(f"    ✓ Secrets DB: {secrets_engine.url}")
        print(f"    ✓ AppData DB: {appdata_engine.url}")
    except Exception as e:
        print(f"    ✗ 数据库初始化失败: {e}")
        return
    
    # 2. 测试 SecretStore
    print("\n[2] 测试 SecretStore...")
    try:
        from services.secret_store import SecretStore
        secret_store = SecretStore(secrets_session_factory)
        
        # 测试写入
        test_result = secret_store.set_secret('_test_key', 'test_value')
        if test_result:
            print("    ✓ 写入测试成功")
        else:
            print("    ✗ 写入测试失败")
        
        # 测试读取
        read_value = secret_store.get_secret('_test_key')
        if read_value == 'test_value':
            print("    ✓ 读取测试成功")
        else:
            print(f"    ✗ 读取测试失败: 期望 'test_value', 实际 '{read_value}'")
        
        # 清理
        secret_store.delete_secret('_test_key')
        print("    ✓ 删除测试成功")
        
    except Exception as e:
        print(f"    ✗ SecretStore 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. 检查现有凭证
    print("\n[3] 检查已保存的凭证...")
    
    # 115 Cookies
    cookies_115 = secret_store.get_secret('cloud115_cookies')
    if cookies_115:
        try:
            cookies = json.loads(cookies_115)
            print(f"    ✓ 115 Cookies 存在, 包含 {len(cookies)} 个键")
        except:
            print(f"    ⚠ 115 Cookies 存在但格式无效")
    else:
        print("    ✗ 115 Cookies 不存在")
    
    # 123 OAuth 凭证
    oauth_123 = secret_store.get_secret('cloud123_oauth_credentials')
    if oauth_123:
        try:
            creds = json.loads(oauth_123)
            client_id = creds.get('clientId', '')
            print(f"    ✓ 123 OAuth 凭证存在, clientId: {client_id[:8]}..." if len(client_id) > 8 else f"    ✓ 123 OAuth 凭证存在")
        except:
            print(f"    ⚠ 123 OAuth 凭证存在但格式无效")
    else:
        print("    ✗ 123 OAuth 凭证不存在")
    
    # 123 Token
    token_123 = secret_store.get_secret('cloud123_token')
    if token_123:
        try:
            token_data = json.loads(token_123)
            expires_at = token_data.get('expires_at', 'unknown')
            print(f"    ✓ 123 Token 存在, 过期时间: {expires_at}")
        except:
            print(f"    ⚠ 123 Token 存在但格式无效")
    else:
        print("    ✗ 123 Token 不存在")
    
    # 4. 测试 Cloud115Service
    print("\n[4] 测试 Cloud115Service...")
    try:
        from services.cloud115_service import Cloud115Service
        cloud115 = Cloud115Service(secret_store)
        
        if cloud115.p115client:
            print("    ✓ p115client 已安装")
        else:
            print("    ⚠ p115client 未安装")
        
        # 尝试获取client
        if cookies_115:
            try:
                client = cloud115._get_authenticated_client()
                print("    ✓ 115 客户端创建成功")
            except Exception as e:
                print(f"    ✗ 115 客户端创建失败: {e}")
        else:
            print("    - 跳过客户端测试 (无 cookies)")
            
    except Exception as e:
        print(f"    ✗ Cloud115Service 测试失败: {e}")
    
    # 5. 测试 Cloud123Service
    print("\n[5] 测试 Cloud123Service...")
    try:
        from services.cloud123_service import Cloud123Service
        cloud123 = Cloud123Service(secret_store)
        
        if oauth_123:
            token = cloud123._get_access_token()
            if token:
                print(f"    ✓ 123 Access Token 获取成功: {token[:16]}...")
            else:
                print("    ✗ 123 Access Token 获取失败")
        else:
            print("    - 跳过 token 测试 (无 OAuth 凭证)")
            
    except Exception as e:
        print(f"    ✗ Cloud123Service 测试失败: {e}")
    
    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)


if __name__ == '__main__':
    main()
