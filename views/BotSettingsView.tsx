
import React, { useState } from 'react';
import { AppConfig } from '../types';
import { loadConfig, saveConfig } from '../services/mockConfig';
import { CommandCard } from '../components/CommandCard';
import { Bot, Save, RefreshCw, MessageSquare } from 'lucide-react';
import { SensitiveInput } from '../components/SensitiveInput';

export const BotSettingsView: React.FC = () => {
  const [config, setConfig] = useState<AppConfig>(loadConfig());
  const [isSaving, setIsSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const updateNested = (section: keyof AppConfig, key: string, value: any) => {
    setConfig(prev => ({
      ...prev,
      [section]: { ...(prev[section] as any), [key]: value }
    }));
  };

  const handleSave = () => {
    setIsSaving(true);
    setTimeout(() => {
      saveConfig(config);
      setIsSaving(false);
      setToast('机器人配置已保存');
      setTimeout(() => setToast(null), 3000);
    }, 800);
  };

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
  const inputClass = "w-full pl-4 pr-10 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-blue-500 outline-none transition-all font-mono text-sm backdrop-blur-sm shadow-inner";
  const actionBtnClass = "px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-colors";

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
      {toast && (
        <div className="fixed top-6 right-6 bg-slate-800/90 backdrop-blur-md text-white px-6 py-3 rounded-xl shadow-2xl z-50 flex items-center gap-3 font-medium border-[0.5px] border-slate-700/50">
          <RefreshCw size={18} className="animate-spin text-brand-400" />
          {toast}
        </div>
      )}

      <div className="flex flex-col md:flex-row justify-between items-center pb-2 gap-4">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight drop-shadow-sm">机器人设置</h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-full">
        {/* Telegram Config */}
        <section className={`${glassCardClass} h-fit`}>
          <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
            <div className="flex items-center gap-3">
               <Bot size={18} className="text-blue-500" />
               <h3 className="font-bold text-slate-700 dark:text-slate-200">核心参数</h3>
            </div>
            <button
                onClick={handleSave}
                disabled={isSaving}
                className={`${actionBtnClass} bg-blue-50 text-blue-600 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400 dark:hover:bg-blue-900/40 disabled:opacity-50`}
            >
                {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                保存设置
            </button>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <label className="flex items-center text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                机器人令牌 (Bot Token)
              </label>
              <SensitiveInput
                  value={config.telegram.botToken}
                  onChange={(e) => updateNested('telegram', 'botToken', e.target.value)}
                  className={inputClass}
                  placeholder="123456:ABC-DEF..."
                />
            </div>

            <div>
              <label className="flex items-center text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                管理员 ID (Admin User ID)
              </label>
              <SensitiveInput
                value={config.telegram.adminUserId}
                onChange={(e) => updateNested('telegram', 'adminUserId', e.target.value)}
                className={inputClass}
                placeholder="123456789"
              />
            </div>
            
             <div>
              <label className="flex items-center text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                通知频道 ID
              </label>
              <SensitiveInput
                value={config.telegram.notificationChannelId}
                onChange={(e) => updateNested('telegram', 'notificationChannelId', e.target.value)}
                className={inputClass}
                placeholder="-100123456789"
              />
            </div>
            
             <div className="flex items-center gap-3 pt-2">
               {/* Small Toggle for Whitelist */}
               <div className="relative inline-block w-9 h-5 transition duration-200 ease-in-out rounded-full cursor-pointer">
                  <input 
                    id="whitelist" 
                    type="checkbox" 
                    className="peer sr-only"
                    checked={config.telegram.whitelistMode}
                    onChange={(e) => updateNested('telegram', 'whitelistMode', e.target.checked)}
                  />
                  <label htmlFor="whitelist" className="block h-5 overflow-hidden bg-slate-200 dark:bg-slate-700 rounded-full cursor-pointer peer-checked:bg-slate-900 dark:peer-checked:bg-white after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white dark:after:bg-slate-900 after:w-4 after:h-4 after:rounded-full after:shadow-sm after:transition-all peer-checked:after:translate-x-full"></label>
              </div>
              <label htmlFor="whitelist" className="text-sm font-medium text-slate-700 dark:text-slate-300 cursor-pointer select-none">开启白名单模式 (仅管理员可用)</label>
            </div>
          </div>
        </section>

        {/* Command Cheat Sheet */}
        <section className={`${glassCardClass} flex flex-col h-[500px] lg:h-auto`}>
           <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center gap-3">
             <MessageSquare size={18} className="text-teal-500" />
             <h3 className="font-bold text-slate-700 dark:text-slate-200">指令速查</h3>
           </div>
           <div className="p-4 overflow-y-auto custom-scrollbar flex-1">
             <div className="grid grid-cols-1 gap-3">
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
    </div>
  );
};
