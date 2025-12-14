
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    import p115client
    print(f"p115client version: {getattr(p115client, '__version__', 'unknown')}")
    
    print("\n--- Testing login_qrcode_token (Default) ---")
    try:
        res = p115client.P115Client.login_qrcode_token()
        print(f"Result: {res}")
        
        if res.get('state') == 1:
            print("SUCCESS")
            uid = res['data'].get('uid')
            print(f"UID: {uid}")
        else:
            print("FAILURE")
    except Exception as e:
        print(f"Default call failed: {e}")

    print("\n--- Testing login_qrcode_token (With arguments) ---")
    # Try passing app argument if supported
    try:
        # Some versions might take different args
        res_ios = p115client.P115Client.login_qrcode_token(app='ios')
        print(f"Result (app='ios'): {res_ios}")
    except TypeError:
        print("p115client.login_qrcode_token does not accept 'app' argument")
    except Exception as e:
        print(f"Error with app arg: {e}")

except ImportError:
    print("p115client not installed")
except Exception as e:
    print(f"Unexpected error: {e}")
