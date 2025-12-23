import sqlite3
import os

db_path = r'c:\boot\backend\data\appdata.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("Tables in appdata.db:", cursor.fetchall())
    conn.close()

db_path_secrets = r'c:\boot\backend\data\secrets.db'
if os.path.exists(db_path_secrets):
    conn = sqlite3.connect(db_path_secrets)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    print("Tables in secrets.db:", cursor.fetchall())
    conn.close()
