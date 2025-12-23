# persistence/db_source_store.py
# 数据库来源存储 - 替代 JSON 文件存储

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

logger = logging.getLogger(__name__)


class DbSourceStore:
    """
    数据库来源存储服务
    替代原来的 sources.json 和 crawled_data.json
    """
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
        logger.info('DbSourceStore initialized')
    
    def _get_session(self) -> Session:
        return self.session_factory()
    
    # ========== 来源管理 ==========
    
    def get_sources(self) -> List[Dict]:
        """获取所有来源"""
        session = self._get_session()
        try:
            from models.config import Source
            
            sources = session.query(Source).order_by(Source.created_at.desc()).all()
            return [s.to_dict() for s in sources]
        except Exception as e:
            logger.error(f'Failed to get sources: {e}')
            return []
        finally:
            session.close()
    
    def get_source(self, source_id: str) -> Optional[Dict]:
        """获取单个来源"""
        session = self._get_session()
        try:
            from models.config import Source
            
            source = session.query(Source).filter(Source.id == source_id).first()
            return source.to_dict() if source else None
        except Exception as e:
            logger.error(f'Failed to get source {source_id}: {e}')
            return None
        finally:
            session.close()
    
    def add_source(self, source_type: str, url: str, name: str = None) -> Dict:
        """添加来源"""
        session = self._get_session()
        try:
            from models.config import Source
            
            source = Source(
                id=str(uuid.uuid4()),
                type=source_type,
                url=url,
                name=name or url,
                enabled=True
            )
            session.add(source)
            session.commit()
            
            logger.info(f'Source added: {source_type} - {url}')
            return source.to_dict()
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to add source: {e}')
            raise
        finally:
            session.close()
    
    def update_source(self, source_id: str, **kwargs) -> Optional[Dict]:
        """更新来源"""
        session = self._get_session()
        try:
            from models.config import Source
            
            source = session.query(Source).filter(Source.id == source_id).first()
            if not source:
                return None
            
            for key, value in kwargs.items():
                if hasattr(source, key):
                    setattr(source, key, value)
            
            session.commit()
            return source.to_dict()
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to update source {source_id}: {e}')
            raise
        finally:
            session.close()
    
    def delete_source(self, source_id: str) -> bool:
        """删除来源及其抓取的资源"""
        session = self._get_session()
        try:
            from models.config import Source, CrawledResource
            
            # 同时删除抓取的资源
            session.query(CrawledResource).filter(
                CrawledResource.source_id == source_id
            ).delete()
            
            result = session.query(Source).filter(Source.id == source_id).delete()
            session.commit()
            
            return result > 0
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to delete source {source_id}: {e}')
            return False
        finally:
            session.close()
    
    def toggle_source(self, source_id: str, enabled: bool) -> bool:
        """切换来源启用状态"""
        result = self.update_source(source_id, enabled=enabled)
        return result is not None
    
    def update_last_crawl(self, source_id: str):
        """更新最后抓取时间"""
        self.update_source(source_id, last_crawl=datetime.now())
    
    # ========== 抓取资源管理 ==========
    
    def get_crawled_resources(self, source_id: str = None, limit: int = 500) -> List[Dict]:
        """获取抓取的资源"""
        session = self._get_session()
        try:
            from models.config import CrawledResource
            
            query = session.query(CrawledResource)
            if source_id:
                query = query.filter(CrawledResource.source_id == source_id)
            
            resources = query.order_by(CrawledResource.created_at.desc()).limit(limit).all()
            return [r.to_dict() for r in resources]
        except Exception as e:
            logger.error(f'Failed to get crawled resources: {e}')
            return []
        finally:
            session.close()
    
    def add_crawled_resource(self, source_id: str, title: str, url: str = None,
                            share_code: str = None, access_code: str = None,
                            cloud_type: str = None, file_size: str = None,
                            extra_data: Dict = None) -> Dict:
        """添加抓取的资源"""
        session = self._get_session()
        try:
            from models.config import CrawledResource
            
            resource = CrawledResource(
                source_id=source_id,
                title=title,
                url=url,
                share_code=share_code,
                access_code=access_code,
                cloud_type=cloud_type,
                file_size=file_size,
                extra_data=json.dumps(extra_data or {}, ensure_ascii=False)
            )
            session.add(resource)
            session.commit()
            
            return resource.to_dict()
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to add crawled resource: {e}')
            raise
        finally:
            session.close()
    
    def add_crawled_resources_batch(self, source_id: str, resources: List[Dict]) -> int:
        """批量添加抓取的资源"""
        session = self._get_session()
        try:
            from models.config import CrawledResource
            
            count = 0
            for res in resources:
                resource = CrawledResource(
                    source_id=source_id,
                    title=res.get('title', ''),
                    url=res.get('url'),
                    share_code=res.get('share_code'),
                    access_code=res.get('access_code'),
                    cloud_type=res.get('cloud_type'),
                    file_size=res.get('file_size'),
                    extra_data=json.dumps(res.get('extra_data', {}), ensure_ascii=False)
                )
                session.add(resource)
                count += 1
            
            session.commit()
            logger.info(f'Batch added {count} crawled resources for source {source_id}')
            return count
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to batch add crawled resources: {e}')
            return 0
        finally:
            session.close()
    
    def search_crawled(self, query: str, limit: int = 50) -> List[Dict]:
        """搜索抓取的资源"""
        session = self._get_session()
        try:
            from models.config import CrawledResource
            
            # 模糊匹配标题
            search_pattern = f'%{query}%'
            resources = session.query(CrawledResource).filter(
                CrawledResource.title.ilike(search_pattern)
            ).order_by(CrawledResource.created_at.desc()).limit(limit).all()
            
            return [r.to_dict() for r in resources]
        except Exception as e:
            logger.error(f'Failed to search crawled resources: {e}')
            return []
        finally:
            session.close()
    
    def clear_crawled_resources(self, source_id: str = None) -> int:
        """清除抓取的资源"""
        session = self._get_session()
        try:
            from models.config import CrawledResource
            
            query = session.query(CrawledResource)
            if source_id:
                query = query.filter(CrawledResource.source_id == source_id)
            
            count = query.delete()
            session.commit()
            return count
        except Exception as e:
            session.rollback()
            logger.error(f'Failed to clear crawled resources: {e}')
            return 0
        finally:
            session.close()
    
    def get_crawl_stats(self) -> Dict[str, Any]:
        """获取抓取统计"""
        session = self._get_session()
        try:
            from models.config import Source, CrawledResource
            from sqlalchemy import func
            
            source_count = session.query(func.count(Source.id)).scalar() or 0
            resource_count = session.query(func.count(CrawledResource.id)).scalar() or 0
            
            # 按来源分组统计
            source_stats = session.query(
                CrawledResource.source_id,
                func.count(CrawledResource.id)
            ).group_by(CrawledResource.source_id).all()
            
            return {
                'source_count': source_count,
                'resource_count': resource_count,
                'source_stats': {s[0]: s[1] for s in source_stats}
            }
        except Exception as e:
            logger.error(f'Failed to get crawl stats: {e}')
            return {'source_count': 0, 'resource_count': 0}
        finally:
            session.close()


# 全局实例
_db_source_store: Optional[DbSourceStore] = None


def get_db_source_store() -> Optional[DbSourceStore]:
    return _db_source_store


def init_db_source_store(session_factory) -> DbSourceStore:
    global _db_source_store
    _db_source_store = DbSourceStore(session_factory)
    return _db_source_store
