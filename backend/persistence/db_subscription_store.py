# persistence/db_subscription_store.py
# 数据库订阅存储 - 替代 JSON 文件存储

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class DbSubscriptionStore:
    """
    数据库订阅存储服务
    替代原来的 subscriptions.json, subscription_history.json, subscription_settings.json
    """
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
        logger.info('DbSubscriptionStore initialized')
    
    def _get_session(self) -> Session:
        return self.session_factory()
    
    # ========== 订阅管理 ==========
    
    def get_subscriptions(self) -> List[Dict]:
        """获取所有订阅"""
        session = self._get_session()
        try:
            from models.config import Subscription
            
            subs = session.query(Subscription).order_by(Subscription.created_at.desc()).all()
            return [s.to_dict() for s in subs]
        except Exception as e:
            logger.error(f'Failed to get subscriptions: {e}')
            return []
        finally:
            session.close()
    
    def get_subscription(self, sub_id: str) -> Optional[Dict]:
        """获取单个订阅"""
        session = self._get_session()
        try:
            from models.config import Subscription
            
            sub = session.query(Subscription).filter(Subscription.id == sub_id).first()
            return sub.to_dict() if sub else None
        except Exception as e:
            logger.error(f'Failed to get subscription {sub_id}: {e}')
            return None
        finally:
            session.close()
    
    def add_subscription(self, keyword: str, cloud_type: str = '115', 
                        filter_config: Dict = None) -> Dict:
        """添加订阅"""
        session = self._get_session()
        try:
            from models.config import Subscription
            
            sub = Subscription(
                id=str(uuid.uuid4()),
                keyword=keyword,
                cloud_type=cloud_type,
                filter_config=json.dumps(filter_config or {}, ensure_ascii=False),
                enabled=True
            )
            session.add(sub)
            session.commit()
            
            logger.info(f'Subscription added: {keyword}')
            return sub.to_dict()
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to add subscription: {e}')
            raise
        finally:
            session.close()
    
    def update_subscription(self, sub_id: str, **kwargs) -> Optional[Dict]:
        """更新订阅"""
        session = self._get_session()
        try:
            from models.config import Subscription
            
            sub = session.query(Subscription).filter(Subscription.id == sub_id).first()
            if not sub:
                return None
            
            for key, value in kwargs.items():
                if key == 'filter_config' and isinstance(value, dict):
                    setattr(sub, key, json.dumps(value, ensure_ascii=False))
                elif hasattr(sub, key):
                    setattr(sub, key, value)
            
            session.commit()
            return sub.to_dict()
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to update subscription {sub_id}: {e}')
            raise
        finally:
            session.close()
    
    def delete_subscription(self, sub_id: str) -> bool:
        """删除订阅"""
        session = self._get_session()
        try:
            from models.config import Subscription, SubscriptionHistory
            
            # 同时删除历史记录
            session.query(SubscriptionHistory).filter(
                SubscriptionHistory.subscription_id == sub_id
            ).delete()
            
            result = session.query(Subscription).filter(Subscription.id == sub_id).delete()
            session.commit()
            
            return result > 0
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to delete subscription {sub_id}: {e}')
            return False
        finally:
            session.close()
    
    def toggle_subscription(self, sub_id: str, enabled: bool) -> bool:
        """切换订阅启用状态"""
        result = self.update_subscription(sub_id, enabled=enabled)
        return result is not None
    
    # ========== 订阅历史 ==========
    
    def get_history(self, sub_id: str = None, limit: int = 100) -> List[Dict]:
        """获取订阅历史"""
        session = self._get_session()
        try:
            from models.config import SubscriptionHistory
            
            query = session.query(SubscriptionHistory)
            if sub_id:
                query = query.filter(SubscriptionHistory.subscription_id == sub_id)
            
            history = query.order_by(SubscriptionHistory.created_at.desc()).limit(limit).all()
            return [h.to_dict() for h in history]
        except Exception as e:
            logger.error(f'Failed to get history: {e}')
            return []
        finally:
            session.close()
    
    def add_history(self, sub_id: str, resource_title: str, resource_url: str = None,
                   cloud_type: str = None, status: str = 'found', details: Dict = None):
        """添加历史记录"""
        session = self._get_session()
        try:
            from models.config import SubscriptionHistory
            
            history = SubscriptionHistory(
                subscription_id=sub_id,
                resource_title=resource_title,
                resource_url=resource_url,
                cloud_type=cloud_type,
                status=status,
                details=json.dumps(details or {}, ensure_ascii=False)
            )
            session.add(history)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to add history: {e}')
        finally:
            session.close()
    
    def clear_history(self, sub_id: str = None) -> int:
        """清除历史记录"""
        session = self._get_session()
        try:
            from models.config import SubscriptionHistory
            
            query = session.query(SubscriptionHistory)
            if sub_id:
                query = query.filter(SubscriptionHistory.subscription_id == sub_id)
            
            count = query.delete()
            session.commit()
            return count
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to clear history: {e}')
            return 0
        finally:
            session.close()
    
    # ========== 订阅设置 ==========
    
    def get_settings(self) -> Dict[str, Any]:
        """获取订阅设置"""
        session = self._get_session()
        try:
            from models.config import SubscriptionSettings
            
            settings = session.query(SubscriptionSettings).all()
            return {s.key: json.loads(s.value) if s.value else None for s in settings}
        except Exception as e:
            logger.error(f'Failed to get settings: {e}')
            return {}
        finally:
            session.close()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取单个设置"""
        session = self._get_session()
        try:
            from models.config import SubscriptionSettings
            
            setting = session.query(SubscriptionSettings).filter(
                SubscriptionSettings.key == key
            ).first()
            
            if setting and setting.value:
                try:
                    return json.loads(setting.value)
                except:
                    return setting.value
            return default
        except Exception as e:
            logger.error(f'Failed to get setting {key}: {e}')
            return default
        finally:
            session.close()
    
    def set_setting(self, key: str, value: Any):
        """设置单个配置"""
        session = self._get_session()
        try:
            from models.config import SubscriptionSettings
            
            setting = session.query(SubscriptionSettings).filter(
                SubscriptionSettings.key == key
            ).first()
            
            if setting:
                setting.value = json.dumps(value, ensure_ascii=False)
            else:
                setting = SubscriptionSettings(
                    key=key,
                    value=json.dumps(value, ensure_ascii=False)
                )
                session.add(setting)
            
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to set setting {key}: {e}')
            raise
        finally:
            session.close()
    
    def update_settings(self, settings: Dict[str, Any]):
        """批量更新设置"""
        for key, value in settings.items():
            self.set_setting(key, value)


# 全局实例
_db_subscription_store: Optional[DbSubscriptionStore] = None


def get_db_subscription_store() -> Optional[DbSubscriptionStore]:
    return _db_subscription_store


def init_db_subscription_store(session_factory) -> DbSubscriptionStore:
    global _db_subscription_store
    _db_subscription_store = DbSubscriptionStore(session_factory)
    return _db_subscription_store
