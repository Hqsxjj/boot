import os
import logging
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session
from models.secret import Secret
from typing import Optional

logger = logging.getLogger(__name__)


class SecretStore:
    """Service for storing and retrieving encrypted secrets."""
    
    def __init__(self, session_factory):
        """Initialize SecretStore with session factory."""
        self.session_factory = session_factory
        self._cipher = self._get_cipher()
        logger.info('SecretStore initialized')
    
    def _get_cipher(self) -> Fernet:
        """Get or create encryption cipher."""
        encryption_key = os.environ.get('SECRETS_ENCRYPTION_KEY')
        
        if not encryption_key:
            # Generate a default key for development (should be overridden in production)
            encryption_key = Fernet.generate_key().decode()
        
        # If it's a string, encode it
        if isinstance(encryption_key, str):
            # If it's not already a valid base64 key, generate one from the string
            try:
                encryption_key = encryption_key.encode()
                # Try to verify it's valid base64
                Fernet(encryption_key)
            except Exception:
                # Hash the provided key to create a valid Fernet key
                import base64
                import hashlib
                hashed = hashlib.sha256(encryption_key).digest()
                encryption_key = base64.urlsafe_b64encode(hashed)
        
        return Fernet(encryption_key)
    
    def set_secret(self, key: str, value: str) -> bool:
        """Store or update an encrypted secret."""
        try:
            encrypted_value = self._cipher.encrypt(value.encode()).decode()
            
            session: Session = self.session_factory()
            
            # Check if secret exists
            existing = session.query(Secret).filter(Secret.key == key).first()
            
            if existing:
                existing.encrypted_value = encrypted_value
                logger.debug(f'Updated secret: {key}')
            else:
                secret = Secret(key=key, encrypted_value=encrypted_value)
                session.add(secret)
                logger.debug(f'Created secret: {key}')
            
            session.commit()
            session.close()
            logger.info(f'Secret saved successfully: {key}')
            return True
        except Exception as e:
            logger.error(f'Failed to save secret {key}: {e}')
            return False
    
    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve and decrypt a secret."""
        try:
            session: Session = self.session_factory()
            secret = session.query(Secret).filter(Secret.key == key).first()
            session.close()
            
            if not secret:
                logger.debug(f'Secret not found: {key}')
                return None
            
            decrypted_value = self._cipher.decrypt(secret.encrypted_value.encode()).decode()
            logger.debug(f'Secret retrieved: {key}')
            return decrypted_value
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
