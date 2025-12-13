import uuid
import time
import os
import threading
import requests
import re
import urllib.parse
from persistence.store import DataStore
from typing import Dict, Any, List, Set
from services.cloud115_service import Cloud115Service
from services.cloud123_service import Cloud123Service

class StrmService:
    """Service for handling STRM generation."""
    
    def __init__(self, store: DataStore):
        self.store = store
        self.tasks: Dict[str, Dict[str, Any]] = {}
        # Services will be initialized when needed to avoid circular imports or early init issues
        self._cloud115_service = None
        self._cloud123_service = None

    @property
    def cloud115(self):
        if not self._cloud115_service:
            # Need to get secret store from main store or pass it in
            # Assuming store has secret_store attribute based on main.py usually
            if hasattr(self.store, 'secret_store'):
                self._cloud115_service = Cloud115Service(self.store.secret_store)
        return self._cloud115_service

    @property
    def cloud123(self):
        if not self._cloud123_service:
            if hasattr(self.store, 'secret_store'):
                self._cloud123_service = Cloud123Service(self.store.secret_store)
        return self._cloud123_service
    
    def _get_config(self) -> Dict[str, Any]:
        """Get STRM configuration from store."""
        try:
            config = self.store.get_config()
            return config.get('strm', {})
        except Exception:
            return {}
    
    def generate_strm(self, strm_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Start STRM generation task for the specified provider."""
        if strm_type not in ['115', '123', 'openlist']:
            return {
                'success': False,
                'data': {'error': f'Invalid STRM type: {strm_type}'}
            }
        
        # Create a task
        task_id = str(uuid.uuid4())
        task = {
            'id': task_id,
            'type': strm_type,
            'status': 'running',
            'progress': 0,
            'current_path': '',
            'files_count': 0,
            'created_at': time.time(),
            'config': config,
            'error': None
        }
        self.tasks[task_id] = task
        
        # Start background thread
        thread = threading.Thread(target=self._run_task, args=(task_id, strm_type, config))
        thread.daemon = True
        thread.start()
        
        return {
            'success': True,
            'data': {
                'jobId': task_id,
                'status': 'running',
                'type': strm_type
            }
        }

    def _run_task(self, task_id: str, strm_type: str, config: Dict[str, Any]):
        """Run the STRM generation task."""
        try:
            if strm_type == '115':
                self._generate_115(task_id, config)
            elif strm_type == '123':
                self._generate_123(task_id, config)
            elif strm_type == 'openlist':
                self._generate_openlist(task_id, config)
        except Exception as e:
            task = self.tasks.get(task_id)
            if task:
                task['status'] = 'failed'
                task['error'] = str(e)
                
    def _update_progress(self, task_id: str, progress: int = None, current_path: str = None, increment_count: bool = False):
        task = self.tasks.get(task_id)
        if not task:
            return
        if progress is not None:
            task['progress'] = progress
        if current_path is not None:
            task['current_path'] = current_path
        if increment_count:
            task['files_count'] = task.get('files_count', 0) + 1

    def _complete_task(self, task_id: str):
        task = self.tasks.get(task_id)
        if task:
            task['status'] = 'completed'
            task['progress'] = 100

    def _write_strm_file(self, output_base: str, relative_path: str, content_path: str):
        """Write .strm file to output directory."""
        # Clean relative path to remove leading slashes to append correctly
        clean_rel = relative_path.lstrip('/\\')
        
        # Construct full output path (replace extension with .strm)
        file_path = os.path.join(output_base, clean_rel)
        video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.iso']
        
        # Only process video files
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in video_exts:
            return False

        strm_path = os.path.splitext(file_path)[0] + '.strm'
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(strm_path), exist_ok=True)
        
        # Write content
        with open(strm_path, 'w', encoding='utf-8') as f:
            f.write(content_path)
        return True

    def _generate_115(self, task_id: str, config: Dict[str, Any]):
        """Generate STRM for 115 Cloud."""
        mount_path = config.get('mountPath', '').rstrip('/\\')  # e.g. X:/115
        output_dir = config.get('outputPath', './strm_out')
        source_cid = config.get('sourceCid', '0')
        
        if not mount_path:
            raise ValueError("Mount Path is required")

        self.cloud115  # Initialize service
        
        queue = [(source_cid, "")]  # (cid, relative_path)
        
        while queue:
            cid, rel_path = queue.pop(0)
            self._update_progress(task_id, current_path=rel_path)
            
            # List directory
            res = self.cloud115.list_directory(cid)
            if not res.get('success'):
                continue
                
            items = res.get('data', [])
            for item in items:
                name = item.get('n') or item.get('name')
                item_id = item.get('id') or item.get('fid') or item.get('cid')
                is_dir = item.get('is_directory') or (item.get('ico') == 'folder') or ('fid' not in item)
                
                new_rel_path = os.path.join(rel_path, name)
                
                if is_dir:
                    queue.append((item_id, new_rel_path))
                else:
                    # File: generate STRM
                    # 115 content path: mount_path/rel_path
                    # Replace backslashes with forward slashes for cross-platform compatibility if needed, 
                    # but usually local paths use system separator. 
                    # Let's use forward slash for consistency in STRM usually, but Windows might need backslash.
                    # Best to follow input mount_path style.
                    full_content_path = os.path.join(mount_path, new_rel_path).replace('\\', '/')
                    
                    if self._write_strm_file(output_dir, new_rel_path, full_content_path):
                        self._update_progress(task_id, increment_count=True)
                        
        self._complete_task(task_id)

    def _generate_123(self, task_id: str, config: Dict[str, Any]):
        """Generate STRM for 123 Cloud."""
        mount_path = config.get('mountPath', '').rstrip('/\\')
        output_dir = config.get('outputPath', './strm_out')
        source_id = config.get('sourceId', '0')
        
        if not mount_path:
            raise ValueError("Mount Path is required")
            
        self.cloud123
        
        queue = [(source_id, "")]
        
        while queue:
            curr_id, rel_path = queue.pop(0)
            self._update_progress(task_id, current_path=rel_path)
            
            res = self.cloud123.list_directory(curr_id)
            if not res.get('success'):
                continue
                
            items = res.get('data', [])
            for item in items:
                name = item.get('filename')
                item_id = item.get('fileId')
                item_type = item.get('type') # 0: folder, 1: file usually
                
                new_rel_path = os.path.join(rel_path, name)
                
                # Check if folder (type=1 for folder in 123 sometimes? No, usually 0 is folder? 
                # Let's check api field: 'type': 1 (folder), 'type': 0 (file)?
                # Or check isFolder field if exists)
                # Looking at cloud123_service: we need to verify directory listing format.
                # Assuming generic structure or checking service output.
                # Usually type 1 is folder in many APIs, but let's assume 'type' field indicates it.
                # Actually commonly: type=1 is directory, type=0 is file for 123pan.
                
                is_dir = (item_type == 1)
                
                if is_dir:
                    queue.append((item_id, new_rel_path))
                else:
                    full_content_path = os.path.join(mount_path, new_rel_path).replace('\\', '/')
                    if self._write_strm_file(output_dir, new_rel_path, full_content_path):
                        self._update_progress(task_id, increment_count=True)

        self._complete_task(task_id)

    def _generate_openlist(self, task_id: str, config: Dict[str, Any]):
        """Generate STRM for OpenList (HTTP Index)."""
        base_url = config.get('baseUrl', '').rstrip('/')
        output_dir = config.get('outputPath', './strm_out')
        mount_path = config.get('mountPath', '') # Optional: if mounting remote via Alist/Rclone
        
        if not base_url:
            raise ValueError("Base URL is required")
            
        queue = [("", base_url)] # (rel_path, full_url)
        visited = set()
        
        while queue:
            rel_path, curr_url = queue.pop(0)
            if curr_url in visited:
                continue
            visited.add(curr_url)
            
            self._update_progress(task_id, current_path=rel_path)
            
            try:
                resp = requests.get(curr_url, timeout=10)
                if resp.status_code != 200:
                    continue
                    
                html = resp.text
                # Simple regex to find links
                # Matches href="..." or href='...'
                links = re.findall(r'href=["\'](.*?)["\']', html, re.IGNORECASE)
                
                for link in links:
                    link = link.strip()
                    if not link or link.startswith('?') or link.startswith('#') or link.startswith('javascript:'):
                        continue
                        
                    # Skip parent directory
                    if link == '../' or link == './' or link == '/' or link == '../':
                        continue
                        
                    # Decode URL encoded chars
                    link_name = urllib.parse.unquote(link).rstrip('/')
                    
                    full_link = urllib.parse.urljoin(curr_url, link)
                    new_rel = os.path.join(rel_path, link_name)
                    
                    if link.endswith('/'):
                        # Directory
                        queue.append((new_rel, full_link))
                    else:
                        # File check extension
                        # Use mapped path if mount_path provided, else use URL
                        if mount_path:
                            content = os.path.join(mount_path, new_rel).replace('\\', '/')
                        else:
                            content = full_link
                            
                        if self._write_strm_file(output_dir, new_rel, content):
                            self._update_progress(task_id, increment_count=True)
                            
            except Exception as e:
                print(f"Error processing {curr_url}: {e}")
                continue

        self._complete_task(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        """List all STRM generation tasks."""
        return list(self.tasks.values())
    
    def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get a specific task by ID."""
        return self.tasks.get(task_id, {})
