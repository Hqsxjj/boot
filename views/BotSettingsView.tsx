
import React from 'react';
import { CommandCard } from '../components/CommandCard';
import { MessageSquare } from 'lucide-react';

export const BotSettingsView: React.FC = () => {
  const commands = [
    { cmd: '/start', desc: '初始化机器人并检查 115 账号连接状态', example: '/start' },
    { cmd: '/magnet', desc: '添加磁力/Ed2k/HTTP 链接离线任务 (115)', example: '/magnet magnet:?xt=urn:btih:...' },
    { cmd: '/123_offline', desc: '添加 123 云盘离线下载任务', example: '/123_offline http://example.com/file.mp4' },
    { cmd: '/link', desc: '转存 115 分享链接 (支持加密)', example: '/link https://115.com/s/...' },
    { cmd: '/rename', desc: '使用 TMDB 手动重命名指定文件/文件夹', example: '/rename <file_id> <tmdb_id>' },
    { cmd: '/organize', desc: '对 115 默认目录执行自动分类整理', example: '/organize' },
    { cmd: '/123_organize', desc: '对 123 云盘目录执行自动分类整理', example: '/123_organize' },
    { cmd: '/dir', desc: '设置或查看当前默认下载文件夹 (CID)', example: '/dir 29384812' },
    { cmd: '/quota', desc: '查看 115 账号离线配额和空间使用情况', example: '/quota' },
    { cmd: '/tasks', desc: '查看当前正在进行的离线任务列表', example: '/tasks' },
  ];

  const glassCardClass = "bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border-[0.5px] border-white/40 dark:border-white/10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.2)] ring-1 ring-white/50 dark:ring-white/5 inset";

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
      <div className="flex flex-col md:flex-row justify-between items-center pb-2 gap-4">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight drop-shadow-sm">机器人指令</h2>
      </div>

      {/* Command Cheat Sheet - Full Width */}
      <section className={`${glassCardClass} flex flex-col`}>
        <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center gap-3">
          <MessageSquare size={18} className="text-teal-500" />
          <h3 className="font-bold text-slate-700 dark:text-slate-200">指令速查</h3>
        </div>
        <div className="p-4 overflow-y-auto custom-scrollbar flex-1">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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
      </section>
    </div>
  );
};
