
import React, { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { RefreshCw } from 'lucide-react';

export const LogsView: React.FC = () => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastTimestamp, setLastTimestamp] = useState<number | null>(null);

  // Load logs on mount and periodically refresh
  useEffect(() => {
    fetchLogs();

    // Set up periodic refresh every 5 seconds
    const interval = setInterval(fetchLogs, 5000);
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

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-140px)] flex items-center justify-center text-slate-500 gap-2">
        <RefreshCw className="animate-spin" /> 正在加载日志...
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-140px)] flex flex-col">
       <div className="mb-4 flex justify-between items-end">
         <h2 className="text-2xl font-bold text-slate-800 dark:text-white drop-shadow-sm">运行日志</h2>
       </div>

       <div className="flex-1 bg-white/70 dark:bg-slate-900/50 backdrop-blur-md rounded-xl shadow-inner border border-slate-200/50 dark:border-slate-800/50 overflow-hidden flex flex-col font-mono text-xs">
         {/* Log Header */}
         <div className="bg-slate-100/50 dark:bg-slate-800/50 px-3 py-2 border-b border-slate-200/50 dark:border-slate-700/50 grid grid-cols-12 gap-2 font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wider backdrop-blur-sm">
             <div className="col-span-3">时间</div>
             <div className="col-span-1">状态</div>
             <div className="col-span-2">任务</div>
             <div className="col-span-6">运行结果</div>
         </div>

         <div className="p-0 overflow-y-auto flex-1 scroll-smooth custom-scrollbar" ref={scrollRef}>
             {logs.length === 0 ? (
               <div className="flex items-center justify-center h-full text-slate-400">
                 暂无日志
               </div>
             ) : (
               <>
                 {logs.map((log, i) => (
                     <div key={i} className="grid grid-cols-12 gap-2 px-3 py-1 border-b border-slate-50/50 dark:border-slate-800/50 hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors items-center">
                         <div className="col-span-3 text-slate-400 opacity-80 scale-95 origin-left">{log.time}</div>
                         <div className="col-span-1">
                             <span className={`px-1.5 py-0.5 rounded-[3px] text-[9px] font-bold border ${
                                 log.status === 'INFO' ? 'bg-blue-50/80 text-blue-600 border-blue-100 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-900' :
                                 log.status === 'WARN' ? 'bg-amber-50/80 text-amber-600 border-amber-100 dark:bg-amber-900/30 dark:text-amber-400 dark:border-amber-900' :
                                 log.status === 'SUCCESS' ? 'bg-emerald-50/80 text-emerald-600 border-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-400 dark:border-emerald-900' :
                                 'bg-red-50/80 text-red-600 border-red-100 dark:bg-red-900/30 dark:text-red-400 dark:border-red-900'
                             }`}>
                                 {log.status}
                             </span>
                         </div>
                         <div className="col-span-2 font-medium text-slate-700 dark:text-slate-300 truncate">{log.level || 'INFO'}</div>
                         <div className="col-span-6 text-slate-600 dark:text-slate-400 truncate" title={log.message || ''}>
                             {maskLogContent(log.message || '')}
                         </div>
                     </div>
                 ))}
                 <div className="py-2 text-center opacity-50">
                      <div className="animate-pulse w-1.5 h-3 bg-brand-400 inline-block align-middle"></div>
                 </div>
               </>
             )}
         </div>
       </div>
     </div>
   );
};
