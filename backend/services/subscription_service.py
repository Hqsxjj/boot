
import json
import os
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

    def __init__(self, data_dir: str, pan_search_service, cloud115_service, cloud123_service):
        self.data_dir = data_dir
        self.file_path = os.path.join(data_dir, 'subscriptions.json')
        self.history_path = os.path.join(data_dir, 'subscription_history.json')
        self.pan_search_service = pan_search_service
        self.cloud115_service = cloud115_service
        self.cloud123_service = cloud123_service
        self.cloud123_service = cloud123_service
        self._lock = threading.Lock()
        self.settings_path = os.path.join(data_dir, 'subscription_settings.json')
        self.scheduler = BackgroundScheduler()
        self.scheduler_job_id = 'subscription_check_job'
        self._ensure_files()


    def _ensure_files(self):
        """Ensure storage files exist."""
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump([], f)
        
        if not os.path.exists(self.history_path):
            with open(self.history_path, 'w') as f:
                json.dump({}, f)

        if not os.path.exists(self.settings_path):
            with open(self.settings_path, 'w') as f:
                json.dump({'check_interval_minutes': 60}, f)


    def _load_subscriptions(self) -> List[Dict]:
        with self._lock:
            with open(self.file_path, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return []

    def _save_subscriptions(self, subs: List[Dict]):
        with self._lock:
            with open(self.file_path, 'w') as f:
                json.dump(subs, f, indent=2)

    def _load_history(self) -> Dict[str, Any]:
        with self._lock:
            with open(self.history_path, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {}

    def _save_history(self, history: Dict[str, Any]):
        with self._lock:
            with open(self.history_path, 'w') as f:
                json.dump(history, f, indent=2)

    def _load_settings(self) -> Dict[str, Any]:
        with self._lock:
            with open(self.settings_path, 'r') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return {'check_interval_minutes': 60}

    def _save_settings(self, settings: Dict[str, Any]):
        with self._lock:
            with open(self.settings_path, 'w') as f:
                json.dump(settings, f, indent=2)

    def start_scheduler(self):
        """Start the background scheduler."""
        if not self.scheduler.running:
            settings = self._load_settings()
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
        return self._load_settings()

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        settings = self._load_settings()
        settings.update(updates)
        self._save_settings(settings)
        
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
                # Job might not exist if not started
                self.scheduler.add_job(
                    self.run_checks,
                    IntervalTrigger(minutes=interval),
                    id=self.scheduler_job_id,
                    replace_existing=True
                )
                
        return settings

    def get_subscription_history(self, sub_id: str) -> List[Dict]:
        """Get history items for a specific subscription."""
        history = self._load_history()
        # History is keyed by URL. We need to filter by sub_id.
        # Structure: { url: { sub_id, title, downloaded_at, ... } }
        items = []
        for url, data in history.items():
            if data.get('sub_id') == sub_id:
                items.append({
                    'url': url,
                    **data
                })
        # Sort by date desc
        items.sort(key=lambda x: x.get('downloaded_at', ''), reverse=True)
        return items

    def check_subscription_availability(self, sub_id: str, date_str: str = None, ep_str: str = None) -> Dict[str, Any]:
        """
        Manually check availability for a subscription with optional filters.
        Returns search results (not downloaded).
        """
        subs = self._load_subscriptions()
        sub = next((s for s in subs if s['id'] == sub_id), None)
        if not sub:
            return {'success': False, 'error': 'Subscription not found'}

        keyword = sub['keyword']
        if date_str:
            keyword = f"{keyword} {date_str}"
        
        logger.info(f"Manual check for {sub['keyword']} (Search: {keyword})")
        
        result = self.pan_search_service.search(keyword, cloud_types=[sub['cloud_type']])
        if not result.get('success'):
            return {'success': False, 'error': result.get('error')}
            
        items = result.get('data', [])
        
        # Filter logic (similar to auto-check but stricter if ep_str provided)
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


    def get_subscriptions(self) -> List[Dict]:
        return self._load_subscriptions()

    def add_subscription(self, keyword: str, cloud_type: str, filter_config: Dict) -> Dict:
        """
        Add a new subscription.
        filter_config example: { 'include': ['4K', 'HDR'], 'exclude': ['CAM', 'H265'] }
        """
        sub = {
            'id': str(uuid.uuid4()),
            'keyword': keyword,
            'cloud_type': cloud_type,
            'filter_config': filter_config,
            'status': 'active',
            'created_at': datetime.now().isoformat(),
            'last_check': None,
            'last_message': 'Created',
            'current_season': 0,
            'current_episode': 0
        }
        subs = self._load_subscriptions()
        subs.append(sub)
        self._save_subscriptions(subs)
        return sub

    def delete_subscription(self, sub_id: str) -> bool:
        subs = self._load_subscriptions()
        new_subs = [s for s in subs if s['id'] != sub_id]
        if len(new_subs) != len(subs):
            self._save_subscriptions(new_subs)
            return True
        return False
    
    def update_subscription(self, sub_id: str, updates: Dict) -> Optional[Dict]:
        subs = self._load_subscriptions()
        for s in subs:
            if s['id'] == sub_id:
                s.update(updates)
                self._save_subscriptions(subs)
                return s
        return None

    def run_checks(self):
        """Run checks for all active subscriptions."""
        subs = self._load_subscriptions()
        history = self._load_history()
        
        logger.info(f"Checking {len(subs)} subscriptions...")
        
        for sub in subs:
            if sub.get('status') != 'active':
                continue
                
            try:
                self._check_single_subscription(sub, history)
            except Exception as e:
                logger.error(f"Error checking subscription {sub['keyword']}: {e}")
                sub['last_message'] = f"Error: {str(e)}"
            
            sub['last_check'] = datetime.now().isoformat()
            
        self._save_subscriptions(subs)
        self._save_history(history)
        logger.info("Subscription checks completed.")

    def _check_single_subscription(self, sub: Dict, history: Dict):
        keyword = sub['keyword']
        cloud_type = sub['cloud_type']
        filters = sub.get('filter_config', {})
        
        # 1. Search
        result = self.pan_search_service.search(keyword, cloud_types=[cloud_type])
        if not result.get('success'):
            logger.warning(f"Search failed for {keyword}: {result.get('error')}")
            sub['last_message'] = f"Search failed: {result.get('error')}"
            return
            
        items = result.get('data', [])
        logger.info(f"Subscription '{keyword}': Found {len(items)} items")
        
        # 2. Filter & Match
        matched_items = []
        for item in items:
            title = item.get('title', '')
            url = item.get('url', '')
            
            # Smart Dedup: Check if URL matches history
            if url in history:
                continue
                
            # Episode Filtering
            parsed_season, parsed_episode = self._parse_episode_info(title)
            current_season = sub.get('current_season', 0)
            current_episode = sub.get('current_episode', 0)
            
            # If we tracked progress, skip old episodes
            is_new = False
            if parsed_season == 0 and parsed_episode == 0:
                is_new = True # Unknown format, trust history check
            elif parsed_season > current_season:
                is_new = True
            elif parsed_season == current_season and parsed_episode > current_episode:
                is_new = True
            
            if not is_new:
                continue

            if self._matches_filters(title, filters):
                matched_items.append(item)
        
        if not matched_items:
            logger.info(f"Subscription '{keyword}': No new items matched filters")
            sub['last_message'] = "No new matches found"
            return

        # 3. Download (All unique matched items)
        count = 0
        success_count = 0
        
        # Track max progress to update subscription
        max_season = sub.get('current_season', 0)
        max_episode = sub.get('current_episode', 0)
        
        for item in matched_items:
            try:
                success = self.trigger_download(item, cloud_type)
                if success:

                    history[item['url']] = {
                        'sub_id': sub['id'],
                        'title': item.get('title'),
                        'downloaded_at': datetime.now().isoformat(),
                        'cloud_type': cloud_type
                    }
                    success_count += 1
                    
                    # Update progress if this item is newer
                    s, e = self._parse_episode_info(item.get('title', ''))
                    if s > max_season:
                        max_season = s
                        max_episode = e
                    elif s == max_season and e > max_episode:
                        max_episode = e
                        
                    logger.info(f"Successfully triggered download for {item.get('title')}")
            except Exception as e:
                logger.error(f"Download failed for item {item.get('title')}: {e}")
                
            count += 1
        
        # Save progress
        sub['current_season'] = max_season
        sub['current_episode'] = max_episode
        sub['last_message'] = f"Found {len(matched_items)} matches, downloaded {success_count}. Now at S{max_season}E{max_episode}"

    def _parse_episode_info(self, title: str) -> tuple:
        """Parse season and episode from title. Returns (season, episode). Default (0, 0)."""
        import re
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
        """
        Check if title matches include/exclude rules.
        """
        # Include: Must match ALL
        includes = filters.get('include', [])
        if isinstance(includes, str): includes = [includes]
        for inc in includes:
            if not inc: continue
            try:
                if not re.search(inc, title, re.IGNORECASE):
                    return False
            except re.error:
                # Fallback to simple string check if regex invalid
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
                # Check for 115 share link
                # Common formats: https://115.com/s/sw3xxxx
                share_code_match = re.search(r'115\.com/s/([a-z0-9]+)', url, re.IGNORECASE)
                if share_code_match:
                    share_code = share_code_match.group(1)
                    # Use password from item if available, or empty
                    # (pan.jivon.de usually provides password in separate field)
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
                     # Assuming Cloud123Service has create_offline_task
                     if hasattr(self.cloud123_service, 'create_offline_task'):
                         result = self.cloud123_service.create_offline_task(url, save_dir_id='/')
                         return result.get('success', False)
                 
                 # 123 Share links handling if API supports it
                 # For now, focus on magnet support for 123 from general search, 
                 # but pan.jivon.de for 123 usually returns direct links or share links.
                 # If share link, would need "save share" logic for 123.
                 # Will assume not implemented for simplified MVP unless needed.
            
            return False
            
        except Exception as e:
            logger.error(f"Download trigger error: {e}")
            return False
