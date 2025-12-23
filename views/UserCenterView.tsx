import React, { useState, useEffect } from 'react';
import { AppConfig } from '../types';
import { api } from '../services/api';
import { Save, RefreshCw, KeyRound, User, Smartphone, HardDrive, Cloud, Globe, Film, Bot, CheckCircle2, AlertCircle, Zap, Download, MonitorDown, Shield, Tv, X, Loader2 } from 'lucide-react';
import { SensitiveInput } from '../components/SensitiveInput';
import { Cloud115Login } from '../components/Cloud115Login';

// [新增] 默认空配置 (看不见的兜底数据)
const DEFAULT_CONFIG: Partial<AppConfig> = {
  cloud115: { loginMethod: 'cookie', loginApp: 'web', cookies: '', userAgent: '', downloadPath: '', downloadDirName: '未连接', autoDeleteMsg: false, qps: 1.0 },
  cloud123: { enabled: false, clientId: '', clientSecret: '', downloadPath: '', downloadDirName: '未连接', qps: 1.0 },

  tmdb: { apiKey: '', language: 'zh-CN', includeAdult: false },
  telegram: { botToken: '', adminUserId: '', whitelistMode: true, notificationChannelId: '' },
  proxy: { enabled: false, type: 'http', host: '', port: '', noProxyHosts: '115.com,123pan.com,123pan.cn' },
  twoFactorSecret: ''
};

// [新增] 代理测试相关 Helper
const getLatencyColor = (latency: number | null) => {
  if (latency === null) return 'text-slate-400 bg-slate-100 dark:bg-slate-800';
  if (latency < 200) return 'text-green-600 bg-green-50 dark:text-green-400 dark:bg-green-900/20 border-green-200/50 dark:border-green-800/50';
  if (latency < 500) return 'text-yellow-600 bg-yellow-50 dark:text-yellow-400 dark:bg-yellow-900/20 border-yellow-200/50 dark:border-yellow-800/50';
  return 'text-red-600 bg-red-50 dark:text-red-400 dark:bg-red-900/20 border-red-200/50 dark:border-red-800/50';
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

  // Proxy Latency State
  const [proxyLatency, setProxyLatency] = useState<number | null>(null);
  const [isTestingProxy, setIsTestingProxy] = useState(false);

  // Cloud Login Modal State
  const [show115Modal, setShow115Modal] = useState(false);
  const [show123Modal, setShow123Modal] = useState(false);
  const [is123Saving, setIs123Saving] = useState(false);
  const [showEmbyModal, setShowEmbyModal] = useState(false);
  const [showTmdbModal, setShowTmdbModal] = useState(false);
  const [showTgModal, setShowTgModal] = useState(false);
  const [showProxyModal, setShowProxyModal] = useState(false);
  const [isEmbyTesting, setIsEmbyTesting] = useState(false);
  const [isTgTesting, setIsTgTesting] = useState(false);



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
      // 静默处理，不显示错误提示
    } finally {
      setLoading(false);
    }
  };

  // [新增] 代理测试逻辑
  useEffect(() => {
    const timer = setTimeout(() => {
      if (config?.proxy?.enabled || (config?.proxy?.host && config?.proxy?.port)) {
        testProxyConnection();
      }
    }, 1000); // Debounce 1s
    return () => clearTimeout(timer);
  }, [config?.proxy?.host, config?.proxy?.port, config?.proxy?.type]);

  const testProxyConnection = async () => {
    if (!config?.proxy?.host || !config?.proxy?.port) {
      setProxyLatency(null);
      return;
    }

    setIsTestingProxy(true);
    try {
      const res = await api.testProxy({
        type: config.proxy.type,
        host: config.proxy.host,
        port: config.proxy.port,
        username: config.proxy.username,
        password: config.proxy.password
      });
      if (res.success) {
        setProxyLatency(res.data.latency);
      } else {
        setProxyLatency(9999); // Error
      }
    } catch (e) {
      setProxyLatency(9999);
    } finally {
      setIsTestingProxy(false);
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
      isConnected: !!config.cloud115?.hasValidSession || !!config.cloud115?.cookies,
      icon: HardDrive,
      colorClass: 'text-orange-600 dark:text-orange-400',
      bgClass: 'bg-orange-50 dark:bg-orange-900/20',
      onClick: () => setShow115Modal(true)
    },
    {
      name: '123 云盘',
      isConnected: !!(config.cloud123?.clientId && config.cloud123?.clientSecret) || !!config.cloud123?.hasValidSession,
      icon: Cloud,
      colorClass: 'text-blue-600 dark:text-blue-400',
      bgClass: 'bg-blue-50 dark:bg-blue-900/20',
      onClick: () => setShow123Modal(true)
    },

    {
      name: 'TMDB',
      isConnected: !!config.tmdb?.apiKey,
      icon: Film,
      colorClass: 'text-pink-600 dark:text-pink-400',
      bgClass: 'bg-pink-50 dark:bg-pink-900/20',
      onClick: () => setShowTmdbModal(true)
    },
    {
      name: 'TG 机器人',
      isConnected: !!config.telegram?.botToken,
      icon: Bot,
      colorClass: 'text-sky-600 dark:text-sky-400',
      bgClass: 'bg-sky-50 dark:bg-sky-900/20',
      onClick: () => setShowTgModal(true)
    },
    {
      name: 'Emby',
      isConnected: !!config.emby?.serverUrl && !!config.emby?.apiKey,
      icon: Tv,
      colorClass: 'text-emerald-600 dark:text-emerald-400',
      bgClass: 'bg-emerald-50 dark:bg-emerald-900/20',
      onClick: () => setShowEmbyModal(true)
    },
    {
      name: '网络代理',
      isConnected: !!config.proxy?.enabled && !!config.proxy?.host,
      icon: Globe,
      colorClass: 'text-purple-600 dark:text-purple-400',
      bgClass: 'bg-purple-50 dark:bg-purple-900/20',
      onClick: () => setShowProxyModal(true)
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
          <button
            key={service.name}
            onClick={service.onClick}
            className={`${glassCardClass} p-4 flex flex-col items-center justify-center gap-3 relative overflow-hidden group hover:-translate-y-1 transition-all duration-300 ${!!service.onClick ? 'cursor-pointer hover:ring-2 hover:ring-brand-500/50' : ''}`}
          >
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
          </button>
        ))}


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
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">当前密钥</label>
                <SensitiveInput
                  value={config?.twoFactorSecret || ''}
                  onChange={() => { }}
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




        {/* WebDAV Server */}
        <section className={`${glassCardClass} lg:col-span-2`}>
          <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-teal-50 dark:bg-teal-900/20 rounded-lg text-teal-600 dark:text-teal-400 shadow-inner">
                <Globe size={20} />
              </div>
              <h3 className="font-bold text-slate-700 dark:text-slate-200">WebDAV 服务</h3>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={handleSave}
                disabled={isSaving}
                className={`${actionBtnClass} bg-teal-50 text-teal-600 hover:bg-teal-100 dark:bg-teal-900/20 dark:text-teal-400 dark:hover:bg-teal-900/40 disabled:opacity-50`}
              >
                {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                保存设置
              </button>
            </div>
          </div>

          <div className="p-6 transition-all duration-300">
            <div className="bg-teal-50/50 dark:bg-teal-900/10 p-3 rounded-xl border-[0.5px] border-teal-100/50 dark:border-teal-900/30 text-sm text-teal-700 dark:text-teal-400 mb-6 flex items-center gap-3 backdrop-blur-sm shadow-inner">
              <HardDrive size={18} />
              <span>
                WebDAV 挂载地址: <strong>http://{window.location.hostname}:18080/dav</strong>
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase mb-2">用户名</label>
                <input
                  type="text"
                  value={config?.strm?.webdav?.username || 'admin'}
                  onChange={(e) => {
                    if (!config) return;
                    setConfig(prev => prev ? ({
                      ...prev,
                      strm: {
                        ...prev.strm,
                        webdav: { ...prev.strm?.webdav, username: e.target.value }
                      }
                    }) : null);
                  }}
                  className={inputClass}
                />
              </div>
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase mb-2">密码</label>
                <SensitiveInput
                  value={config?.strm?.webdav?.password || ''}
                  onChange={(e) => {
                    if (!config) return;
                    setConfig(prev => prev ? ({
                      ...prev,
                      strm: {
                        ...prev.strm,
                        webdav: { ...prev.strm?.webdav, password: e.target.value }
                      }
                    }) : null);
                  }}
                  className={inputClass}
                />
              </div>
              <div className="flex items-end pb-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={config?.strm?.webdav?.readOnly || false}
                    onChange={(e) => {
                      if (!config) return;
                      setConfig(prev => prev ? ({
                        ...prev,
                        strm: {
                          ...prev.strm,
                          webdav: { ...prev.strm?.webdav, readOnly: e.target.checked }
                        }
                      }) : null);
                    }}
                    className="w-4 h-4 rounded text-teal-600 focus:ring-teal-500"
                  />
                  <span className="text-sm font-medium text-slate-700 dark:text-slate-300">只读模式</span>
                </label>
              </div>
            </div>
          </div>
        </section>
      </div>




      {/* PWA Module - Bottom */}
      {(deferredPrompt || isPwaInstalled) && (
        <section className={`${glassCardClass} flex flex-col md:flex-row items-center justify-between p-6 gap-6 animate-in fade-in slide-in-from-bottom-8 duration-500`}>
          <div className="flex items-center gap-4">
            <div className={`p-4 rounded-2xl shadow-inner border-[0.5px] border-black/5 ${isPwaInstalled ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400' : 'bg-slate-100 dark:bg-slate-800 text-slate-500'}`}>
              {isPwaInstalled ? <Smartphone size={32} strokeWidth={1.5} /> : <MonitorDown size={32} strokeWidth={1.5} />}
            </div>
            <div>
              <h3 className="font-bold text-lg text-slate-800 dark:text-white flex items-center gap-2">
                PWA 渐进式应用
                {isPwaInstalled && <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-[10px] font-bold border border-green-200">已安装</span>}
              </h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                {isPwaInstalled
                  ? '应用已安装到您的设备，支持离线访问和更原生的体验'
                  : '安装应用到您的设备，获得如原生应用般的流畅体验'}
              </p>
            </div>
          </div>

          <div>
            {!isPwaInstalled && deferredPrompt ? (
              <button
                onClick={handlePwaInstall}
                className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-bold shadow-lg shadow-indigo-500/20 transition-all active:scale-95 flex items-center gap-2"
              >
                <Download size={18} />
                立即安装
              </button>
            ) : isPwaInstalled ? (
              <button disabled className="px-6 py-2.5 bg-slate-100 dark:bg-slate-800 text-slate-400 rounded-xl font-bold border-[0.5px] border-slate-200 dark:border-slate-700 cursor-default flex items-center gap-2">
                <CheckCircle2 size={18} />
                运行正常
              </button>
            ) : (
              <span className="text-xs text-slate-400 font-mono bg-slate-100 dark:bg-slate-800 px-3 py-1.5 rounded-lg border-[0.5px] border-slate-200 dark:border-slate-700">
                当前浏览器不支持或已禁用
              </span>
            )}
          </div>
        </section>
      )}

      {/* 115 Login Modal */}
      {show115Modal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShow115Modal(false)}>
          <div className={`${glassCardClass} w-full max-w-lg max-h-[90vh] overflow-y-auto`} onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-orange-50 dark:bg-orange-900/20 rounded-lg text-orange-600 dark:text-orange-400">
                  <HardDrive size={20} />
                </div>
                <h3 className="font-bold text-slate-700 dark:text-slate-200">115 网盘登录</h3>
              </div>
              <button onClick={() => setShow115Modal(false)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors">
                <X size={18} />
              </button>
            </div>
            <div className="p-6">
              <Cloud115Login
                loginMethod={config.cloud115.loginMethod as 'cookie' | 'qrcode' | 'open_app'}
                onLoginMethodChange={(method) => updateNested('cloud115', 'loginMethod', method)}
                selectedApp={config.cloud115.loginApp || 'android'}
                onAppChange={(app) => updateNested('cloud115', 'loginApp', app)}
                appId={config.cloud115.appId || ''}
                onAppIdChange={(id) => updateNested('cloud115', 'appId', id)}
                cookies={config.cloud115.cookies || ''}
                onCookiesChange={(cookies) => updateNested('cloud115', 'cookies', cookies)}
                onLoginSuccess={() => {
                  fetchConfig();
                  setShow115Modal(false);
                  setToast('115 网盘登录成功');
                  setTimeout(() => setToast(null), 3000);
                }}
                onToast={(msg) => {
                  setToast(msg);
                  setTimeout(() => setToast(null), 3000);
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* 123 Login Modal */}
      {show123Modal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShow123Modal(false)}>
          <div className={`${glassCardClass} w-full max-w-lg max-h-[90vh] overflow-y-auto`} onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg text-blue-600 dark:text-blue-400">
                  <Cloud size={20} />
                </div>
                <h3 className="font-bold text-slate-700 dark:text-slate-200">123 云盘登录</h3>
              </div>
              <button onClick={() => setShow123Modal(false)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors">
                <X size={18} />
              </button>
            </div>
            <div className="p-6 space-y-6">
              {/* 登录方式切换 */}
              <div className="flex gap-2">
                <button
                  onClick={() => updateNested('cloud123', 'loginMethod', 'password')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all shadow-sm ${config.cloud123.loginMethod === 'password' ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-500'}`}
                >
                  密码登录
                </button>
                <button
                  onClick={() => updateNested('cloud123', 'loginMethod', 'oauth')}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all shadow-sm ${config.cloud123.loginMethod !== 'password' ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-700 text-slate-500'}`}
                >
                  开放平台凭据
                </button>
              </div>

              {/* 密码登录 */}
              {config.cloud123.loginMethod === 'password' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">手机号</label>
                    <SensitiveInput
                      value={config.cloud123.passport || ''}
                      onChange={(e) => updateNested('cloud123', 'passport', e.target.value)}
                      placeholder="请输入手机号或邮箱"
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">密码</label>
                    <SensitiveInput
                      value={config.cloud123.password || ''}
                      onChange={(e) => updateNested('cloud123', 'password', e.target.value)}
                      placeholder="请输入密码"
                      className={inputClass}
                    />
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        setIs123Saving(true);
                        const result = await api.login123WithPassword(
                          config.cloud123.passport || '',
                          config.cloud123.password || ''
                        );
                        if (result.success) {
                          fetchConfig();
                          setShow123Modal(false);
                          setToast('123 云盘登录成功');
                        } else {
                          setToast(result.error || '登录失败');
                        }
                      } catch (err: any) {
                        setToast(err.response?.data?.error || '登录失败');
                      } finally {
                        setIs123Saving(false);
                        setTimeout(() => setToast(null), 3000);
                      }
                    }}
                    disabled={is123Saving || !config.cloud123.passport || !config.cloud123.password}
                    className="w-full px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-bold flex items-center justify-center gap-2 hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {is123Saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                    密码登录
                  </button>
                </div>
              )}

              {/* OAuth 登录 */}
              {config.cloud123.loginMethod !== 'password' && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">客户端 ID (Client ID)</label>
                    <SensitiveInput
                      value={config.cloud123.clientId}
                      onChange={(e) => updateNested('cloud123', 'clientId', e.target.value)}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">客户端密钥 (Client Secret)</label>
                    <SensitiveInput
                      value={config.cloud123.clientSecret}
                      onChange={(e) => updateNested('cloud123', 'clientSecret', e.target.value)}
                      className={inputClass}
                    />
                  </div>
                  <button
                    onClick={async () => {
                      setIs123Saving(true);
                      try {
                        await api.saveConfig(config);
                        fetchConfig();
                        setShow123Modal(false);
                        setToast('123 云盘凭据已保存');
                      } catch (e) {
                        setToast('保存失败');
                      } finally {
                        setIs123Saving(false);
                        setTimeout(() => setToast(null), 3000);
                      }
                    }}
                    disabled={is123Saving || !config.cloud123.clientId || !config.cloud123.clientSecret}
                    className="w-full px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-bold flex items-center justify-center gap-2 hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {is123Saving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                    保存凭据
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Emby Modal */}
      {showEmbyModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowEmbyModal(false)}>
          <div className={`${glassCardClass} w-full max-w-lg`} onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg text-emerald-600 dark:text-emerald-400">
                  <Tv size={20} />
                </div>
                <h3 className="font-bold text-slate-700 dark:text-slate-200">Emby 服务器配置</h3>
              </div>
              <button onClick={() => setShowEmbyModal(false)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors">
                <X size={18} />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">服务器地址</label>
                <input
                  type="text"
                  value={config.emby?.serverUrl || ''}
                  onChange={(e) => updateNested('emby', 'serverUrl', e.target.value)}
                  placeholder="http://192.168.1.100:8096"
                  className={inputClass}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">API 密钥</label>
                <SensitiveInput
                  value={config.emby?.apiKey || ''}
                  onChange={(e) => updateNested('emby', 'apiKey', e.target.value)}
                  placeholder="请输入 Emby API Key"
                  className={inputClass}
                />
              </div>
              <button
                onClick={async () => {
                  setIsEmbyTesting(true);
                  try {
                    await api.saveConfig(config);
                    const result = await api.testEmbyConnection();
                    if (result.data?.success || result.success) {
                      fetchConfig();
                      setShowEmbyModal(false);
                      setToast('Emby 连接成功');
                    } else {
                      setToast(result.data?.msg || '连接失败');
                    }
                  } catch (e: any) {
                    setToast(e.response?.data?.error || '连接失败');
                  } finally {
                    setIsEmbyTesting(false);
                    setTimeout(() => setToast(null), 3000);
                  }
                }}
                disabled={isEmbyTesting || !config.emby?.serverUrl || !config.emby?.apiKey}
                className="w-full px-5 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-bold flex items-center justify-center gap-2 hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isEmbyTesting ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                保存并测试连接
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TMDB Modal */}
      {showTmdbModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowTmdbModal(false)}>
          <div className={`${glassCardClass} w-full max-w-lg`} onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-pink-50 dark:bg-pink-900/20 rounded-lg text-pink-600 dark:text-pink-400">
                  <Film size={20} />
                </div>
                <h3 className="font-bold text-slate-700 dark:text-slate-200">TMDB API 配置</h3>
              </div>
              <button onClick={() => setShowTmdbModal(false)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors">
                <X size={18} />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">API 密钥</label>
                <SensitiveInput
                  value={config.tmdb?.apiKey || ''}
                  onChange={(e) => updateNested('tmdb', 'apiKey', e.target.value)}
                  placeholder="请输入 TMDB API Key"
                  className={inputClass}
                />
                <p className="text-xs text-slate-400 mt-2">
                  💡 前往 <a href="https://www.themoviedb.org/settings/api" target="_blank" rel="noopener noreferrer" className="text-pink-500 hover:underline">TMDB 官网</a> 获取 API 密钥
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">语言设置</label>
                <select
                  value={config.tmdb?.language || 'zh-CN'}
                  onChange={(e) => updateNested('tmdb', 'language', e.target.value)}
                  className={`${inputClass} cursor-pointer`}
                >
                  <option value="zh-CN">简体中文</option>
                  <option value="zh-TW">繁体中文</option>
                  <option value="en-US">English</option>
                  <option value="ja-JP">日本語</option>
                  <option value="ko-KR">한국어</option>
                </select>
              </div>
              <button
                onClick={async () => {
                  try {
                    await api.saveConfig(config);
                    fetchConfig();
                    setShowTmdbModal(false);
                    setToast('TMDB 配置已保存');
                  } catch (e) {
                    setToast('保存失败');
                  }
                  setTimeout(() => setToast(null), 3000);
                }}
                disabled={!config.tmdb?.apiKey}
                className="w-full px-5 py-2.5 bg-pink-600 text-white rounded-lg text-sm font-bold flex items-center justify-center gap-2 hover:bg-pink-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Save size={16} />
                保存配置
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TG Bot Modal */}
      {showTgModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowTgModal(false)}>
          <div className={`${glassCardClass} w-full max-w-lg max-h-[90vh] overflow-y-auto`} onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-sky-50 dark:bg-sky-900/20 rounded-lg text-sky-600 dark:text-sky-400">
                  <Bot size={20} />
                </div>
                <h3 className="font-bold text-slate-700 dark:text-slate-200">Telegram 机器人配置</h3>
              </div>
              <button onClick={() => setShowTgModal(false)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors">
                <X size={18} />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">Bot Token</label>
                <SensitiveInput
                  value={config.telegram?.botToken || ''}
                  onChange={(e) => updateNested('telegram', 'botToken', e.target.value)}
                  placeholder="123456789:ABCdefGHI..."
                  className={inputClass}
                />
                <p className="text-xs text-slate-400 mt-1">从 @BotFather 获取</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">管理员用户 ID</label>
                <input
                  type="text"
                  value={config.telegram?.adminUserId || ''}
                  onChange={(e) => updateNested('telegram', 'adminUserId', e.target.value)}
                  placeholder="123456789"
                  className={inputClass}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">通知频道 ID (可选)</label>
                <input
                  type="text"
                  value={config.telegram?.notificationChannelId || ''}
                  onChange={(e) => updateNested('telegram', 'notificationChannelId', e.target.value)}
                  placeholder="-1001234567890"
                  className={inputClass}
                />
              </div>
              <div className="flex items-center justify-between py-2">
                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">白名单模式</label>
                <input
                  type="checkbox"
                  checked={config.telegram?.whitelistMode ?? true}
                  onChange={(e) => updateNested('telegram', 'whitelistMode', e.target.checked)}
                  className="w-5 h-5 rounded text-sky-600 focus:ring-sky-500 cursor-pointer"
                />
              </div>
              <button
                onClick={async () => {
                  setIsTgTesting(true);
                  try {
                    await api.saveConfig(config);
                    const result = await api.testBotMessage('admin');
                    if (result.success) {
                      fetchConfig();
                      setShowTgModal(false);
                      setToast('TG 机器人配置成功，测试消息已发送');
                    } else {
                      setToast(result.error || '配置失败');
                    }
                  } catch (e: any) {
                    setToast(e.response?.data?.error || '配置失败');
                  } finally {
                    setIsTgTesting(false);
                    setTimeout(() => setToast(null), 3000);
                  }
                }}
                disabled={isTgTesting || !config.telegram?.botToken || !config.telegram?.adminUserId}
                className="w-full px-5 py-2.5 bg-sky-600 text-white rounded-lg text-sm font-bold flex items-center justify-center gap-2 hover:bg-sky-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isTgTesting ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                保存并发送测试
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Proxy Modal */}
      {showProxyModal && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowProxyModal(false)}>
          <div className={`${glassCardClass} w-full max-w-lg`} onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded-lg text-purple-600 dark:text-purple-400">
                  <Globe size={20} />
                </div>
                <h3 className="font-bold text-slate-700 dark:text-slate-200">网络代理设置</h3>
              </div>
              <button onClick={() => setShowProxyModal(false)} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg transition-colors">
                <X size={18} />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-between py-2">
                <label className="text-sm font-medium text-slate-600 dark:text-slate-400">启用代理</label>
                <input
                  type="checkbox"
                  checked={config.proxy?.enabled ?? false}
                  onChange={(e) => updateNested('proxy', 'enabled', e.target.checked)}
                  className="w-5 h-5 rounded text-purple-600 focus:ring-purple-500 cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">代理类型</label>
                <select
                  value={config.proxy?.type || 'http'}
                  onChange={(e) => updateNested('proxy', 'type', e.target.value)}
                  className={`${inputClass} cursor-pointer`}
                >
                  <option value="http">HTTP</option>
                  <option value="https">HTTPS</option>
                  <option value="socks5">SOCKS5</option>
                </select>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2">
                  <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">代理地址</label>
                  <input
                    type="text"
                    value={config.proxy?.host || ''}
                    onChange={(e) => updateNested('proxy', 'host', e.target.value)}
                    placeholder="127.0.0.1"
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">端口</label>
                  <input
                    type="text"
                    value={config.proxy?.port || ''}
                    onChange={(e) => updateNested('proxy', 'port', e.target.value)}
                    placeholder="7890"
                    className={inputClass}
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">不代理域名 (逗号分隔)</label>
                <input
                  type="text"
                  value={config.proxy?.noProxyHosts || ''}
                  onChange={(e) => updateNested('proxy', 'noProxyHosts', e.target.value)}
                  placeholder="115.com,123pan.com"
                  className={inputClass}
                />
              </div>
              <button
                onClick={async () => {
                  try {
                    await api.saveConfig(config);
                    const result = await api.testProxy({
                      type: config.proxy?.type || 'http',
                      host: config.proxy?.host || '',
                      port: config.proxy?.port || ''
                    });
                    if (result.data?.latency) {
                      fetchConfig();
                      setShowProxyModal(false);
                      setToast(`代理连接成功，延迟 ${result.data.latency}ms`);
                    } else {
                      setToast('代理连接失败');
                    }
                  } catch (e: any) {
                    setToast(e.response?.data?.error || '代理测试失败');
                  }
                  setTimeout(() => setToast(null), 3000);
                }}
                disabled={!config.proxy?.host || !config.proxy?.port}
                className="w-full px-5 py-2.5 bg-purple-600 text-white rounded-lg text-sm font-bold flex items-center justify-center gap-2 hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Zap size={16} />
                保存并测试连接
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};