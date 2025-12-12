import React, { useState, useEffect } from 'react';
import { AppConfig } from '../types';
import { api } from '../services/api'; 
import { Save, RefreshCw, KeyRound, User, Smartphone, HardDrive, Cloud, Globe, Film, Bot, CheckCircle2, AlertCircle, Zap, Download, MonitorDown, Shield } from 'lucide-react';
import { SensitiveInput } from '../components/SensitiveInput';

// [新增] 默认空配置 (看不见的兜底数据)
const DEFAULT_CONFIG: Partial<AppConfig> = {
    cloud115: { loginMethod: 'cookie', loginApp: 'web', cookies: '', userAgent: '', downloadPath: '', downloadDirName: '未连接', autoDeleteMsg: false, qps: 1.0 },
    cloud123: { enabled: false, clientId: '', clientSecret: '', downloadPath: '', downloadDirName: '未连接', qps: 1.0 },
    openList: { enabled: false, url: '', mountPath: '', username: '', password: '' },
    tmdb: { apiKey: '', language: 'zh-CN', includeAdult: false },
    telegram: { botToken: '', adminUserId: '', whitelistMode: true, notificationChannelId: '' },
    proxy: { enabled: false, type: 'http', host: '', port: '' },
    twoFactorSecret: ''
};

export const UserCenterView: React.FC = () => {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const [newPassword, setNewPassword] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [isPwSaving, setIsPwSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  
  // 2FA Setup State
  const [isSetup2FA, setIsSetup2FA] = useState(false);
  const [tempSecret, setTempSecret] = useState('');
  const [qrCodeUri, setQrCodeUri] = useState('');
  const [verifyCode, setVerifyCode] = useState('');
  const [setupError, setSetupError] = useState('');

  // PWA State
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isPwaInstalled, setIsPwaInstalled] = useState(false);

  useEffect(() => {
    fetchConfig();

    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsPwaInstalled(true);
    }

    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
  }, []);

  // [核心修复] 获取配置，失败则使用默认值
  const fetchConfig = async () => {
    setLoading(true);
    try {
      const data = await api.getConfig();
      if (data) {
          setConfig(data as AppConfig);
      } else {
          throw new Error("Empty data");
      }
    } catch (error) {
      console.warn("后端连接失败，加载默认界面");
      setConfig(DEFAULT_CONFIG as AppConfig);
      setToast('连接服务器失败，已显示默认界面'); 
    } finally {
      setLoading(false);
    }
  };

  const handlePwaInstall = () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then((choiceResult: any) => {
        if (choiceResult.outcome === 'accepted') {
          console.log('User accepted the PWA prompt');
        }
        setDeferredPrompt(null);
      });
    }
  };

  const updateNested = (section: keyof AppConfig, key: string, value: any) => {
    if (!config) return;
    setConfig(prev => prev ? ({
      ...prev,
      [section]: { ...(prev[section] as any), [key]: value }
    }) : null);
  };

  const handleSave = async () => {
    if (!config) return;
    setIsSaving(true);
    try {
        await api.saveConfig(config);
        setToast('配置已更新');
    } catch (e) {
        setToast('保存失败 (网络错误)');
    } finally {
        setIsSaving(false);
        setTimeout(() => setToast(null), 3000);
    }
  };

  const handlePasswordSave = async () => {
    if (!newPassword) return;
    setIsPwSaving(true);
    try {
        await api.updatePassword(newPassword);
        setNewPassword('');
        setToast('管理员密码已修改');
    } catch (e) {
        setToast('修改失败');
    } finally {
        setIsPwSaving(false);
        setTimeout(() => setToast(null), 3000);
    }
  };

  const fillLocalIp = () => {
      updateNested('proxy', 'host', window.location.hostname);
  };

  const start2FASetup = async () => {
      try {
          const data = await api.setup2FA();
          setTempSecret(data.secret);
          setQrCodeUri(data.qrCodeUri);
          setVerifyCode('');
          setSetupError('');
          setIsSetup2FA(true);
      } catch (e) {
          setToast("无法连接后端初始化 2FA");
      }
  };

  const cancel2FASetup = () => {
      setIsSetup2FA(false);
      setTempSecret('');
      setQrCodeUri('');
  };

  const confirm2FASetup = async () => {
      try {
          await api.verify2FA(verifyCode);
          setConfig(prev => prev ? ({ ...prev, twoFactorSecret: tempSecret }) : null);
          setIsSetup2FA(false);
          setToast('2FA 配置已更新');
          setTimeout(() => setToast(null), 3000);
      } catch (e) {
          setSetupError('验证码错误或失效');
      }
  };

  // [核心修复] 只要 loading 结束，无论 config 是否为空（其实有默认值了），都渲染界面
  if (loading) {
      return (
          <div className="flex h-screen items-center justify-center text-slate-500 gap-2 bg-slate-50 dark:bg-slate-900">
              <RefreshCw className="animate-spin" /> 正在加载配置...
          </div>
      );
  }
  
  if (!config) return null; // 理论上不会走到这

  // Service Status Definitions
  const services = [
    {
        name: '115 网盘',
        isConnected: !!config.cloud115?.cookies,
        icon: HardDrive,
        colorClass: 'text-orange-600 dark:text-orange-400',
        bgClass: 'bg-orange-50 dark:bg-orange-900/20'
    },
    {
        name: '123 云盘',
        isConnected: config.cloud123?.enabled && !!config.cloud123?.clientId,
        icon: Cloud,
        colorClass: 'text-blue-600 dark:text-blue-400',
        bgClass: 'bg-blue-50 dark:bg-blue-900/20'
    },
    {
        name: 'OpenList',
        isConnected: config.openList?.enabled && !!config.openList?.url,
        icon: Globe,
        colorClass: 'text-cyan-600 dark:text-cyan-400',
        bgClass: 'bg-cyan-50 dark:bg-cyan-900/20'
    },
    {
        name: 'TMDB',
        isConnected: !!config.tmdb?.apiKey,
        icon: Film,
        colorClass: 'text-pink-600 dark:text-pink-400',
        bgClass: 'bg-pink-50 dark:bg-pink-900/20'
    },
    {
        name: 'TG 机器人',
        isConnected: !!config.telegram?.botToken,
        icon: Bot,
        colorClass: 'text-sky-600 dark:text-sky-400',
        bgClass: 'bg-sky-50 dark:bg-sky-900/20'
    }
  ];

  const glassCardClass = "bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border-[0.5px] border-white/40 dark:border-white/10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.2)] ring-1 ring-white/50 dark:ring-white/5 inset";
  const inputClass = "w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-slate-500 outline-none transition-all placeholder:text-slate-400 text-sm backdrop-blur-sm shadow-inner";
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
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight drop-shadow-sm">用户中心</h2>
      </div>

      {/* Service Status Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {services.map((service) => (
            <div key={service.name} className={`${glassCardClass} p-4 flex flex-col items-center justify-center gap-3 relative overflow-hidden group hover:-translate-y-1 transition-all duration-300`}>
                <div className={`p-3 rounded-xl ${service.bgClass} ${service.colorClass} mb-1 shadow-inner border-[0.5px] border-black/5`}>
                    <service.icon size={24} strokeWidth={1.5} />
                </div>
                <div className="text-center">
                    <div className="text-sm font-bold text-slate-700 dark:text-slate-200">{service.name}</div>
                    <div className={`text-[10px] font-medium mt-1 flex items-center justify-center gap-1.5 ${service.isConnected ? 'text-green-600 dark:text-green-400' : 'text-slate-400'}`}>
                        {service.isConnected ? (
                            <>
                                <CheckCircle2 size={12} /> 已连接
                            </>
                        ) : (
                            <>
                                <AlertCircle size={12} /> 未配置
                            </>
                        )}
                    </div>
                </div>
                {service.isConnected && (
                    <div className="absolute top-3 right-3 w-2 h-2 bg-green-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
                )}
            </div>
        ))}

        {/* PWA Module */}
        <div 
           onClick={!isPwaInstalled && deferredPrompt ? handlePwaInstall : undefined}
           className={`${glassCardClass} p-4 flex flex-col items-center justify-center gap-3 relative overflow-hidden group hover:-translate-y-1 transition-all duration-300 ${!isPwaInstalled && deferredPrompt ? 'cursor-pointer hover:ring-2 hover:ring-indigo-500/50' : ''}`}
        >
            <div className={`p-3 rounded-xl mb-1 shadow-inner border-[0.5px] border-black/5 ${isPwaInstalled ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}`}>
                {isPwaInstalled ? <Smartphone size={24} strokeWidth={1.5} /> : <MonitorDown size={24} strokeWidth={1.5} />}
            </div>
            <div className="text-center">
                <div className="text-sm font-bold text-slate-700 dark:text-slate-200">PWA 应用</div>
                <div className={`text-[10px] font-medium mt-1 flex items-center justify-center gap-1.5 ${isPwaInstalled ? 'text-green-600 dark:text-green-400' : 'text-indigo-500'}`}>
                    {isPwaInstalled ? (
                        <>
                             <CheckCircle2 size={12} /> 已安装
                        </>
                    ) : deferredPrompt ? (
                        <>
                             <Download size={12} /> 点击安装
                        </>
                    ) : (
                        <span className="text-slate-400">不支持/已安装</span>
                    )}
                </div>
            </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Account Settings */}
        <section className={`${glassCardClass} flex flex-col`}>
           <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                 <User size={18} className="text-slate-400" />
                 <h3 className="font-bold text-slate-700 dark:text-slate-200">管理员账号</h3>
              </div>
              <button
                  onClick={handlePasswordSave}
                  disabled={!newPassword || isPwSaving}
                  className={`${actionBtnClass} bg-brand-50 text-brand-600 hover:bg-brand-100 dark:bg-brand-900/20 dark:text-brand-400 dark:hover:bg-brand-900/40 disabled:opacity-50`}
               >
                 {isPwSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                 保存设置
               </button>
           </div>
           <div className="p-6 space-y-5 flex-1">
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">用户名</label>
                <input
                  type="text"
                  value="admin"
                  disabled
                  className="w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-200 dark:border-slate-700/50 bg-slate-50/50 dark:bg-slate-800/50 text-slate-500 dark:text-slate-400 cursor-not-allowed text-sm backdrop-blur-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">
                  修改密码
                </label>
                <div className="relative">
                    <KeyRound className="absolute left-3.5 top-2.5 text-slate-400" size={16} />
                    <SensitiveInput
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="输入新密码"
                    className={inputClass + " pl-10"}
                    />
                </div>
              </div>
           </div>
        </section>

        {/* 2FA Settings */}
        <section className={`${glassCardClass} flex flex-col`}>
           <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center gap-3">
              <Smartphone size={18} className="text-slate-400" />
              <h3 className="font-bold text-slate-700 dark:text-slate-200">双重验证 (2FA)</h3>
           </div>
           
           {!isSetup2FA ? (
               <div className="p-6 flex-1 flex flex-col justify-between">
                   <div className="flex items-center gap-4 mb-6">
                        <div className={`p-3 rounded-full shadow-inner ${config?.twoFactorSecret ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400' : 'bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500'}`}>
                            <Shield size={24} />
                        </div>
                        <div>
                            <h4 className="font-bold text-slate-800 dark:text-white text-base">
                                {config?.twoFactorSecret ? '已启用保护' : '未启用保护'}
                            </h4>
                        </div>
                   </div>

                  <div className="mb-5">
                      <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">当前密钥 (Secret Key)</label>
                      <SensitiveInput
                          value={config?.twoFactorSecret || ''}
                          onChange={(e) => {}} 
                          className={inputClass + " font-mono"}
                       />
                  </div>

                  <button 
                    onClick={start2FASetup}
                    className="w-full py-2.5 bg-white/50 dark:bg-white/5 border-[0.5px] border-slate-300 dark:border-slate-600 text-slate-700 dark:text-slate-300 rounded-lg text-sm font-bold hover:border-brand-500 hover:text-brand-600 transition-colors shadow-sm"
                  >
                      {config?.twoFactorSecret ? '重置 / 配置验证' : '立即设置验证'}
                  </button>
               </div>
           ) : (
               <div className="p-6 flex-1">
                  <h4 className="font-bold text-slate-800 dark:text-white mb-4 text-sm">设置步骤</h4>
                  
                  <div className="bg-white/50 dark:bg-slate-900/50 p-4 rounded-xl border-[0.5px] border-slate-200 dark:border-slate-700/50 flex flex-col items-center mb-4">
                      <img 
                        src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(qrCodeUri)}`}
                        alt="2FA QR"
                        className="w-28 h-28 mb-4 rounded-lg mix-blend-multiply dark:mix-blend-normal opacity-90"
                      />
                      <div className="text-center w-full">
                          <code className="bg-slate-100/80 dark:bg-slate-800/80 px-3 py-1.5 rounded-lg text-xs font-mono text-slate-600 dark:text-slate-300 block break-all tracking-wider border-[0.5px] border-slate-300/30">
                              {tempSecret}
                          </code>
                      </div>
                  </div>

                  <div className="space-y-4">
                      <input 
                          type="text"
                          maxLength={6}
                          value={verifyCode}
                          onChange={(e) => setVerifyCode(e.target.value)}
                          placeholder="输入 6 位验证码"
                          className="w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-center font-mono text-lg tracking-[0.5em] focus:ring-2 focus:ring-brand-500 outline-none backdrop-blur-sm"
                      />
                      {setupError && <p className="text-xs text-red-500 text-center font-bold">{setupError}</p>}

                      <div className="flex gap-3">
                          <button 
                             onClick={cancel2FASetup}
                             className="flex-1 py-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800/50 rounded-lg text-xs font-medium transition-colors"
                          >
                             取消
                          </button>
                          <button 
                             onClick={confirm2FASetup}
                             className="flex-1 py-2 bg-brand-600/90 hover:bg-brand-600 backdrop-blur-sm border-[0.5px] border-white/20 text-white rounded-lg text-xs font-bold shadow-sm transition-all active:scale-95"
                          >
                             确认启用
                          </button>
                      </div>
                  </div>
               </div>
           )}
        </section>

        {/* Network Proxy */}
        <section className={`${glassCardClass} lg:col-span-2`}>
          <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
            <div className="flex items-center gap-3">
               <Zap size={18} className="text-slate-400" />
               <h3 className="font-bold text-slate-700 dark:text-slate-200">网络代理</h3>
            </div>
            
            <div className="flex items-center gap-4">
                {config?.proxy?.enabled && (
                    <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100/50 dark:bg-slate-700/30 border border-slate-200/50 dark:border-slate-600/50">
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
                        <span className="text-[10px] font-mono font-medium text-slate-500 dark:text-slate-400">128ms</span>
                    </div>
                )}
                <button
                    onClick={handleSave}
                    disabled={isSaving}
                    className={`${actionBtnClass} bg-brand-50 text-brand-600 hover:bg-brand-100 dark:bg-brand-900/20 dark:text-brand-400 dark:hover:bg-brand-900/40 disabled:opacity-50`}
                >
                    {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                    保存设置
                </button>
            </div>
          </div>
          
          <div className="p-6">
            <div className="space-y-6 transition-all duration-300">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                 <div className="md:col-span-1">
                    <label className="block text-xs font-bold text-slate-500 uppercase mb-2">类型 (Type)</label>
                    <select 
                      value={config?.proxy?.type || 'http'}
                      onChange={(e) => updateNested('proxy', 'type', e.target.value)}
                      className={inputClass}
                    >
                      <option value="http">HTTP</option>
                      <option value="socks5">SOCKS5</option>
                    </select>
                 </div>
                 <div className="md:col-span-2">
                    <div className="flex justify-between items-center mb-2">
                      <label className="block text-xs font-bold text-slate-500 uppercase">代理地址 (Host:Port)</label>
                      <button onClick={fillLocalIp} className="text-xs text-brand-600 hover:text-brand-500 flex items-center gap-1 font-medium"><Zap size={12} /> 自动填入</button>
                    </div>
                    <div className="flex gap-3">
                       <input
                        type="text"
                        value={config?.proxy?.host || ''}
                        onChange={(e) => updateNested('proxy', 'host', e.target.value)}
                        placeholder="192.168.1.5"
                        className={`${inputClass} flex-1 font-mono`}
                      />
                      <input
                        type="text"
                        value={config?.proxy?.port || ''}
                        onChange={(e) => updateNested('proxy', 'port', e.target.value)}
                        placeholder="7890"
                        className={`${inputClass} w-24 font-mono`}
                      />
                    </div>
                 </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};