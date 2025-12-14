import logging
import json
import requests
from typing import Dict, Any, Optional
from services.secret_store import SecretStore
from services.config_loader import get_recognition_rules, get_category_config

logger = logging.getLogger(__name__)

class LLMService:
    """Service for intelligent media parsing using LLM."""
    
    def __init__(self, secret_store: SecretStore):
        self.secret_store = secret_store
        
    def _get_api_config(self) -> Dict[str, str]:
        """Get LLM API configuration from secrets."""
        # Default to OpenAI-compatible interface/format
        api_key = self.secret_store.get_secret('llm_api_key')
        base_url = self.secret_store.get_secret('llm_base_url') or 'https://api.openai.com/v1'
        model = self.secret_store.get_secret('llm_model') or 'gpt-3.5-turbo'
        
        return {
            'api_key': api_key,
            'base_url': base_url.rstrip('/'),
            'model': model
        }

    def parse_filename(self, filename: str) -> Dict[str, Any]:
        """
        Parse filename using LLM to extract media info.
        
        Args:
            filename: The filename to parse
            
        Returns:
            Dict containing parsed info (title, year, type, etc.)
        """
        config = self._get_api_config()
        if not config['api_key']:
            logger.warning("LLM API key not configured, skipping intelligent parsing")
            return {}

        rules = get_recognition_rules()
        categories = get_category_config()
        
        # Build prompt context
        prompt = f"""
        You are a smart media filename parser. Your task is to extract metadata from the given filename and classify it according to the provided rules.
        
        Filename: "{filename}"
        
        Please extract:
        1. Title (Clean title without year, resolution, etc.)
        2. Year (YYYY)
        3. Type (movie or tv)
        4. Season (Sxx, integer) - if applicable
        5. Episode (Exx, integer) - if applicable
        6. TMDB ID - if present in name like {{tmdb-123}}
        7. Category - Choose the best matching category from the list below based on the rules.
        
        Category Configuration:
        {json.dumps(categories.get('advanced_rules', {}), ensure_ascii=False, indent=2)}
        
        If unsure about category, default to '其他电影' (movie) or '其他剧集' (tv).
        
        Respond ONLY with a valid JSON object in the following format:
        {{
            "title": "string",
            "year": "string or null",
            "type": "movie" or "tv",
            "season": int or null,
            "episode": int or null,
            "tmdb_id": int or null,
            "category": "string"
        }}
        """

        try:
            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": config['model'],
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that outputs only JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"}
            }
            
            response = requests.post(
                f"{config['base_url']}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            parsed_data = json.loads(content)
            
            logger.info(f"LLM successfully parsed '{filename}': {parsed_data}")
            return parsed_data
            
        except Exception as e:
            logger.error(f"LLM parsing failed for '{filename}': {e}")
            return {}
