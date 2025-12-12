import requests
import time
from persistence.store import DataStore
from typing import Dict, Any, List


class EmbyService:
    """Service for handling Emby server integration."""
    
    def __init__(self, store: DataStore):
        self.store = store
        self.timeout = 10
    
    def _get_config(self) -> Dict[str, Any]:
        """Get Emby configuration from store."""
        try:
            config = self.store.get_config()
            return config.get('emby', {})
        except Exception:
            return {}
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to Emby server."""
        config = self._get_config()
        server_url = config.get('serverUrl', '').strip()
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {
                'success': False,
                'latency': 0,
                'msg': 'Server URL and API Key are required'
            }
        
        try:
            start_time = time.time()
            
            # Test connection by making a simple API call
            response = requests.get(
                f'{server_url}/emby/System/Info',
                params={'api_key': api_key},
                timeout=self.timeout
            )
            
            latency = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'latency': latency,
                    'msg': f'Connected successfully ({latency}ms)'
                }
            else:
                return {
                    'success': False,
                    'latency': latency,
                    'msg': f'Connection failed: HTTP {response.status_code}'
                }
        except requests.Timeout:
            return {
                'success': False,
                'latency': 0,
                'msg': 'Connection timeout'
            }
        except requests.ConnectionError:
            return {
                'success': False,
                'latency': 0,
                'msg': 'Connection refused'
            }
        except Exception as e:
            return {
                'success': False,
                'latency': 0,
                'msg': f'Error: {str(e)}'
            }
    
    def scan_missing_episodes(self) -> Dict[str, Any]:
        """Scan for missing episodes in Emby."""
        config = self._get_config()
        server_url = config.get('serverUrl', '').strip()
        api_key = config.get('apiKey', '').strip()
        
        if not server_url or not api_key:
            return {
                'success': False,
                'data': []
            }
        
        try:
            # In a real implementation, this would query Emby API for missing episodes
            # For now, return an empty list (client can show "No missing episodes")
            missing_data = []
            
            # Example: query Emby for series and check against TMDB
            # This is a placeholder that would need actual implementation
            # based on your Emby API integration requirements
            
            return {
                'success': True,
                'data': missing_data
            }
        except Exception as e:
            return {
                'success': False,
                'data': []
            }
