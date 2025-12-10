
import React from 'react';
import { CommandCard } from '../components/CommandCard';
import { Activity, Server, Database, Wifi, Zap, Wand2 } from 'lucide-react';

export const DashboardView: React.FC = () => {
  const commands = [
    { cmd: '/start', desc: '初始化机器人并检查 115 账号连接状态', example: '/start' },
    { cmd: '/magnet', desc: '添加磁力/Ed2k/HTTP 链接离线任务 (115)', example: '/magnet magnet:?xt=urn:btih:...' },
    { cmd: '/123_offline', desc: '添加 123 云盘离线下载任务', example: '/123_offline http://example.com/file.mp4' },
    { cmd: '/link', desc: '转存 115 分享链接 (支持加密)', example: '/link https://115.com/s/...' },
    { cmd: '/organize', desc: '对 115 默认目录执行自动分类整理', example: '/organize' },
    { cmd: '/123_organize', desc: '对 123 云盘目录执行自动分类整理', example: '/123_organize' },
    { cmd: '/rename', desc: '手动重命名指定文件 (TMDB 匹配)', example: '/rename <file_id> <tmdb_id>' },
    { cmd: '/quota', desc: '查看账号离线配额和空间使用情况', example: '/quota' },
  ];

  const glassCardClass = "bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border-[0.5px] border-white/40 dark:border-white/10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.2)] ring-1 ring-white/50 dark:ring-white/5 inset";

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-center pb-2 gap-4">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight drop-shadow-sm">系统概览</h2>
      </div>

      {/* Status Widgets */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-gradient-to-br from-brand-500 to-brand-600 rounded-xl p-6 text-white shadow-lg shadow-brand-500/20 relative overflow-hidden group">
           <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
              <Activity size={80} />
           </div>
          <div className="flex justify-between items-start mb-4 relative z-10">
            <div className="p-2 bg-white/20 rounded-lg backdrop-blur-sm">
              <Activity size={24} />
            </div>
            <span className="bg-green-400/90 text-[10px] font-bold px-2 py-0.5 rounded-full text-brand-900 uppercase shadow-sm">运行中</span>
          </div>
          <div className="text-3xl font-bold mb-1 relative z-10">活跃</div>
          <div className="text-brand-100 text-xs relative z-10">Docker 服务运行正常</div>
        </div>

        <div className={`${glassCardClass} p-6`}>
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-orange-50 dark:bg-orange-900/20 text-orange-600 dark:text-orange-400 rounded-lg shadow-inner">
              <Database size={24} />
            </div>
            <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">API 状态</span>
          </div>
          <div className="text-3xl font-bold text-slate-800 dark:text-white mb-1">已连接</div>
          <div className="text-slate-500 dark:text-slate-400 text-xs flex items-center gap-1 font-mono">
             <Wifi size={12} className="text-green-500" /> Ping: 45ms
          </div>
        </div>
        
         <div className={`${glassCardClass} p-6`}>
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-teal-50 dark:bg-teal-900/20 text-teal-600 dark:text-teal-400 rounded-lg shadow-inner">
              <Wand2 size={24} />
            </div>
            <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">智能整理</span>
          </div>
          <div className="text-3xl font-bold text-slate-800 dark:text-white mb-1">开启</div>
          <div className="text-slate-500 dark:text-slate-400 text-xs">TMDB 插件正常工作中</div>
        </div>

         <div className={`${glassCardClass} p-6`}>
          <div className="flex justify-between items-start mb-4">
            <div className="p-2 bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 rounded-lg shadow-inner">
              <Zap size={24} />
            </div>
            <span className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">下载队列</span>
          </div>
          <div className="text-3xl font-bold text-slate-800 dark:text-white mb-1">0</div>
          <div className="text-slate-500 dark:text-slate-400 text-xs">当前无正在进行的任务</div>
        </div>
      </div>

      {/* Commands Grid */}
      <div className={`${glassCardClass} overflow-hidden`}>
        <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center gap-3">
           <Server size={18} className="text-slate-400" />
           <h3 className="font-bold text-slate-700 dark:text-slate-200">指令速查表</h3>
        </div>
        <div className="p-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {commands.map((c) => (
                <CommandCard 
                key={c.cmd} 
                command={c.cmd} 
                description={c.desc} 
                example={c.example} 
                />
            ))}
            </div>
        </div>
      </div>

      {/* Quick Help */}
      <div className={`${glassCardClass} p-6`}>
        <h4 className="font-bold text-slate-800 dark:text-white mb-3 text-sm">使用提示</h4>
        <ul className="list-disc list-inside text-xs text-slate-600 dark:text-slate-400 space-y-2 leading-relaxed">
            <li>直接发送磁力链接、ed2k 链接或 HTTP 链接给机器人，它会自动识别并添加任务。</li>
            <li>发送 115 分享链接 (如 115.com/s/...)，机器人会自动转存到默认目录。</li>
            <li>如果启用了自动整理，任务完成后机器人会尝试匹配 TMDB 信息并按规则移动文件。</li>
            <li>对于识别错误的文件，可以使用 <code>/rename</code> 手动修正。</li>
        </ul>
      </div>
    </div>
  );
};
