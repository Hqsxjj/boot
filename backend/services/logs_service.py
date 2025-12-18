import os
import time
import glob
from typing import List, Dict, Any, Optional


class LogsService:
    """Service for reading application logs."""
    
    def __init__(self, log_dir: str = None):
        # Use DATA_DIR environment variable or fallback
        data_dir = os.environ.get('DATA_DIR', '/data')
        self.log_dir = log_dir or os.path.join(data_dir, 'logs')
    
    def get_logs(self, limit: int = 100, since: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Get logs from all application log files.
        
        Args:
            limit: Maximum number of log entries to return
            since: Unix timestamp - only return logs after this time
        
        Returns:
            List of log entries in reverse chronological order (newest first)
        """
        logs = []
        
        try:
            # Create log dir if not exists
            os.makedirs(self.log_dir, exist_ok=True)
            
            # Find all log files
            log_files = glob.glob(os.path.join(self.log_dir, '*.log'))
            
            if not log_files:
                return self._get_default_logs()
            
            # Read from all log files
            all_lines = []
            for log_file in log_files:
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        # Tag each line with its source file
                        source = os.path.basename(log_file).replace('.log', '')
                        for line in lines:
                            all_lines.append((source, line))
                except Exception:
                    continue
            
            # Parse log entries (newest first)
            for source, line in reversed(all_lines):
                line = line.strip()
                if not line:
                    continue
                
                try:
                    entry = self._parse_log_line(line, source)
                    
                    if entry:
                        if since and entry.get('timestamp', 0) < since:
                            continue
                        
                        logs.append(entry)
                        
                        if len(logs) >= limit:
                            break
                except Exception:
                    continue
            
        except Exception as e:
            return self._get_default_logs()
        
        return logs if logs else self._get_default_logs()
    
    def _parse_log_line(self, line: str, source: str = 'app') -> Optional[Dict[str, Any]]:
        """Parse a single log line."""
        timestamp = time.time()
        level = 'INFO'
        message = line
        module = source
        
        # Parse format: HH:MM:SS │ 级别 │ 模块 │ 消息
        # Or: YYYY-MM-DD HH:MM:SS │ 级别 │ 模块 │ 消息
        try:
            if '│' in line:
                parts = line.split('│')
                if len(parts) >= 4:
                    time_part = parts[0].strip()
                    level_part = parts[1].strip()
                    module_part = parts[2].strip()
                    message = '│'.join(parts[3:]).strip()
                    
                    # Map Chinese level to English
                    level_map = {
                        '调试': 'DEBUG', '信息': 'INFO', '警告': 'WARN',
                        '错误': 'ERROR', '严重': 'CRITICAL',
                        'DEBUG': 'DEBUG', 'INFO': 'INFO', 'WARNING': 'WARN',
                        'WARN': 'WARN', 'ERROR': 'ERROR', 'CRITICAL': 'CRITICAL'
                    }
                    level = level_map.get(level_part, 'INFO')
                    module = module_part
                    
                    # Try to parse time
                    try:
                        from datetime import datetime
                        if len(time_part) > 10:
                            dt = datetime.strptime(time_part, '%Y-%m-%d %H:%M:%S')
                        else:
                            dt = datetime.strptime(time_part, '%H:%M:%S')
                            dt = dt.replace(year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
                        timestamp = dt.timestamp()
                    except:
                        pass
        except Exception:
            pass
        
        return {
            'time': self._format_timestamp(timestamp),
            'timestamp': timestamp,
            'status': self._map_level_to_status(level),
            'level': module,  # Use module as "任务" column
            'message': message[:500]
        }
    
    def _format_timestamp(self, ts: float) -> str:
        """Format timestamp for display."""
        from datetime import datetime
        dt = datetime.fromtimestamp(ts)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    def _map_level_to_status(self, level: str) -> str:
        """Map log level to status for UI."""
        level_map = {
            'DEBUG': 'DEBUG',
            'INFO': 'INFO',
            'WARNING': 'WARN',
            'WARN': 'WARN',
            'ERROR': 'ERROR',
            'CRITICAL': 'ERROR',
            'SUCCESS': 'SUCCESS'
        }
        return level_map.get(level.upper(), 'INFO')
    
    def _get_default_logs(self) -> List[Dict[str, Any]]:
        """Return default sample logs when no files available."""
        now = time.time()
        return [
            {
                'time': self._format_timestamp(now),
                'timestamp': now,
                'status': 'INFO',
                'level': '系统',
                'message': '日志系统已启动 - 等待新日志写入...'
            }
        ]
