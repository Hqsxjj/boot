import React, { useState, useEffect } from 'react';
import { AppConfig } from '../types';
import { api } from '../services/api';
import { Save, RefreshCw, Clapperboard, BarChart3, Clock, Zap, Bell, Copy, FileWarning, Search, CheckCircle2 } from 'lucide-react';
import { SensitiveInput } from '../components/SensitiveInput';

// === 定义默认配置 (防止后端连不上时页面白屏) ===
const DEFAULT_CONFIG: AppConfig = {
    emby: {
        serverUrl: "",
        apiKey: "",
        refreshAfterOrganize: false,
        notifications: {
            forwardToTelegram: false,
            playbackReportingFreq: "daily"
        },
        missingEpisodes: {
            cronSchedule: "0 0 * * *"
        }
    }
    // 其他必填字段会由 api.getConfig() 提供
} as any;

export const EmbyView: React.FC = () => {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isScanning, setIsScanning] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  
  // 连接状态
  const [connectionStatus, setConnectionStatus] = useState<{
    success: boolean | null;
    latency: number;
    msg?: string;
  }>({ success: null, latency: 0 });

  const [missingData, setMissingData] = useState<any[]>([]);

  // 加载配置
  useEffect(() => {
      const initConfig = async () => {
          try {
              const data = await api.getConfig();
              if (data?.emby) {
                  setConfig(data);
                  // 如果获取到了配置，顺便测试一下连接
                  if (data.emby.serverUrl && data.emby.apiKey) {
                      checkConnection(data);
                  }
              } else {
                  setConfig(DEFAULT_CONFIG);
              }
          } catch (err) {
              console.error("加载配置失败:", err);
              setConfig(DEFAULT_CONFIG);
              setToast('连接后端失败，已加载默认配置');
              setTimeout(() => setToast(null), 3000);
          }
      };

      initConfig();
  }, []);

  // 测试 Emby 连接
  const checkConnection = async (cfg: AppConfig = config!) => {
      if(!cfg?.emby?.serverUrl) return;
      try {
          // 先保存当前配置
          await api.saveConfig(cfg);
          
          const result = await api.testEmbyConnection();
          setConnectionStatus({
              success: result.data.success,
              latency: result.data.latency,
              msg: result.data.msg
          });
      } catch (e) {
          setConnectionStatus({ success: false, latency: 0, msg: "网络错误" });
      }
  };

  // 保存配置
  const handleSave = async () => {
    if (!config) return;
    setIsSaving(true);
    try {
        await api.saveConfig(config);
        setToast('配置已保存');
        checkConnection(); // 保存后重新测试连接
        setTimeout(() => setToast(null), 3000);
    } catch (e) {
        setToast('保存失败');
    } finally {
        setIsSaving(false);
    }
  };

  // 扫描缺集
  const handleScan = async () => {
      setIsScanning(true);
      try {
          const result = await api.scanEmbyMissing();
          setMissingData(result.data || []);
          setToast('扫描完成');
      } catch (e) {
          setToast('扫描失败');
      } finally {
          setIsScanning(false);
          setTimeout(() => setToast(null), 2000);
      }
  };

  // 辅助更新函数
  const updateNested = (section: keyof AppConfig, key: string, value: any) => {
    if(!config) return;
    setConfig(prev => prev ? ({
      ...prev,
      [section]: { ...(prev[section] as any), [key]: value }
    }) : null);
  };

  const updateNotifications = (key: string, value: any) => {
    if(!config) return;
    setConfig(prev => prev ? ({
        ...prev,
        emby: {
            ...prev.emby,
            notifications: { ...prev.emby.notifications, [key]: value }
        }
    }) : null);
  };

  const updateMissing = (key: string, value: any) => {
    if(!config) return;
     setConfig(prev => prev ? ({
      ...prev,
      emby: {
          ...prev.emby,
          missingEpisodes: { ...prev.emby.missingEpisodes, [key]: value }
      }
     }) : null);
  };

  const fillLocalIp = () => {
      updateNested('emby', 'serverUrl', `http://${window.location.hostname}:8096`);
  };

  const copyWebhook = () => {
      navigator.clipboard.writeText(`http://${window.location.hostname}:18080/api/webhook/115bot`);
      setToast('Webhook 地址已复制');
      setTimeout(() => setToast(null), 2000);
  };

  // === Loading 状态判断 ===
  // 只有当 config 真的是 null 时才显示 Loading
  // 现在因为有了 catch -> setConfig(DEFAULT)，除非 JS 报错，否则几乎不会一直卡在这里
  if (!config) return <div className="p-10 flex justify-center text-slate-500"><RefreshCw className="animate-spin"/></div>;

  const glassCardClass = "bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border-[0.5px] border-white/40 dark:border-white/10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.2)] ring-1 ring-white/50 dark:ring-white/5 inset";
  const inputClass = "w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-green-500 outline-none text-sm font-mono backdrop-blur-sm shadow-inner";
  const actionBtnClass = "px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-colors";

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
      {toast && (
        <div className="fixed top-6 right-6 bg-slate-800/90 backdrop-blur-md text-white px-6 py-3 rounded-xl shadow-2xl z-50 flex items-center gap-3 font-medium border-[0.5px] border-slate-700/50">
          <CheckCircle2 size={18} className="text-green-400" />
          {toast}
        </div>
      )}

      <div className="flex flex-col md:flex-row justify-between items-center pb-2 gap-4">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight drop-shadow-sm">Emby 联动</h2>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        
        {/* Server Connection */}
        <section className={`${glassCardClass} overflow-hidden h-fit`}>
           <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                 <div className="p-2 bg-green-50 dark:bg-green-900/20 rounded-lg text-green-600 dark:text-green-400 shadow-inner">
                    <Clapperboard size={20} />
                 </div>
                 <h3 className="font-bold text-slate-700 dark:text-slate-200">服务器连接</h3>
              </div>
              
               <div className="flex items-center gap-3">
                  {/* 连接状态指示器 */}
                  <div className={`flex items-center gap-2 px-3 py-1 rounded-full border-[0.5px] ${
                      connectionStatus.success === true ? 'bg-green-50/50 border-green-200 dark:bg-green-900/10 dark:border-green-800' :
                      connectionStatus.success === false ? 'bg-red-50/50 border-red-200 dark:bg-red-900/10 dark:border-red-800' :
                      'bg-slate-100/50 border-slate-200 dark:bg-slate-800/50 dark:border-slate-700'
                  }`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${
                            connectionStatus.success === true ? 'bg-green-500 animate-pulse' : 
                            connectionStatus.success === false ? 'bg-red-500' : 'bg-slate-400'
                        }`}></div>
                        <span className="text-[10px] font-mono font-medium text-slate-500 dark:text-slate-400">
                            {connectionStatus.success === null ? '未连接' : 
                             connectionStatus.success ? `${connectionStatus.latency}ms` : 'Error'}
                        </span>
                  </div>

                   <button
                      onClick={handleSave}
                      disabled={isSaving}
                      className={`${actionBtnClass} bg-green-50 text-green-600 hover:bg-green-100 dark:bg-green-900/20 dark:text-green-400 dark:hover:bg-green-900/40 disabled:opacity-50`}
                   >
                      {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                      保存
                   </button>
              </div>
           </div>
           
           <div className="p-6 space-y-5 transition-all duration-300">
               <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="block text-xs font-bold text-slate-500 uppercase">服务器地址</label>
                    <button onClick={fillLocalIp} className="text-xs text-brand-600 hover:text-brand-500 flex items-center gap-1 font-medium"><Zap size={12} /> 自动填入</button>
                  </div>
                  <input
                    type="text"
                    value={config.emby.serverUrl}
                    onChange={(e) => updateNested('emby', 'serverUrl', e.target.value)}
                    placeholder="http://192.168.1.5:8096"
                    className={inputClass}
                    onBlur={() => checkConnection()} // 失去焦点时测试连接
                  />
               </div>
               <div>
                  <label className="block text-xs font-bold text-slate-500 uppercase mb-2">API 密钥 (API Key)</label>
                  <SensitiveInput
                    value={config.emby.apiKey}
                    onChange={(e) => updateNested('emby', 'apiKey', e.target.value)}
                    className={inputClass}
                  />
               </div>
               
               <div className="flex items-center gap-2 pt-2">
                  <input 
                    type="checkbox" 
                    id="refreshAfterOrganize"
                    checked={config.emby.refreshAfterOrganize}
                    onChange={(e) => updateNested('emby', 'refreshAfterOrganize', e.target.checked)}
                    className="w-4 h-4 rounded text-green-600 focus:ring-green-500"
                  />
                  <label htmlFor="refreshAfterOrganize" className="text-sm font-medium text-slate-700 dark:text-slate-300 cursor-pointer select-none">整理完成后延迟 3 秒刷新海报墙</label>
               </div>
           </div>
        </section>

        {/* Notifications & Reporting */}
        <section className={`${glassCardClass} overflow-hidden h-fit`}>
           <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                 <div className="p-2 bg-sky-50 dark:bg-sky-900/20 rounded-lg text-sky-600 dark:text-sky-400 shadow-inner">
                    <Bell size={20} />
                 </div>
                 <h3 className="font-bold text-slate-700 dark:text-slate-200">通知与报告</h3>
              </div>
              <div className="flex items-center gap-3">
                  <button
                      onClick={handleSave}
                      disabled={isSaving}
                      className={`${actionBtnClass} bg-sky-50 text-sky-600 hover:bg-sky-100 dark:bg-sky-900/20 dark:text-sky-400 dark:hover:bg-sky-900/40 disabled:opacity-50`}
                  >
                      {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                      保存
                  </button>
              </div>
           </div>
           
           <div className="p-6 space-y-6 transition-all duration-300">
               <div className="bg-slate-50/50 dark:bg-slate-900/30 p-4 rounded-xl border-[0.5px] border-slate-200/50 dark:border-slate-700/50 backdrop-blur-sm">
                   <div className="flex justify-between items-center mb-2">
                       <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1"><Zap size={12}/> Webhook 回调地址</label>
                       <button onClick={copyWebhook} className="text-xs text-sky-600 hover:text-sky-500 flex items-center gap-1 font-bold"><Copy size={12} /> 复制</button>
                   </div>
                   <code className="block w-full px-3 py-2 bg-white/50 dark:bg-slate-900/50 rounded-lg text-xs font-mono text-slate-600 dark:text-slate-400 break-all border-[0.5px] border-slate-200/50 dark:border-slate-800/50 select-all shadow-inner">
                       http://{window.location.hostname}:18080/api/webhook/115bot
                   </code>
               </div>

               <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 rounded-lg hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition-colors border-[0.5px] border-transparent hover:border-slate-200/50 dark:hover:border-slate-700/30">
                     <span className="text-sm font-medium text-slate-700 dark:text-slate-200">转发 Emby 通知 (附带海报)</span>
                     <div className="relative inline-block w-9 h-5 transition duration-200 ease-in-out rounded-full cursor-pointer">
                        <input 
                            id="fwdTg" 
                            type="checkbox" 
                            className="peer sr-only"
                            checked={config.emby.notifications?.forwardToTelegram || false}
                            onChange={(e) => updateNotifications('forwardToTelegram', e.target.checked)}
                        />
                        <label htmlFor="fwdTg" className="block h-5 overflow-hidden bg-slate-200 dark:bg-slate-700 rounded-full cursor-pointer peer-checked:bg-sky-600 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white dark:after:bg-white after:w-4 after:h-4 after:rounded-full after:shadow-sm after:transition-all peer-checked:after:translate-x-full"></label>
                    </div>
                  </div>

                  <div className="space-y-3 pt-2 border-t border-slate-100 dark:border-slate-800">
                      <div className="flex justify-between items-center">
                          <label className="text-sm font-medium text-slate-700 dark:text-slate-200 flex items-center gap-2">
                             <BarChart3 size={16} className="text-sky-500" />
                             观影报告推送频率
                          </label>
                          <select 
                            value={config.emby.notifications?.playbackReportingFreq || 'daily'}
                            onChange={(e) => updateNotifications('playbackReportingFreq', e.target.value)}
                            className="px-3 py-1.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-slate-800 dark:text-slate-100 text-xs font-bold backdrop-blur-sm"
                          >
                             <option value="daily">每天 (Daily)</option>
                             <option value="weekly">每周 (Weekly)</option>
                             <option value="monthly">每月 (Monthly)</option>
                          </select>
                      </div>
                  </div>
               </div>
           </div>
        </section>

        {/* Missing Episodes Dashboard */}
        <section className={`${glassCardClass} overflow-hidden xl:col-span-2`}>
           <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                 <div className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded-lg text-purple-600 dark:text-purple-400 shadow-inner">
                    <FileWarning size={20} />
                 </div>
                 <h3 className="font-bold text-slate-700 dark:text-slate-200">电视剧缺集检测</h3>
              </div>
               <div className="flex items-center gap-3">
                   <button
                      onClick={handleSave}
                      disabled={isSaving}
                      className={`${actionBtnClass} bg-purple-50 text-purple-600 hover:bg-purple-100 dark:bg-purple-900/20 dark:text-purple-400 dark:hover:bg-purple-900/40 disabled:opacity-50`}
                   >
                      {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                      保存设置
                   </button>
               </div>
           </div>
           
           <div className="p-6 transition-all duration-300">
               <div className="flex flex-col gap-6">
                   <div className="flex items-end gap-4">
                       <div className="flex-1">
                          <label className="block text-xs font-bold text-slate-500 uppercase mb-2 flex items-center gap-1"><Clock size={12}/> 检测计划 (Cron 表达式)</label>
                          <input 
                            type="text"
                            value={config.emby.missingEpisodes?.cronSchedule || "0 0 * * *"}
                            onChange={(e) => updateMissing('cronSchedule', e.target.value)}
                            placeholder="0 0 * * *"
                            className={inputClass + " font-mono"}
                          />
                       </div>
                       <div className="flex-1">
                          <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed pt-6">定期扫描 Emby 库中的电视剧，比对 TMDB 数据检测缺失的剧集。</p>
                       </div>
                   </div>

                   {/* Dashboard Table */}
                   <div className="bg-slate-50/50 dark:bg-slate-900/30 rounded-xl border-[0.5px] border-slate-200/50 dark:border-slate-700/50 overflow-hidden">
                       <div className="px-4 py-2 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center bg-slate-100/30 dark:bg-slate-800/30">
                          <span className="text-xs font-bold text-slate-500 uppercase">检测结果预览</span>
                          <button 
                            onClick={handleScan}
                            disabled={isScanning}
                            className="text-xs text-purple-600 hover:text-purple-500 font-bold flex items-center gap-1 disabled:opacity-50"
                          >
                             {isScanning ? <RefreshCw className="animate-spin" size={12}/> : <Search size={12}/>} 
                             {isScanning ? "扫描中..." : "立即检测"}
                          </button>
                       </div>
                       
                       <div className="overflow-x-auto">
                           {missingData.length === 0 && !isScanning && (
                               <div className="p-8 text-center text-slate-400 text-xs">
                                   暂无数据，请点击右上角“立即检测”
                               </div>
                           )}

                           {missingData.length > 0 && (
                               <table className="w-full text-left text-xs">
                                   <thead className="text-slate-500 dark:text-slate-400 bg-white/20 dark:bg-white/5 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50">
                                       <tr>
                                           <th className="p-3 font-medium">封面</th>
                                           <th className="p-3 font-medium">剧集名称</th>
                                           <th className="p-3 font-medium">季</th>
                                           <th className="p-3 font-medium text-center">总集数</th>
                                           <th className="p-3 font-medium text-center">现有</th>
                                           <th className="p-3 font-medium text-red-500">缺失集数</th>
                                       </tr>
                                   </thead>
                                   <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                       {missingData.map((item) => (
                                           <tr key={item.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors">
                                               <td className="p-3">
                                                   <div className="w-8 h-12 bg-slate-200 dark:bg-slate-700 rounded overflow-hidden shadow-sm">
                                                       {item.poster && <img src={item.poster} alt="poster" className="w-full h-full object-cover" />}
                                                   </div>
                                               </td>
                                               <td className="p-3 font-medium text-slate-700 dark:text-slate-200">{item.name}</td>
                                               <td className="p-3 text-slate-500">Season {item.season}</td>
                                               <td className="p-3 text-center text-slate-600 dark:text-slate-400">{item.totalEp}</td>
                                               <td className="p-3 text-center text-slate-600 dark:text-slate-400">{item.localEp}</td>
                                               <td className="p-3 text-red-500 font-mono font-bold">{item.missing}</td>
                                           </tr>
                                       ))}
                                   </tbody>
                               </table>
                           )}
                       </div>
                   </div>
               </div>
           </div>
        </section>

      </div>
    </div>
  );
};