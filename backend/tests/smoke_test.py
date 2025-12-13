#!/usr/bin/env python3
"""
Smoke test for Flask backend API.
Tests the complete workflow: login -> get config -> update config -> verify changes.
"""

import requests
import json
import sys


def smoke_test(base_url="http://localhost:8000"):
    """Run smoke tests against a running Flask server."""
    print(f"Running smoke tests against {base_url}")
    print("=" * 60)
    
    # Test 1: Health check
    print("\n1. Testing health check endpoint...")
    response = requests.get(f"{base_url}/api/health")
    assert response.status_code == 200, "Health check failed"
    data = response.json()
    assert data["success"] is True, "Health check returned error"
    print("   ✓ Health check passed")
    
    # Test 2: Login
    print("\n2. Testing login...")
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "smoketest123"}
    )
    assert response.status_code == 200, f"Login failed: {response.status_code}"
    data = response.json()
    assert data["success"] is True, "Login returned error"
    token = data["data"]["token"]
    print("   ✓ Login successful")
    print(f"   Token: {token[:50]}...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 3: Get user info
    print("\n3. Testing /api/me endpoint...")
    response = requests.get(f"{base_url}/api/me", headers=headers)
    assert response.status_code == 200, "Failed to get user info"
    data = response.json()
    assert data["success"] is True, "Get user info returned error"
    assert data["data"]["username"] == "admin", "Wrong username"
    print("   ✓ User info retrieved")
    print(f"   Username: {data['data']['username']}")
    print(f"   2FA Enabled: {data['data']['twoFactorEnabled']}")
    
    # Test 4: Get config
    print("\n4. Testing get config...")
    response = requests.get(f"{base_url}/api/config", headers=headers)
    assert response.status_code == 200, "Failed to get config"
    data = response.json()
    assert data["success"] is True, "Get config returned error"
    config = data["data"]
    assert "telegram" in config, "Config missing telegram section"
    assert "cloud115" in config, "Config missing cloud115 section"
    print("   ✓ Config retrieved")
    print(f"   Config sections: {', '.join(config.keys())}")
    
    # Test 5: Update config
    print("\n5. Testing update config...")
    config["telegram"]["botToken"] = "smoke-test-token-12345"
    config["telegram"]["adminUserId"] = "999888777"
    response = requests.put(
        f"{base_url}/api/config",
        json=config,
        headers=headers
    )
    assert response.status_code == 200, "Failed to update config"
    data = response.json()
    assert data["success"] is True, "Update config returned error"
    updated_config = data["data"]
    assert updated_config["telegram"]["botToken"] == "smoke-test-token-12345", "Config not updated"
    assert updated_config["telegram"]["adminUserId"] == "999888777", "Config not updated"
    print("   ✓ Config updated")
    print(f"   Bot Token: {updated_config['telegram']['botToken']}")
    print(f"   Admin User ID: {updated_config['telegram']['adminUserId']}")
    
    # Test 6: Verify persistence
    print("\n6. Testing config persistence...")
    response = requests.get(f"{base_url}/api/config", headers=headers)
    assert response.status_code == 200, "Failed to get config again"
    data = response.json()
    config = data["data"]
    assert config["telegram"]["botToken"] == "smoke-test-token-12345", "Config not persisted"
    assert config["telegram"]["adminUserId"] == "999888777", "Config not persisted"
    print("   ✓ Config persisted correctly")
    
    # Test 7: Test unauthorized access
    print("\n7. Testing authentication requirement...")
    response = requests.get(f"{base_url}/api/config")
    assert response.status_code == 401, "Should require authentication"
    print("   ✓ Authentication properly enforced")
    
    # Test 8: Test wrong credentials
    print("\n8. Testing wrong credentials...")
    response = requests.post(
        f"{base_url}/api/auth/login",
        json={"username": "admin", "password": "wrongpassword"}
    )
    assert response.status_code == 401, "Should reject wrong password"
    print("   ✓ Wrong credentials rejected")
    
    print("\n" + "=" * 60)
    print("All smoke tests passed! ✓")
    print("=" * 60)
    return True


if __name__ == "__main__":
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    
    try:
        smoke_test(base_url)
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"\n✗ Could not connect to {base_url}")
        print("Make sure the Flask server is running:")
        print("  cd backend && DATA_PATH=/tmp/test.json python main.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
