"""
Cloud 115 Token Service

Manages 115 cloud tokens in the database.
Supports both Cookie and Open Platform (OAuth) authentication.
"""
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class Cloud115TokenService:
    """Service for managing 115 tokens in database."""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
    
    def get_active_token(self, token_type: str = None) -> Optional[Dict[str, Any]]:
        """
        Get the currently active token.
        
        Args:
            token_type: Filter by 'cookie' or 'open', or None for any
            
        Returns:
            Token dict or None
        """
        from models.app_data import Cloud115Token
        
        session: Session = self.session_factory()
        try:
            query = session.query(Cloud115Token).filter(Cloud115Token.is_active == True)
            if token_type:
                query = query.filter(Cloud115Token.token_type == token_type)
            token = query.first()
            return token.to_dict() if token else None
        except Exception as e:
            logger.error(f"[115 DB] 获取活动 Token 失败: {e}")
            return None
        finally:
            session.close()
    
    def get_active_cookie_token(self) -> Optional[Dict[str, Any]]:
        """Get active cookie token with full cookie string."""
        from models.app_data import Cloud115Token
        
        session: Session = self.session_factory()
        try:
            token = session.query(Cloud115Token).filter(
                Cloud115Token.is_active == True,
                Cloud115Token.token_type == 'cookie'
            ).first()
            if token:
                result = token.to_dict()
                result['cookie'] = token.cookie
                return result
            return None
        except Exception as e:
            logger.error(f"[115 DB] 获取 Cookie Token 失败: {e}")
            return None
        finally:
            session.close()
    
    def get_active_open_token(self) -> Optional[Dict[str, Any]]:
        """Get active open platform token with access/refresh tokens."""
        from models.app_data import Cloud115Token
        
        session: Session = self.session_factory()
        try:
            token = session.query(Cloud115Token).filter(
                Cloud115Token.is_active == True,
                Cloud115Token.token_type == 'open'
            ).first()
            if token:
                result = token.to_dict()
                result['accessToken'] = token.access_token
                result['refreshToken'] = token.refresh_token
                result['appId'] = token.app_id
                return result
            return None
        except Exception as e:
            logger.error(f"[115 DB] 获取 Open Token 失败: {e}")
            return None
        finally:
            session.close()
    
    def save_cookie_token(self, name: str, cookie: str, client: str = None,
                          user_id: str = None, user_name: str = None) -> bool:
        """Save or update a cookie token."""
        from models.app_data import Cloud115Token
        
        session: Session = self.session_factory()
        try:
            # 先将其他同类型的设为非活动
            session.query(Cloud115Token).filter(
                Cloud115Token.token_type == 'cookie'
            ).update({'is_active': False})
            
            # 查找或创建
            token = session.query(Cloud115Token).filter(
                Cloud115Token.name == name
            ).first()
            
            if token:
                token.cookie = cookie
                token.client = client
                token.user_id = user_id
                token.user_name = user_name
                token.is_active = True
                token.updated_at = datetime.now()
            else:
                token = Cloud115Token(
                    name=name,
                    token_type='cookie',
                    cookie=cookie,
                    client=client,
                    user_id=user_id,
                    user_name=user_name,
                    is_active=True
                )
                session.add(token)
            
            session.commit()
            logger.info(f"[115 DB] 保存 Cookie Token: {name}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"[115 DB] 保存 Cookie Token 失败: {e}")
            return False
        finally:
            session.close()
    
    def save_open_token(self, name: str, access_token: str, refresh_token: str,
                        expires_at: datetime, app_id: str = None,
                        user_id: str = None, user_name: str = None) -> bool:
        """Save or update an open platform token."""
        from models.app_data import Cloud115Token
        
        session: Session = self.session_factory()
        try:
            # 先将其他同类型的设为非活动
            session.query(Cloud115Token).filter(
                Cloud115Token.token_type == 'open'
            ).update({'is_active': False})
            
            # 查找或创建
            token = session.query(Cloud115Token).filter(
                Cloud115Token.name == name
            ).first()
            
            if token:
                token.access_token = access_token
                token.refresh_token = refresh_token
                token.expires_at = expires_at
                token.app_id = app_id
                token.user_id = user_id
                token.user_name = user_name
                token.is_active = True
                token.updated_at = datetime.now()
            else:
                token = Cloud115Token(
                    name=name,
                    token_type='open',
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    app_id=app_id,
                    user_id=user_id,
                    user_name=user_name,
                    is_active=True
                )
                session.add(token)
            
            session.commit()
            logger.info(f"[115 DB] 保存 Open Token: {name}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"[115 DB] 保存 Open Token 失败: {e}")
            return False
        finally:
            session.close()
    
    def list_tokens(self) -> List[Dict[str, Any]]:
        """List all tokens (without sensitive data)."""
        from models.app_data import Cloud115Token
        
        session: Session = self.session_factory()
        try:
            tokens = session.query(Cloud115Token).order_by(
                Cloud115Token.is_active.desc(),
                Cloud115Token.updated_at.desc()
            ).all()
            return [t.to_dict() for t in tokens]
        except Exception as e:
            logger.error(f"[115 DB] 列出 Token 失败: {e}")
            return []
        finally:
            session.close()
    
    def delete_token(self, token_id: int) -> bool:
        """Delete a token by ID."""
        from models.app_data import Cloud115Token
        
        session: Session = self.session_factory()
        try:
            token = session.query(Cloud115Token).filter(Cloud115Token.id == token_id).first()
            if token:
                session.delete(token)
                session.commit()
                logger.info(f"[115 DB] 删除 Token: {token.name}")
                return True
            return False
        except Exception as e:
            session.rollback()
            logger.error(f"[115 DB] 删除 Token 失败: {e}")
            return False
        finally:
            session.close()
    
    def set_active(self, token_id: int) -> bool:
        """Set a token as active (deactivates others of same type)."""
        from models.app_data import Cloud115Token
        
        session: Session = self.session_factory()
        try:
            token = session.query(Cloud115Token).filter(Cloud115Token.id == token_id).first()
            if not token:
                return False
            
            # 先将同类型的其他设为非活动
            session.query(Cloud115Token).filter(
                Cloud115Token.token_type == token.token_type,
                Cloud115Token.id != token_id
            ).update({'is_active': False})
            
            token.is_active = True
            token.updated_at = datetime.now()
            session.commit()
            logger.info(f"[115 DB] 设置活动 Token: {token.name}")
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"[115 DB] 设置活动 Token 失败: {e}")
            return False
        finally:
            session.close()


# Global instance
_token_service: Optional[Cloud115TokenService] = None


def get_token_service(session_factory=None) -> Optional[Cloud115TokenService]:
    """Get global token service instance."""
    global _token_service
    if _token_service is None and session_factory:
        _token_service = Cloud115TokenService(session_factory)
    return _token_service


def init_token_service(session_factory) -> Cloud115TokenService:
    """Initialize global token service."""
    global _token_service
    _token_service = Cloud115TokenService(session_factory)
    return _token_service
