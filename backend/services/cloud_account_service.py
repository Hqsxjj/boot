"""
Cloud Account Service for multi-account management.
Reference: EmbyNginxDK r115.py
"""
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from models.cloud_account import CloudAccount
from models.database import get_appdata_db_url, _create_engine, get_session_factory, AppDataBase

logger = logging.getLogger(__name__)


class CloudAccountService:
    """Service for managing multiple cloud accounts."""
    
    def __init__(self):
        self._engine = None
        self._session_factory = None
        self._init_db()
    
    def _init_db(self):
        """Initialize database connection."""
        try:
            db_url = get_appdata_db_url()
            self._engine = _create_engine(db_url)
            AppDataBase.metadata.create_all(self._engine, checkfirst=True)
            self._session_factory = get_session_factory(self._engine)
            logger.info("CloudAccountService database initialized")
        except Exception as e:
            logger.error(f"Failed to initialize CloudAccountService database: {e}")
    
    def _get_session(self):
        """Get a new database session."""
        if not self._session_factory:
            self._init_db()
        return self._session_factory()
    
    # ==================== CRUD Operations ====================
    
    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """Get all cloud accounts."""
        session = self._get_session()
        try:
            accounts = session.query(CloudAccount).order_by(CloudAccount.created_at.desc()).all()
            return [acc.to_dict() for acc in accounts]
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            return []
        finally:
            session.close()
    
    def get_accounts_by_type(self, account_type: str) -> List[Dict[str, Any]]:
        """Get accounts filtered by type (115, 115open, 123, 123open)."""
        session = self._get_session()
        try:
            accounts = session.query(CloudAccount).filter(
                CloudAccount.account_type == account_type
            ).order_by(CloudAccount.created_at.desc()).all()
            return [acc.to_dict() for acc in accounts]
        except Exception as e:
            logger.error(f"Failed to get accounts by type: {e}")
            return []
        finally:
            session.close()
    
    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        """Get a single account by ID."""
        session = self._get_session()
        try:
            account = session.query(CloudAccount).filter(CloudAccount.id == account_id).first()
            return account.to_full_dict() if account else None
        except Exception as e:
            logger.error(f"Failed to get account: {e}")
            return None
        finally:
            session.close()
    
    def get_active_account(self, account_type: str = None) -> Optional[Dict[str, Any]]:
        """Get the currently active account (optionally filtered by type)."""
        session = self._get_session()
        try:
            query = session.query(CloudAccount).filter(CloudAccount.is_active == True)
            if account_type:
                # 匹配同类型 (115/115open 都算 115 类)
                if account_type.startswith('115'):
                    query = query.filter(CloudAccount.account_type.like('115%'))
                elif account_type.startswith('123'):
                    query = query.filter(CloudAccount.account_type.like('123%'))
                else:
                    query = query.filter(CloudAccount.account_type == account_type)
            account = query.first()
            return account.to_full_dict() if account else None
        except Exception as e:
            logger.error(f"Failed to get active account: {e}")
            return None
        finally:
            session.close()
    
    def add_account(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new cloud account."""
        session = self._get_session()
        try:
            account = CloudAccount(
                name=data.get('name', '未命名账号'),
                account_type=data.get('account_type', '115'),
                cookie=data.get('cookie'),
                client=data.get('client', 'android'),
                access_token=data.get('access_token'),
                refresh_token=data.get('refresh_token'),
                expires_in=data.get('expires_in'),
                refresh_time=data.get('refresh_time'),
                app_id=data.get('app_id'),
                client_id=data.get('client_id'),
                client_secret=data.get('client_secret'),
                passport=data.get('passport'),
                password=data.get('password'),
                is_active=data.get('is_active', False),
            )
            session.add(account)
            session.commit()
            logger.info(f"Added new account: {account.name} ({account.account_type})")
            return {'success': True, 'data': account.to_dict()}
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to add account: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()
    
    def update_account(self, account_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing account."""
        session = self._get_session()
        try:
            account = session.query(CloudAccount).filter(CloudAccount.id == account_id).first()
            if not account:
                return {'success': False, 'error': '账号不存在'}
            
            # Update fields
            for key in ['name', 'account_type', 'cookie', 'client', 
                       'access_token', 'refresh_token', 'expires_in', 'refresh_time',
                       'app_id', 'client_id', 'client_secret', 'passport', 'password']:
                if key in data:
                    setattr(account, key, data[key])
            
            account.updated_at = datetime.utcnow()
            session.commit()
            logger.info(f"Updated account: {account.name}")
            return {'success': True, 'data': account.to_dict()}
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to update account: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()
    
    def delete_account(self, account_id: str) -> Dict[str, Any]:
        """Delete an account."""
        session = self._get_session()
        try:
            account = session.query(CloudAccount).filter(CloudAccount.id == account_id).first()
            if not account:
                return {'success': False, 'error': '账号不存在'}
            
            name = account.name
            session.delete(account)
            session.commit()
            logger.info(f"Deleted account: {name}")
            return {'success': True, 'message': f'已删除账号: {name}'}
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to delete account: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()
    
    def activate_account(self, account_id: str) -> Dict[str, Any]:
        """Set an account as active (deactivate others of same type)."""
        session = self._get_session()
        try:
            account = session.query(CloudAccount).filter(CloudAccount.id == account_id).first()
            if not account:
                return {'success': False, 'error': '账号不存在'}
            
            # Deactivate all accounts of the same type family
            if account.account_type.startswith('115'):
                session.query(CloudAccount).filter(
                    CloudAccount.account_type.like('115%')
                ).update({'is_active': False}, synchronize_session=False)
            elif account.account_type.startswith('123'):
                session.query(CloudAccount).filter(
                    CloudAccount.account_type.like('123%')
                ).update({'is_active': False}, synchronize_session=False)
            
            # Activate the selected account
            account.is_active = True
            session.commit()
            logger.info(f"Activated account: {account.name}")
            return {'success': True, 'data': account.to_dict()}
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to activate account: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()

    # ==================== Account Type Summary ====================
    
    def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary by type (like EmbyNginxDK's get_115_cookie_names)."""
        session = self._get_session()
        try:
            accounts = session.query(CloudAccount).all()
            
            result = {
                'all_names': [],
                '115': [],
                '115open': [],
                '123': [],
                '123open': [],
            }
            
            for acc in accounts:
                result['all_names'].append(acc.name)
                if acc.account_type in result:
                    result[acc.account_type].append({
                        'id': acc.id,
                        'name': acc.name,
                        'is_active': acc.is_active
                    })
            
            return {'success': True, 'data': result}
        except Exception as e:
            logger.error(f"Failed to get account summary: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            session.close()


# Singleton instance
_account_service = None

def get_account_service() -> CloudAccountService:
    """Get singleton CloudAccountService instance."""
    global _account_service
    if _account_service is None:
        _account_service = CloudAccountService()
    return _account_service
