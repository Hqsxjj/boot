
import React, { useEffect, useRef } from 'react';

export const LogsView: React.FC = () => {
  const scrollRef = useRef<HTMLDivElement>(null);
  
  // Mock logs
  const logs = [
    { time: '2023-10-27 10:30:01', status: 'INFO', task: '系统启动', result: '初始化完成' },
    { time: '2023-10-27 10:30:02', status: 'INFO', task: '连接 Telegram', result: '正在连接 Bot API...' },
    { time: '2023-10-27 10:30:04', status: 'SUCCESS', task: '连接 Telegram', result: '已连接 (@My115DownloaderBot)' },
    { time: '2023-10-27 10:30:05', status: 'WARN', task: '代理检查', result: '使用代理: 192.168.1.5:7890' },
    { time: '2023-10-27 10:31:00', status: 'INFO', task: '115 鉴权', result: 'Cookie 有效. UID: 123****89' },
    { time: '2023-10-27 10:35:12', status: 'INFO', task: '接收指令', result: '收到用户 99887766 的 /tasks 指令' },
    { time: '2023-10-27 10:35:15', status: 'SUCCESS', task: '查询任务', result: '返回活跃任务列表 (0)' },
    { time: '2023-10-27 11:02:00', status: 'INFO', task: '自动整理', result: '开始扫描默认下载目录...' },
    { time: '2023-10-27 11:02:45', status: 'SUCCESS', task: '自动整理', result: '完成. 移动 3 个文件, 重命名 3 个文件.' },
    { time: '2023-10-27 11:05:00', status: 'INFO', task: 'Emby 通知', result: '发送播放报告到 Telegram' },
    { time: '2023-10-27 11:10:00', status: 'INFO', task: 'STRM 生成', result: '检测到新文件，生成索引...' },
    { time: '2023-10-27 11:10:02', status: 'SUCCESS', task: 'STRM 生成', result: '生成完成: /strm/bot/Movie/Test.strm' },
  ];

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

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
    <div className="h-[calc(100vh-140px)] flex flex-col">
       <div className="mb-4 flex justify-between items-end">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white drop-shadow-sm">运行日志</h2>
        {/* Removed English text */}
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
                    <div className="col-span-2 font-medium text-slate-700 dark:text-slate-300 truncate">{log.task}</div>
                    <div className="col-span-6 text-slate-600 dark:text-slate-400 truncate" title={log.result}>
                        {maskLogContent(log.result)}
                    </div>
                </div>
            ))}
            <div className="py-2 text-center opacity-50">
                 <div className="animate-pulse w-1.5 h-3 bg-brand-400 inline-block align-middle"></div>
            </div>
        </div>
      </div>
    </div>
  );
};
