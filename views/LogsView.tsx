
import React, { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { RefreshCw, X } from 'lucide-react';

interface LogsViewProps {
  onClose?: () => void;
}

export const LogsView: React.FC<LogsViewProps> = ({ onClose }) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastTimestamp, setLastTimestamp] = useState<number | null>(null);

  // Load logs on mount and periodically refresh
  useEffect(() => {
    fetchLogs();

    // Set up periodic refresh every 2 seconds for live feeling
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, []);

  const fetchLogs = async () => {
    try {
      const data = await api.fetchLogs(100);
      setLogs(data || []);
      if (data && data.length > 0) {
        setLastTimestamp(data[0].timestamp);
      }
      setIsLoading(false);
    } catch (e) {
      console.error('Failed to fetch logs:', e);
      // Keep existing logs if fetch fails
      setIsLoading(false);
    }
  };

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  // Function to mask sensitive data in logs
  const maskLogContent = (content: string) => {
    return content
      // Mask Telegram Bot Tokens (e.g., 123456:ABC-DEF...)
      .replace(/\d{8,}:[a-zA-Z0-9_-]{10,}/g, '[TOKEN HIDDEN]')
      // Mask Generic Keys/Secrets (e.g., key=..., secret=...)
      .replace(/(token|key|secret|password|auth|sk_|pk_)([:=]\s?)([^\s]+)/gi, '$1$2******')
      // Mask Cookie fields
      .replace(/(uid|cid|seid|cookie)([:=]\s?)([^\s]+)/gi, '$1$2******')
      // Mask API Keys (long alphanumeric strings)
      .replace(/([a-zA-Z0-9]{32,})/g, '******');
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-[90vw] h-[90vh] bg-white dark:bg-slate-900 rounded-2xl shadow-2xl flex flex-col border border-slate-200 dark:border-slate-700 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-slate-200 dark:bg-slate-800 rounded-lg">
              <RefreshCw size={18} className={`text-slate-500 dark:text-slate-400 ${isLoading ? 'animate-spin' : ''}`} />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-800 dark:text-white">运行日志</h2>
              <div className="text-xs text-slate-500">实时监控系统运行状态</div>
            </div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20 dark:hover:text-red-400 rounded-lg transition-colors text-slate-400"
            >
              <X size={20} />
            </button>
          )}
        </div>

        {/* Log Content */}
        <div className="flex-1 bg-slate-950 text-slate-200 font-mono text-xs overflow-hidden flex flex-col relative">
          {/* Log Header Row */}
          <div className="grid grid-cols-12 gap-2 px-4 py-2 bg-slate-900 border-b border-slate-800 font-bold text-slate-400 uppercase tracking-wider">
            <div className="col-span-2">时间</div>
            <div className="col-span-1">状态</div>
            <div className="col-span-2">任务模块</div>
            <div className="col-span-7">详细信息</div>
          </div>

          <div className="p-4 overflow-y-auto flex-1 scroll-smooth custom-scrollbar space-y-1" ref={scrollRef}>
            {logs.length === 0 ? (
              <div className="flex items-center justify-center h-full text-slate-500">
                暂无日志记录
              </div>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="grid grid-cols-12 gap-2 hover:bg-white/5 p-1 rounded transition-colors items-start">
                  <div className="col-span-2 text-slate-500">{log.time.split(' ')[1]} <span className="text-[10px] opacity-50">{log.time.split(' ')[0]}</span></div>
                  <div className="col-span-1">
                    <span className={`px-1.5 py-0.5 rounded-[2px] text-[10px] font-bold ${log.status === 'INFO' ? 'text-blue-400 bg-blue-500/10' :
                      log.status === 'WARN' ? 'text-amber-400 bg-amber-500/10' :
                        log.status === 'SUCCESS' ? 'text-emerald-400 bg-emerald-500/10' :
                          'text-red-400 bg-red-500/10'
                      }`}>
                      {log.status}
                    </span>
                  </div>
                  <div className="col-span-2 text-indigo-300 font-medium truncate" title={log.level}>{log.level || 'SYSTEM'}</div>
                  <div className="col-span-7 text-slate-300 break-words whitespace-pre-wrap leading-relaxed">
                    {maskLogContent(log.message || '')}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
