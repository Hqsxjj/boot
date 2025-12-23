# services/subscription_service.py
# 订阅服务 - 使用数据库存储替代 JSON 文件

import uuid
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service to manage resource subscriptions and automated downloads."""

    def __init__(self, session_factory, pan_search_service, cloud115_service, cloud123_service):
        """
        Initialize subscription service with database backend.
        
        Args:
            session_factory: SQLAlchemy session factory for appdata.db
            pan_search_service: Pan search service instance
            cloud115_service: Cloud 115 service instance
            cloud123_service: Cloud 123 service instance
        """
        self.session_factory = session_factory
        self.pan_search_service = pan_search_service
        self.cloud115_service = cloud115_service
        self.cloud123_service = cloud123_service
        self._lock = threading.Lock()
        self.scheduler = BackgroundScheduler()
        self.scheduler_job_id = 'subscription_check_job'
        
        # 初始化数据库存储
        self._db_store = None
        if session_factory:
            from persistence.db_subscription_store import DbSubscriptionStore
            self._db_store = DbSubscriptionStore(session_factory)
        
        logger.info('SubscriptionService initialized with database backend')

    def start_scheduler(self):
        """Start the background scheduler."""
        if not self.scheduler.running:
            settings = self.get_settings()
            interval = settings.get('check_interval_minutes', 60)
            if interval < 5: interval = 5 # Minimum 5 mins
            
            logger.info(f"Starting subscription scheduler with interval {interval} minutes")
            self.scheduler.add_job(
                self.run_checks,
                IntervalTrigger(minutes=interval),
                id=self.scheduler_job_id,
                replace_existing=True
            )
            self.scheduler.start()

    def get_settings(self) -> Dict[str, Any]:
        """Get subscription settings from database."""
        if self._db_store:
            settings = self._db_store.get_settings()
            # Ensure default values
            if 'check_interval_minutes' not in settings:
                settings['check_interval_minutes'] = 60
            return settings
        return {'check_interval_minutes': 60}

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update subscription settings in database."""
        if self._db_store:
            self._db_store.update_settings(updates)
        
        settings = self.get_settings()
        
        # Reschedule if interval changed
        if 'check_interval_minutes' in updates:
            interval = int(updates['check_interval_minutes'])
            if interval < 5: interval = 5
            
            logger.info(f"Rescheduling subscription checks to every {interval} minutes")
            try:
                self.scheduler.reschedule_job(
                    self.scheduler_job_id,
                    trigger=IntervalTrigger(minutes=interval)
                )
            except Exception:
                self.scheduler.add_job(
                    self.run_checks,
                    IntervalTrigger(minutes=interval),
                    id=self.scheduler_job_id,
                    replace_existing=True
                )
                
        return settings

    def get_subscription_history(self, sub_id: str) -> List[Dict]:
        """Get history items for a specific subscription."""
        if self._db_store:
            return self._db_store.get_history(sub_id)
        return []

    def get_subscriptions(self) -> List[Dict]:
        """Get all subscriptions from database."""
        if self._db_store:
            return self._db_store.get_subscriptions()
        return []

    def add_subscription(self, keyword: str, cloud_type: str, filter_config: Dict) -> Dict:
        """Add a new subscription."""
        if self._db_store:
            return self._db_store.add_subscription(keyword, cloud_type, filter_config)
        
        # Fallback (should not happen)
        return {
            'id': str(uuid.uuid4()),
            'keyword': keyword,
            'cloud_type': cloud_type,
            'filter_config': filter_config,
            'enabled': True,
            'created_at': datetime.now().isoformat()
        }

    def delete_subscription(self, sub_id: str) -> bool:
        """Delete a subscription."""
        if self._db_store:
            return self._db_store.delete_subscription(sub_id)
        return False
    
    def update_subscription(self, sub_id: str, updates: Dict) -> Optional[Dict]:
        """Update a subscription."""
        if self._db_store:
            return self._db_store.update_subscription(sub_id, **updates)
        return None

    def check_subscription_availability(self, sub_id: str, date_str: str = None, ep_str: str = None) -> Dict[str, Any]:
        """
        Manually check availability for a subscription with optional filters.
        Returns search results (not downloaded).
        """
        subs = self.get_subscriptions()
        sub = next((s for s in subs if s['id'] == sub_id), None)
        if not sub:
            return {'success': False, 'error': 'Subscription not found'}

        keyword = sub['keyword']
        if date_str:
            keyword = f"{keyword} {date_str}"
        
        logger.info(f"Manual check for {sub['keyword']} (Search: {keyword})")
        
        result = self.pan_search_service.search(keyword, cloud_types=[sub.get('cloud_type', '115')])
        if not result.get('success'):
            return {'success': False, 'error': result.get('error')}
            
        items = result.get('data', [])
        
        # Filter logic
        matched_items = []
        filters = sub.get('filter_config', {})
        
        target_season = 0
        target_episode = 0
        if ep_str:
            target_season, target_episode = self._parse_episode_info(ep_str)

        for item in items:
            title = item.get('title', '')
            
            # If target episode specified, matching is stricter
            if target_season > 0 or target_episode > 0:
                s, e = self._parse_episode_info(title)
                if s != target_season or e != target_episode:
                    continue
            
            if self._matches_filters(title, filters):
                matched_items.append(item)
                
        return {'success': True, 'data': matched_items}

    def run_checks(self):
        """Run checks for all active subscriptions."""
        subs = self.get_subscriptions()
        
        logger.info(f"Checking {len(subs)} subscriptions...")
        
        for sub in subs:
            if not sub.get('enabled', True):
                continue
                
            try:
                self._check_single_subscription(sub)
            except Exception as e:
                logger.error(f"Error checking subscription {sub.get('keyword')}: {e}")
            
            # Update last check time
            if self._db_store:
                self._db_store.update_subscription(sub['id'], last_check=datetime.now())
            
        logger.info("Subscription checks completed.")

    def _check_single_subscription(self, sub: Dict):
        """Check a single subscription for new content."""
        keyword = sub.get('keyword', '')
        cloud_type = sub.get('cloud_type', '115')
        filters = sub.get('filter_config', {})
        
        # 1. Search
        result = self.pan_search_service.search(keyword, cloud_types=[cloud_type])
        if not result.get('success'):
            logger.warning(f"Search failed for {keyword}: {result.get('error')}")
            return
            
        items = result.get('data', [])
        logger.info(f"Subscription '{keyword}': Found {len(items)} items")
        
        # 2. Get existing history to avoid duplicates
        history = self.get_subscription_history(sub['id'])
        history_urls = {h.get('resource_url') for h in history if h.get('resource_url')}
        
        # 3. Filter & Match
        matched_items = []
        for item in items:
            title = item.get('title', '')
            url = item.get('url', '')
            
            # Skip if already downloaded
            if url in history_urls:
                continue
                
            if self._matches_filters(title, filters):
                matched_items.append(item)
        
        if not matched_items:
            logger.info(f"Subscription '{keyword}': No new items matched filters")
            return

        # 4. Download matched items
        success_count = 0
        
        for item in matched_items:
            try:
                success = self.trigger_download(item, cloud_type)
                status = 'saved' if success else 'failed'
                
                # Record in history
                if self._db_store:
                    self._db_store.add_history(
                        sub_id=sub['id'],
                        resource_title=item.get('title', ''),
                        resource_url=item.get('url', ''),
                        cloud_type=cloud_type,
                        status=status
                    )
                
                if success:
                    success_count += 1
                    logger.info(f"Successfully triggered download for {item.get('title')}")
            except Exception as e:
                logger.error(f"Download failed for item {item.get('title')}: {e}")
        
        logger.info(f"Subscription '{keyword}': Downloaded {success_count}/{len(matched_items)} items")

    def _parse_episode_info(self, title: str) -> tuple:
        """Parse season and episode from title. Returns (season, episode). Default (0, 0)."""
        if not title: return 0, 0
        
        # S01E01 or S1E1
        match = re.search(r'S(\d+)\s*E(\d+)', title, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))
            
        # E01 or EP01
        match = re.search(r'(?:E|EP)(\d+)', title, re.IGNORECASE)
        if match:
            return 1, int(match.group(1))

        # Chinese: 第xx集
        match = re.search(r'第(\d+)集', title)
        if match:
            return 1, int(match.group(1))
            
        return 0, 0

    def _matches_filters(self, title: str, filters: Dict) -> bool:
        """Check if title matches include/exclude rules."""
        # Include: Must match ALL
        includes = filters.get('include', [])
        if isinstance(includes, str): includes = [includes]
        for inc in includes:
            if not inc: continue
            try:
                if not re.search(inc, title, re.IGNORECASE):
                    return False
            except re.error:
                if inc.lower() not in title.lower():
                    return False
                
        # Exclude: Must match NONE
        excludes = filters.get('exclude', [])
        if isinstance(excludes, str): excludes = [excludes]
        for exc in excludes:
            if not exc: continue
            try:
                if re.search(exc, title, re.IGNORECASE):
                    return False
            except re.error:
                if exc.lower() in title.lower():
                    return False
                
        return True

    def trigger_download(self, item: Dict, cloud_type: str) -> bool:
        """Trigger offline download or save share."""
        url = item.get('url', '')
        password = item.get('password', '')
        if not url: return False
        
        try:
            if cloud_type == '115':
                share_code_match = re.search(r'115\.com/s/([a-z0-9]+)', url, re.IGNORECASE)
                if share_code_match:
                    share_code = share_code_match.group(1)
                    logger.info(f"Saving 115 share: {share_code}, pwd: {password}")
                    result = self.cloud115_service.save_share(share_code, password, save_cid='0')
                    return result.get('success', False)
                elif url.startswith('magnet:?'):
                    logger.info(f"Adding 115 offline task: {url[:30]}...")
                    result = self.cloud115_service.create_offline_task(url, save_cid='0')
                    return result.get('success', False)
                    
            elif cloud_type == '123':
                if url.startswith('magnet:?'):
                    logger.info(f"Adding 123 offline task: {url[:30]}...")
                    if hasattr(self.cloud123_service, 'create_offline_task'):
                        result = self.cloud123_service.create_offline_task(url, save_dir_id='/')
                        return result.get('success', False)
            
            return False
            
        except Exception as e:
            logger.error(f"Download trigger error: {e}")
            return False
