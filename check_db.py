import sqlite3
import os
import json

def get_data_dir():
    data_dir = os.environ.get('DATA_DIR', 'data')
    if not os.path.isabs(data_dir):
        # Try a few common locations
        candidates = [
            os.getcwd(),
            os.path.dirname(os.path.abspath(__file__)),
        ]
        for candidate in candidates:
            path = os.path.join(candidate, data_dir)
            if os.path.exists(path):
                return path
    return os.path.abspath(data_dir)

data_dir = get_data_dir()
print(f"Checking data directory: {data_dir}")

appdata_path = os.path.join(data_dir, 'appdata.db')
secrets_path = os.path.join(data_dir, 'secrets.db')

def check_appdata():
    if not os.path.exists(appdata_path):
        print("appdata.db not found")
        return
    
    print("\n--- Config Entries ---")
    conn = sqlite3.connect(appdata_path)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM config_entries WHERE key LIKE 'organize.ai.%' OR key LIKE 'cloud123.%'")
    rows = cursor.fetchall()
    for row in rows:
        print(f"{row[0]}: {row[1]}")
    conn.close()

def check_secrets():
    if not os.path.exists(secrets_path):
        print("secrets.db not found")
        return
    
    print("\n--- Secrets ---")
    conn = sqlite3.connect(secrets_path)
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM secrets WHERE key LIKE 'llm_%' OR key LIKE 'cloud123%'")
    rows = cursor.fetchall()
    for row in rows:
        val = row[1]
        if 'token' in row[0].lower() or 'secret' in row[0].lower() or 'key' in row[0].lower():
            if val and len(val) > 10:
                val = val[:10] + "..."
        print(f"{row[0]}: {val}")
    conn.close()

check_appdata()
check_secrets()
