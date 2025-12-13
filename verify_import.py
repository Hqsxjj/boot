
try:
    from backend.cloud123 import Cloud123Client
    print("SUCCESS: Cloud123Client imported")
    client = Cloud123Client()
    print("SUCCESS: Cloud123Client instantiated")
except ImportError as e:
    print(f"FAILED: {e}")
except Exception as e:
    print(f"FAILED: {e}")
