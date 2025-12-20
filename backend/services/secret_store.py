import os
import logging
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from models.secret import Secret
from typing import Optional

logger = logging.getLogger(__name__)

# 不需要加密的凭证 key 列表（云盘凭证使用明文存储以确保可靠性）
UNENCRYPTED_KEYS = {
    'cloud115_cookies',
    'cloud115_qr_cookies',
    'cloud115_manual_cookies',
    'cloud115_openapp_cookies',
    'cloud115_session_metadata',
    'cloud123_credentials',
    'cloud123_cookies',
    'cloud123_session_metadata',
}


class SecretStore:
    """Service for storing and retrieving encrypted secrets."""
    
    def __init__(self, session_factory):
        """Initialize SecretStore with session factory."""
        self.session_factory = session_factory
        self._cipher = self._get_cipher()
        logger.info('SecretStore initialized')
    
    def _get_cipher(self) -> Fernet:
        """Get or create encryption cipher with persistent key."""
        encryption_key = os.environ.get('SECRETS_ENCRYPTION_KEY')
        
        if not encryption_key:
            # 尝试从文件加载持久化的密钥
            key_file = os.path.join(os.path.dirname(__file__), '..', 'data', '.encryption_key')
            key_file = os.path.abspath(key_file)
            
            # 确保 data 目录存在
            os.makedirs(os.path.dirname(key_file), exist_ok=True)
            
            if os.path.exists(key_file):
                # 从文件加载已有的密钥
                try:
                    with open(key_file, 'r') as f:
                        encryption_key = f.read().strip()
                    logger.info('Loaded encryption key from file')
                except Exception as e:
                    logger.warning(f'Failed to load encryption key from file: {e}')
            
            if not encryption_key:
                # 生成新密钥并保存到文件
                encryption_key = Fernet.generate_key().decode()
                try:
                    with open(key_file, 'w') as f:
                        f.write(encryption_key)
                    logger.info('Generated and saved new encryption key to file')
                except Exception as e:
                    logger.warning(f'Failed to save encryption key to file: {e}')
        
        # If it's a string, encode it
        if isinstance(encryption_key, str):
            # Try to verify it's valid base64
            try:
                encryption_key = encryption_key.encode()
                Fernet(encryption_key)
            except Exception:
                # Hash the provided key to create a valid Fernet key
                import base64
                import hashlib
                hashed = hashlib.sha256(encryption_key).digest()
                encryption_key = base64.urlsafe_b64encode(hashed)
        
        return Fernet(encryption_key)
    
    def _should_encrypt(self, key: str) -> bool:
        """Check if a key should be encrypted."""
        return key not in UNENCRYPTED_KEYS
    
    def set_secret(self, key: str, value: str) -> bool:
        """Store or update a secret (encrypted or plain based on key)."""
        try:
            # 云盘凭证不加密，其他凭证加密
            if self._should_encrypt(key):
                stored_value = self._cipher.encrypt(value.encode()).decode()
                is_encrypted = True
            else:
                stored_value = value
                is_encrypted = False
                logger.debug(f'Storing {key} without encryption (cloud credential)')
            
            session: Session = self.session_factory()
            
            # Check if secret exists
            existing = session.query(Secret).filter(Secret.key == key).first()
            
            if existing:
                existing.encrypted_value = stored_value
                logger.debug(f'Updated secret: {key}')
            else:
                secret = Secret(key=key, encrypted_value=stored_value)
                session.add(secret)
                logger.debug(f'Created secret: {key}')
            
            session.commit()
            session.close()
            logger.info(f'Secret saved successfully: {key} (encrypted={is_encrypted})')
            return True
        except Exception as e:
            logger.error(f'Failed to save secret {key}: {e}')
            return False
    
    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret (decrypt if needed based on key)."""
        try:
            session: Session = self.session_factory()
            secret = session.query(Secret).filter(Secret.key == key).first()
            session.close()
            
            if not secret:
                logger.debug(f'Secret not found: {key}')
                return None
            
            stored_value = secret.encrypted_value
            
            # 云盘凭证不解密，直接返回
            if not self._should_encrypt(key):
                logger.debug(f'Secret retrieved (plain): {key}')
                return stored_value
            
            # 尝试解密
            try:
                decrypted_value = self._cipher.decrypt(stored_value.encode()).decode()
                logger.debug(f'Secret retrieved (decrypted): {key}')
                return decrypted_value
            except Exception as decrypt_error:
                # 如果解密失败，可能是旧的明文数据，直接返回
                logger.warning(f'Decryption failed for {key}, returning as plain text: {decrypt_error}')
                return stored_value
        except Exception as e:
            logger.error(f'Failed to get secret {key}: {e}')
            return None
    
    def delete_secret(self, key: str) -> bool:
        """Delete a secret."""
        try:
            session: Session = self.session_factory()
            session.query(Secret).filter(Secret.key == key).delete()
            session.commit()
            session.close()
            return True
        except Exception as e:
            return False
    
    def secret_exists(self, key: str) -> bool:
        """Check if a secret exists."""
        try:
            session: Session = self.session_factory()
            exists = session.query(Secret).filter(Secret.key == key).first() is not None
            session.close()
            return exists
        except Exception as e:
            return False

