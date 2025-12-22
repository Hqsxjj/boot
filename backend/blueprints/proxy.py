from flask import Blueprint, request, jsonify
import requests
import time
import logging

proxy_bp = Blueprint('proxy', __name__, url_prefix='/api/proxy')
logger = logging.getLogger(__name__)

@proxy_bp.route('/test', methods=['POST'])
def test_proxy():
    """
    Test proxy connection and measure latency.
    Expects JSON payload with: type, host, port, username(optional), password(optional)
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Missing config data'}), 400

    proxy_type = data.get('type', 'http')
    host = data.get('host')
    port = data.get('port')
    username = data.get('username')
    password = data.get('password')

    if not host or not port:
         return jsonify({'success': False, 'error': 'Host and port are required'}), 400

    # Construct proxy string
    proxy_url = ""
    if proxy_type == 'socks5':
        if username and password:
            proxy_url = f"socks5://{username}:{password}@{host}:{port}"
        else:
            proxy_url = f"socks5://{host}:{port}"
    else: # http/https
        if username and password:
            proxy_url = f"http://{username}:{password}@{host}:{port}"
        else:
            proxy_url = f"http://{host}:{port}"

    proxies = {
        "http": proxy_url,
        "https": proxy_url,
    }

    try:
        start_time = time.time()
        # Use a reliable target to test connectivity (e.g., Google or Cloudflare)
        # We assume if the user needs a proxy, they likely want to access blocked sites.
        # Github is a good middle ground, or 1.1.1.1
        resp = requests.get("https://www.google.com/generate_204", proxies=proxies, timeout=10)
        end_time = time.time()
        
        latency_ms = int((end_time - start_time) * 1000)

        if resp.status_code == 204 or resp.status_code == 200:
             return jsonify({
                'success': True, 
                'data': {
                    'latency': latency_ms,
                    'message': f'Connection successful ({latency_ms}ms)'
                }
            })
        else:
             return jsonify({
                'success': False, 
                'data': {
                    'latency': latency_ms,
                    'error': f'HTTP {resp.status_code}'
                }
            }), 200 # Return 200 so frontend can handle the logic

    except requests.exceptions.Timeout:
        return jsonify({'success': False, 'error': 'Connection timed out'}), 200
    except requests.exceptions.ProxyError:
        return jsonify({'success': False, 'error': 'Proxy handshake failed'}), 200
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'error': str(e)}), 200
    except Exception as e:
        logger.error(f"Proxy test error: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
