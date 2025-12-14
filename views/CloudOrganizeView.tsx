import React, { useState, useEffect, useRef } from 'react';
import { AppConfig, ClassificationRule, MatchConditionType } from '../types';
import { api } from '../services/api';
// 确保 mockConfig 存在，如果不存在请创建一个空文件或根据需求调整
import { DEFAULT_MOVIE_RULES, DEFAULT_TV_RULES } from '../services/mockConfig';
import { Save, RefreshCw, Cookie, QrCode, Smartphone, FolderInput, Gauge, Trash2, Plus, Film, Type, Globe, Cloud, Tv, LayoutList, GripVertical, AlertCircle, FolderOutput, Zap, RotateCcw, X, Edit, Check, BrainCircuit, Bot, Loader2 } from 'lucide-react';
import { SensitiveInput } from '../components/SensitiveInput';
import { FileSelector } from '../components/FileSelector';

const GENRES = [
   { id: '28', name: '动作 (Action)' }, { id: '12', name: '冒险 (Adventure)' }, { id: '16', name: '动画 (Animation)' },
   { id: '35', name: '喜剧 (Comedy)' }, { id: '80', name: '犯罪 (Crime)' }, { id: '99', name: '纪录 (Documentary)' },
   { id: '18', name: '剧情 (Drama)' }, { id: '10751', name: '家庭 (Family)' }, { id: '14', name: '奇幻 (Fantasy)' },
   { id: '36', name: '历史 (History)' }, { id: '27', name: '恐怖 (Horror)' }, { id: '10402', name: '音乐 (Music)' },
   { id: '9648', name: '悬疑 (Mystery)' }, { id: '10749', name: '爱情 (Romance)' }, { id: '878', name: '科幻 (Sci-Fi)' },
   { id: '10770', name: '电视电影 (TV Movie)' }, { id: '53', name: '惊悚 (Thriller)' }, { id: '10752', name: '战争 (War)' },
   { id: '37', name: '西部 (Western)' }, { id: '10762', name: '儿童 (Kids)' }, { id: '10764', name: '真人秀 (Reality)' },
   { id: '10767', name: '脱口秀 (Talk)' }
];

const LANGUAGES = [
   { id: 'zh,cn,bo,za', name: '中文 (Chinese)' }, { id: 'en', name: '英语 (English)' }, { id: 'ja', name: '日语 (Japanese)' },
   { id: 'ko', name: '韩语 (Korean)' }, { id: 'fr', name: '法语 (French)' }, { id: 'de', name: '德语 (German)' },
   { id: 'es', name: '西班牙语 (Spanish)' }, { id: 'ru', name: '俄语 (Russian)' }, { id: 'hi', name: '印地语 (Hindi)' }
];

const COUNTRIES = [
   { id: 'CN,TW,HK', name: '中国/港台 (CN/TW/HK)' }, { id: 'US', name: '美国 (USA)' }, { id: 'JP', name: '日本 (Japan)' },
   { id: 'KR', name: '韩国 (Korea)' }, { id: 'GB', name: '英国 (UK)' }, { id: 'FR', name: '法国 (France)' },
   { id: 'DE', name: '德国 (Germany)' }, { id: 'IN', name: '印度 (India)' }, { id: 'TH', name: '泰国 (Thailand)' }
];

const RENAME_TAGS = [
   { label: '标题', value: '{title}' }, { label: '年份', value: '{year}' }, { label: '季号(S)', value: '{season}' },
   { label: '集号(E)', value: '{episode}' }, { label: '分辨率', value: '{resolution}' }, { label: '制作组', value: '{group}' },
   { label: '原名', value: '{original_title}' }, { label: '来源', value: '{source}' }, { label: 'TMDB ID', value: '[TMDB-{id}]' },
];

// 默认配置
const DEFAULT_CONFIG: Partial<AppConfig> = {
   cloud115: { loginMethod: 'cookie', loginApp: 'web', cookies: '', userAgent: '', downloadPath: '', downloadDirName: '未连接', autoDeleteMsg: false, qps: 1.0 },
   cloud123: { enabled: false, clientId: '', clientSecret: '', downloadPath: '', downloadDirName: '未连接', qps: 1.0 },
   openList: { enabled: false, url: '', mountPath: '', username: '', password: '' },
   tmdb: { apiKey: '', language: 'zh-CN', includeAdult: false },
   organize: { enabled: true, sourceCid: '', sourceDirName: '', targetCid: '', targetDirName: '', ai: { enabled: false, provider: 'openai', baseUrl: '', apiKey: '', model: '' }, rename: { enabled: true, movieTemplate: '', seriesTemplate: '', addTmdbIdToFolder: true }, movieRules: DEFAULT_MOVIE_RULES, tvRules: DEFAULT_TV_RULES }
};

export const CloudOrganizeView: React.FC = () => {
   const [config, setConfig] = useState<AppConfig | null>(null);
   const [loading, setLoading] = useState(true);

   const [isSaving, setIsSaving] = useState(false);
   const [toast, setToast] = useState<string | null>(null);

   const [activeTab, setActiveTab] = useState<'115' | '123' | 'openlist'>('115');
   const [activeRuleTab, setActiveRuleTab] = useState<'movie' | 'tv'>('movie');
   const [fileSelectorOpen, setFileSelectorOpen] = useState(false);
   const [selectorTarget, setSelectorTarget] = useState<'download' | 'download123' | 'source' | 'target' | null>(null);

   const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
   const [tempRule, setTempRule] = useState<ClassificationRule | null>(null);

   const [qrState, setQrState] = useState<'idle' | 'loading' | 'waiting' | 'scanned' | 'success' | 'expired' | 'error'>('idle');
   const [qrImage, setQrImage] = useState<string>('');
   const [qrSessionId, setQrSessionId] = useState<string>('');
   const qrTimerRef = useRef<NodeJS.Timeout | null>(null);

   useEffect(() => {
      fetchConfig();
      return () => stopQrCheck();
   }, []);

   const fetchConfig = async () => {
      setLoading(true);
      try {
         const data = await api.getConfig();
         if (data) {
            setConfig(data as AppConfig);
         } else {
            throw new Error("Empty data");
         }
      } catch (e) {
         console.warn("加载配置失败，使用默认配置");
         setConfig(DEFAULT_CONFIG as AppConfig);
         // 静默处理，不显示错误提示
      } finally {
         setLoading(false);
      }
   };

   const handleSave = async () => {
      if (!config) return;
      setIsSaving(true);
      try {
         await api.saveConfig(config);
         setToast('配置已保存到服务器');
         setTimeout(() => setToast(null), 3000);
      } catch (e) {
         setToast('保存失败 (网络错误)');
      } finally {
         setIsSaving(false);
      }
   };

   // Helper Functions
   const updateNested = (section: keyof AppConfig, key: string, value: any) => {
      if (!config) return;
      setConfig(prev => prev ? ({
         ...prev,
         [section]: { ...(prev[section] as any), [key]: value }
      }) : null);
   };

   const updateRenameRule = (key: string, value: any) => {
      if (!config) return;
      setConfig(prev => prev ? ({
         ...prev,
         organize: {
            ...prev.organize,
            rename: { ...prev.organize.rename, [key]: value }
         }
      }) : null);
   };

   const updateAiConfig = (key: string, value: any) => {
      if (!config) return;
      setConfig(prev => prev ? ({
         ...prev,
         organize: {
            ...prev.organize,
            ai: { ...prev.organize.ai, [key]: value }
         }
      }) : null);
   };

   const updateOrganize = (key: string, value: any) => {
      if (!config) return;
      setConfig(prev => prev ? ({
         ...prev,
         organize: { ...prev.organize, [key]: value }
      }) : null);
   };

   const getActiveRules = () => {
      if (!config) return [];
      return activeRuleTab === 'movie' ? config.organize.movieRules : config.organize.tvRules;
   };

   const updateRuleList = (newRules: ClassificationRule[]) => {
      if (!config) return;
      setConfig(prev => prev ? ({
         ...prev,
         organize: {
            ...prev.organize,
            [activeRuleTab === 'movie' ? 'movieRules' : 'tvRules']: newRules
         }
      }) : null);
   };

   // Rule Logic
   const handleAddRule = () => {
      const newRule: ClassificationRule = {
         id: `custom_${Date.now()}`,
         name: '自定义模块',
         targetCid: '',
         conditions: {}
      };
      setTempRule(newRule);
      setEditingRuleId(newRule.id);
   };

   const handleEditRule = (rule: ClassificationRule) => {
      setTempRule({ ...rule, conditions: { ...rule.conditions } });
      setEditingRuleId(rule.id);
   };

   const handleDeleteRule = (id: string) => {
      updateRuleList(getActiveRules().filter(r => r.id !== id));
   };

   const handleSaveRule = () => {
      if (!tempRule) return;
      const currentRules = getActiveRules();
      const existingIndex = currentRules.findIndex(r => r.id === tempRule.id);
      if (existingIndex >= 0) {
         const updated = [...currentRules];
         updated[existingIndex] = tempRule;
         updateRuleList(updated);
      } else {
         updateRuleList([...currentRules, tempRule]);
      }
      setEditingRuleId(null);
      setTempRule(null);
   };

   const handleRestorePresets = () => {
      if (confirm('确定要恢复默认分类模块吗？所有自定义更改将丢失。')) {
         if (!config) return;
         setConfig(prev => prev ? ({
            ...prev,
            organize: {
               ...prev.organize,
               movieRules: DEFAULT_MOVIE_RULES,
               tvRules: DEFAULT_TV_RULES
            }
         }) : null);
         setToast('已恢复默认预设模块');
      }
   };

   const toggleTempCondition = (type: MatchConditionType, value: string) => {
      if (!tempRule) return;
      let currentVal = tempRule.conditions[type] || '';
      let items = currentVal.replace(/^!/, '').split(',').filter(Boolean);
      const hasExclusiveFlag = currentVal.startsWith('!');
      if (items.includes(value)) items = items.filter(i => i !== value);
      else items.push(value);
      let newVal = items.join(',');
      if (newVal && hasExclusiveFlag) newVal = '!' + newVal;
      setTempRule({ ...tempRule, conditions: { ...tempRule.conditions, [type]: newVal } });
   };

   const toggleExclusive = (type: MatchConditionType) => {
      if (!tempRule) return;
      const currentVal = tempRule.conditions[type] || '';
      if (!currentVal) return;
      if (currentVal.startsWith('!')) {
         setTempRule({ ...tempRule, conditions: { ...tempRule.conditions, [type]: currentVal.substring(1) } });
      } else {
         setTempRule({ ...tempRule, conditions: { ...tempRule.conditions, [type]: '!' + currentVal } });
      }
   };

   const isSelected = (type: MatchConditionType, value: string) => {
      if (!tempRule) return false;
      const val = tempRule.conditions[type] || '';
      return val.replace(/^!/, '').split(',').includes(value);
   };

   const isExclusiveMode = (type: MatchConditionType) => {
      return tempRule?.conditions[type]?.startsWith('!') || false;
   };

   // 真实 QR 逻辑 - 已修复 open_app 参数
   const stopQrCheck = () => {
      if (qrTimerRef.current) {
         clearInterval(qrTimerRef.current);
         qrTimerRef.current = null;
      }
   };

   const generateRealQr = async () => {
      if (!config) return;

      // 1. 补丁：open_app 必须填写 AppID
      if (
         config.cloud115.loginMethod === 'open_app' &&
         !config.cloud115.appId
      ) {
         setToast('请先填写第三方 AppID');
         return;
      }

      stopQrCheck();
      setQrState('loading');
      setQrImage('');
      setQrSessionId('');

      try {
         // 2. 补丁：区分 qrcode / open_app 调用参数
         const targetApp = config.cloud115.loginMethod === 'open_app' ? 'open_app' : config.cloud115.loginApp;
         const targetAppId = config.cloud115.loginMethod === 'open_app' ? config.cloud115.appId : undefined;

         const data = await api.get115QrCode(
            targetApp,
            config.cloud115.loginMethod as 'qrcode' | 'open_app',
            targetAppId
         );

         setQrImage(data.qrcode);
         setQrSessionId(data.sessionId);
         setQrState('waiting');

         qrTimerRef.current = setInterval(async () => {
            try {
               const statusRes = await api.check115QrStatus(
                  data.sessionId,
                  0,
                  ''
               );
               const status = statusRes.data.status;

               // 使用 switch 处理状态
               switch (status) {
                  case 'scanned':
                     setQrState('scanned');
                     break;
                  case 'success':
                     stopQrCheck();
                     setQrState('success');
                     fetchConfig();
                     setToast('登录成功，Cookie 已自动保存');
                     break;
                  case 'expired':
                  case 'error':
                     stopQrCheck();
                     setQrState(status);
                     break;
                  default:
                     break;
               }
            } catch (err) {
               console.error('QR Poll failed', err);
            }
         }, 2000);
      } catch (e: any) {
         console.error('QR Code generation failed:', e);
         setQrState('error');
         // 根据错误类型显示不同的消息
         if (e.code === 'ERR_NETWORK' || e.message?.includes('Network Error')) {
            setToast('无法连接后端服务器，请检查网络或服务状态');
         } else if (e.response?.status === 401) {
            setToast('登录已过期，请重新登录');
         } else if (e.response?.data?.error) {
            setToast(`二维码生成失败: ${e.response.data.error}`);
         } else {
            setToast(`二维码生成失败: ${e.message || '未知错误'}`);
         }
         stopQrCheck();
      }
   };


   const handleDirSelect = (cid: string, name: string) => {
      if (selectorTarget === 'download') { updateNested('cloud115', 'downloadPath', cid); updateNested('cloud115', 'downloadDirName', name); }
      else if (selectorTarget === 'download123') { updateNested('cloud123', 'downloadPath', cid); updateNested('cloud123', 'downloadDirName', name); }
      else if (selectorTarget === 'source') { updateOrganize('sourceCid', cid); updateOrganize('sourceDirName', name); }
      else if (selectorTarget === 'target') { updateOrganize('targetCid', cid); updateOrganize('targetDirName', name); }
   };

   const fillOpenListIp = () => {
      updateNested('openList', 'url', `http://${window.location.hostname}:5244`);
   };

   const insertTag = (tag: string, target: 'movie' | 'series') => {
      if (!config) return;
      const current = target === 'movie' ? config.organize.rename.movieTemplate : config.organize.rename.seriesTemplate;
      updateRenameRule(target === 'movie' ? 'movieTemplate' : 'seriesTemplate', current + ' ' + tag);
   };

   if (loading) {
      return (
         <div className="flex h-screen items-center justify-center text-slate-500 gap-2 bg-slate-50 dark:bg-slate-900">
            <Loader2 className="animate-spin" /> 正在加载配置...
         </div>
      );
   }

   if (!config) return null;

   const glassCardClass = "bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border-[0.5px] border-white/40 dark:border-white/10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.2)] ring-1 ring-white/50 dark:ring-white/5 inset";
   const inputClass = "w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-brand-500 outline-none transition-all font-mono text-sm backdrop-blur-sm shadow-inner";
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
            <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight drop-shadow-sm">网盘整理</h2>
         </div>

         <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">

            {/* Account Management */}
            <section className={`${glassCardClass} xl:col-span-2`}>
               <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                     <div className="p-2 bg-orange-50 dark:bg-orange-900/20 rounded-lg text-orange-600 dark:text-orange-400 shadow-inner">
                        <Cookie size={20} />
                     </div>
                     <h3 className="font-bold text-slate-700 dark:text-slate-200 text-base">账号与连接</h3>
                  </div>
                  <button
                     onClick={handleSave}
                     disabled={isSaving}
                     className={`${actionBtnClass} bg-orange-50 text-orange-600 hover:bg-orange-100 dark:bg-orange-900/20 dark:text-orange-400 dark:hover:bg-orange-900/40 disabled:opacity-50`}
                  >
                     {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                     保存设置
                  </button>
               </div>
               <div className="p-6">
                  {/* Account Tabs */}
                  <div className="flex gap-6 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 mb-6">
                     <button onClick={() => setActiveTab('115')} className={`pb-3 px-2 font-bold text-sm transition-colors border-b-2 ${activeTab === '115' ? 'border-brand-600 text-brand-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>115 网盘</button>
                     <button onClick={() => setActiveTab('123')} className={`pb-3 px-2 font-bold text-sm transition-colors border-b-2 ${activeTab === '123' ? 'border-brand-600 text-brand-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>123 云盘</button>
                     <button onClick={() => setActiveTab('openlist')} className={`pb-3 px-2 font-bold text-sm transition-colors border-b-2 ${activeTab === 'openlist' ? 'border-brand-600 text-brand-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>OpenList</button>
                  </div>

                  {/* 115 Settings */}
                  {activeTab === '115' && (
                     <div className="space-y-6 animate-in fade-in duration-300">
                        <div className="flex flex-wrap gap-3 mb-6">
                           {[
                              { id: 'cookie', label: 'Cookie 导入', icon: Cookie },
                              { id: 'qrcode', label: '扫码获取', icon: QrCode },
                              { id: 'open_app', label: '第三方 App ID', icon: Smartphone }
                           ].map((tab) => (
                              <button
                                 key={tab.id}
                                 onClick={() => updateNested('cloud115', 'loginMethod', tab.id)}
                                 className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border-[0.5px] transition-all shadow-sm ${config.cloud115.loginMethod === tab.id
                                    ? 'bg-brand-50 border-brand-200 text-brand-600 dark:bg-brand-900/20 dark:border-brand-800 dark:text-brand-400'
                                    : 'bg-white/50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-600 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-700/50'
                                    }`}
                              >
                                 <tab.icon size={16} /> {tab.label}
                              </button>
                           ))}
                        </div>

                        {config.cloud115.loginMethod === 'cookie' && (
                           <div className="space-y-3">
                              <label className="text-sm font-medium text-slate-600 dark:text-slate-400">Cookie 字符串</label>
                              <SensitiveInput
                                 multiline
                                 value={config.cloud115.cookies}
                                 onChange={(e) => updateNested('cloud115', 'cookies', e.target.value)}
                                 placeholder="UID=...; CID=...; SEID=..."
                                 className={inputClass}
                              />
                              <button
                                 onClick={handleSave}
                                 disabled={isSaving || !config.cloud115.cookies}
                                 className="px-5 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-lg hover:bg-brand-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                 {isSaving ? <RefreshCw className="animate-spin" size={16} /> : <Save size={16} />}
                                 登录 / 保存 Cookie
                              </button>
                           </div>
                        )}

                        {/* 扫码与第三方登录区域 */}
                        {(config.cloud115.loginMethod === 'qrcode' || config.cloud115.loginMethod === 'open_app') && (
                           <div className="border-[0.5px] border-dashed border-slate-300 dark:border-slate-700 rounded-xl p-8 flex flex-col items-center justify-center bg-slate-50/50 dark:bg-slate-900/30">

                              {/* 场景 A: 第三方 App ID 输入 (仅在 open_app 模式显示) */}
                              {config.cloud115.loginMethod === 'open_app' && (
                                 <div className="w-full max-w-sm mb-6 animate-in fade-in slide-in-from-bottom-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">App ID</label>
                                    <SensitiveInput
                                       value={config.cloud115.appId || ''}
                                       onChange={(e) => updateNested('cloud115', 'appId', e.target.value)}
                                       className={inputClass}
                                    />
                                 </div>
                              )}

                              {/* 场景 B: 标准扫码 - 模拟终端选择 (仅在 qrcode 模式显示) */}
                              {config.cloud115.loginMethod === 'qrcode' && (
                                 <div className="w-full max-w-sm mb-6 animate-in fade-in slide-in-from-bottom-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase mb-3 block flex items-center gap-1">
                                       <Smartphone size={14} /> 模拟登录终端 (App Type)
                                    </label>
                                    <select
                                       value={config.cloud115.loginApp || 'web'}
                                       onChange={(e) => updateNested('cloud115', 'loginApp', e.target.value)}
                                       className="w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-700/50 text-slate-800 dark:text-slate-100 text-sm focus:ring-2 focus:ring-brand-500 outline-none backdrop-blur-sm"
                                    >
                                       <option value="web">web</option>
                                       <option value="pcweb">pcweb</option>
                                       <option value="android">android</option>
                                       <option value="android_tv">android_tv</option>
                                       <option value="ios">ios</option>
                                       <option value="ipad">ipad</option>
                                       <option value="applet">applet</option>
                                       <option value="mini">mini</option>
                                       <option value="qandroid">qandroid</option>
                                       <option value="desktop">desktop</option>
                                       <option value="windows">windows</option>
                                       <option value="mac">mac</option>
                                       <option value="linux">linux</option>
                                       <option value="harmony">harmony</option>
                                       <option value="xiaomi">xiaomi</option>
                                       <option value="huawei">huawei</option>
                                       <option value="oppo">oppo</option>
                                       <option value="vivo">vivo</option>
                                       <option value="samsung">samsung</option>
                                       <option value="browser">browser</option>
                                       <option value="client">client</option>
                                       <option value="open_app">open_app</option>
                                    </select>
                                 </div>
                              )}

                              {/* 二维码显示区域 (共用) */}
                              {!qrImage && qrState !== 'loading' ? (
                                 <button onClick={generateRealQr} className="px-6 py-3 bg-brand-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-lg hover:bg-brand-700 transition-colors">
                                    <QrCode size={18} />
                                    {config.cloud115.loginMethod === 'qrcode' ? '生成二维码' : '获取第三方登录二维码'}
                                 </button>
                              ) : (
                                 <div className="text-center animate-in fade-in zoom-in duration-300 relative">
                                    {qrState === 'loading' ? (
                                       <div className="w-40 h-40 flex items-center justify-center"><RefreshCw className="animate-spin text-brand-500" size={32} /></div>
                                    ) : (
                                       <img src={qrImage} alt="QR" className={`w-40 h-40 rounded-lg border-4 border-white shadow-xl mx-auto mb-4 ${qrState === 'expired' ? 'opacity-20' : ''}`} />
                                    )}

                                    {(qrState === 'expired' || qrState === 'error') && (
                                       <div className="absolute inset-0 flex items-center justify-center cursor-pointer" onClick={generateRealQr}>
                                          <div className="bg-slate-800/80 text-white px-4 py-2 rounded-full text-xs font-bold flex items-center gap-1 hover:scale-105 transition-transform">
                                             <RotateCcw size={14} /> 点击刷新
                                          </div>
                                       </div>
                                    )}

                                    <p className="text-sm text-slate-600 dark:text-slate-300 font-medium">请使用 115 App 扫码</p>
                                    <p className={`text-xs mt-1 font-bold ${qrState === 'success' ? 'text-green-500' : 'text-slate-400'}`}>
                                       {qrState === 'scanned' ? '已扫描，请在手机上确认' :
                                          qrState === 'success' ? '登录成功！' :
                                             qrState === 'expired' ? '二维码已过期' :
                                                qrState === 'error' ? '获取失败，请重试' : '等待扫描...'}
                                    </p>
                                 </div>
                              )}
                           </div>
                        )}

                        <div className="flex gap-8 pt-6 border-t-[0.5px] border-slate-100 dark:border-slate-700/50">
                           <div className="flex-1">
                              <label className="flex items-center text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">默认下载目录</label>
                              <div className="flex gap-3">
                                 <div className="flex-1 px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-slate-50/50 dark:bg-slate-900/50 text-slate-600 dark:text-slate-400 text-sm flex items-center gap-2 backdrop-blur-sm shadow-inner">
                                    <FolderInput size={18} />
                                    {config.cloud115.downloadDirName}
                                    <span className="text-xs opacity-50 ml-auto font-mono">CID: {config.cloud115.downloadPath}</span>
                                 </div>
                                 <button
                                    onClick={() => { setSelectorTarget('download'); setFileSelectorOpen(true); }}
                                    className="px-4 py-2.5 bg-white/50 dark:bg-slate-700/50 border-[0.5px] border-slate-300/50 dark:border-slate-600/50 hover:border-brand-500 text-slate-700 dark:text-slate-200 rounded-lg text-sm font-medium transition-colors backdrop-blur-sm"
                                 >
                                    选择
                                 </button>
                              </div>
                           </div>
                           <div className="w-1/3">
                              <label className="flex items-center text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5 gap-2">
                                 <Gauge size={16} /> QPS 限制
                              </label>
                              <input
                                 type="range" min="0.1" max="1.2" step="0.1"
                                 value={config.cloud115.qps}
                                 onChange={(e) => updateNested('cloud115', 'qps', parseFloat(e.target.value))}
                                 className="w-full h-2 bg-slate-200 dark:bg-slate-600 rounded-lg cursor-pointer accent-brand-600 mb-2"
                              />
                              <div className="flex justify-between text-xs text-slate-500 font-medium">
                                 <span>0.1</span>
                                 <span className="font-bold text-brand-600">{config.cloud115.qps} /s</span>
                                 <span>1.2</span>
                              </div>
                           </div>
                        </div>
                     </div>
                  )}

                  {activeTab === '123' && (
                     <div className="space-y-6 animate-in fade-in duration-300">
                        {/* 登录方式切换 */}
                        <div className="flex gap-2 mb-4">
                           <button
                              onClick={() => updateNested('cloud123', 'loginMethod', 'password')}
                              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all shadow-sm ${config.cloud123.loginMethod === 'password' ? 'bg-blue-600 text-white shadow-blue-200' : 'border-slate-200 text-slate-500'}`}
                           >
                              密码登录
                           </button>
                           <button
                              onClick={() => updateNested('cloud123', 'loginMethod', 'oauth')}
                              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all shadow-sm ${config.cloud123.loginMethod !== 'password' ? 'bg-blue-600 text-white shadow-blue-200' : 'border-slate-200 text-slate-500'}`}
                           >
                              开放平台凭据
                           </button>
                        </div>

                        {/* 密码登录表单 */}
                        {config.cloud123.loginMethod === 'password' && (
                           <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-4 bg-white/30 dark:bg-slate-800/30 rounded-xl border border-slate-200/50 dark:border-slate-700/50">
                              <div>
                                 <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">手机号</label>
                                 <input
                                    type="text"
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
                              <div className="col-span-2">
                                 <button
                                    onClick={async () => {
                                       try {
                                          setIsSaving(true);
                                          const result = await api.login123WithPassword(
                                             config.cloud123.passport || '',
                                             config.cloud123.password || ''
                                          );
                                          if (result.success) {
                                             setToast('123云盘登录成功！');
                                          } else {
                                             setToast(result.error || '登录失败');
                                          }
                                       } catch (err: any) {
                                          setToast(err.response?.data?.error || '登录失败');
                                       } finally {
                                          setIsSaving(false);
                                       }
                                    }}
                                    disabled={isSaving || !config.cloud123.passport || !config.cloud123.password}
                                    className="px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                 >
                                    {isSaving ? <RefreshCw className="animate-spin" size={16} /> : <Save size={16} />}
                                    密码登录
                                 </button>
                              </div>
                           </div>
                        )}

                        {/* OAuth 登录表单 */}
                        {config.cloud123.loginMethod !== 'password' && (
                           <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
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
                           </div>
                        )}
                        {config.cloud123.loginMethod !== 'password' && (
                           <div className="flex items-center gap-4 mt-4">
                              <button
                                 onClick={handleSave}
                                 disabled={isSaving || !config.cloud123.clientId || !config.cloud123.clientSecret}
                                 className="px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                              >
                                 {isSaving ? <RefreshCw className="animate-spin" size={16} /> : <Save size={16} />}
                                 登录 / 保存凭据
                              </button>
                           </div>
                        )}

                        <div className="flex gap-8 pt-2">
                           <div className="flex-1">
                              <label className="flex items-center text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">离线下载目录</label>
                              <div className="flex gap-3">
                                 <div className="flex-1 px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-slate-50/50 dark:bg-slate-900/50 text-slate-600 dark:text-slate-400 text-sm flex items-center gap-2 backdrop-blur-sm shadow-inner">
                                    <FolderInput size={18} />
                                    {config.cloud123.downloadDirName}
                                    <span className="text-xs opacity-50 ml-auto font-mono">ID: {config.cloud123.downloadPath}</span>
                                 </div>
                                 <button
                                    onClick={() => { setSelectorTarget('download123'); setFileSelectorOpen(true); }}
                                    className="px-4 py-2.5 bg-white/50 dark:bg-slate-700/50 border-[0.5px] border-slate-300/50 dark:border-slate-600/50 hover:border-brand-500 text-slate-700 dark:text-slate-200 rounded-lg text-sm font-medium transition-colors backdrop-blur-sm"
                                 >
                                    选择
                                 </button>
                              </div>
                           </div>
                           <div className="w-1/3">
                              <label className="flex items-center text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5 gap-2">
                                 <Gauge size={16} /> QPS 限制 (最大 2.0)
                              </label>
                              <input
                                 type="range" min="0.1" max="2.0" step="0.1"
                                 value={config.cloud123.qps || 1.0}
                                 onChange={(e) => updateNested('cloud123', 'qps', parseFloat(e.target.value))}
                                 className="w-full h-2 bg-slate-200 dark:bg-slate-600 rounded-lg cursor-pointer accent-blue-600 mb-2"
                              />
                              <div className="flex justify-between text-xs text-slate-500 font-medium">
                                 <span>0.1</span>
                                 <span className="font-bold text-blue-600">{config.cloud123.qps || 1.0} /s</span>
                                 <span>2.0</span>
                              </div>
                           </div>
                        </div>
                     </div>
                  )}

                  {activeTab === 'openlist' && (
                     <div className="grid grid-cols-1 md:grid-cols-2 gap-6 animate-in fade-in duration-300">
                        <div className="md:col-span-2 bg-cyan-50/50 dark:bg-cyan-900/20 p-4 rounded-xl border-[0.5px] border-cyan-100 dark:border-cyan-800 mb-2 flex items-start gap-3 backdrop-blur-sm">
                           <AlertCircle size={20} className="text-cyan-600 dark:text-cyan-400 shrink-0 mt-0.5" />
                           <div className="text-sm text-cyan-800 dark:text-cyan-200">
                              <strong>重要提示：</strong> 为了确保正常连接，请务必在 OpenList 后台设置中关闭 <code>sign</code> 和 <code>sign_slice</code> 两个签名验证选项。
                           </div>
                        </div>

                        <div className="md:col-span-2">
                           <div className="flex justify-between items-center mb-2">
                              <label className="block text-sm font-medium text-slate-600 dark:text-slate-400">服务器地址</label>
                              <button onClick={fillOpenListIp} className="text-xs text-brand-600 hover:text-brand-500 flex items-center gap-1 font-medium"><Zap size={12} /> 自动填入</button>
                           </div>
                           <input
                              type="text"
                              value={config.openList.url}
                              onChange={(e) => updateNested('openList', 'url', e.target.value)}
                              placeholder="http://192.168.1.5:5244"
                              className={inputClass}
                           />
                        </div>
                        <div>
                           <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">用户名</label>
                           <input
                              type="text"
                              value={config.openList.username}
                              onChange={(e) => updateNested('openList', 'username', e.target.value)}
                              className={inputClass}
                           />
                        </div>
                        <div>
                           <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-1.5">密码</label>
                           <SensitiveInput
                              value={config.openList.password || ''}
                              onChange={(e) => updateNested('openList', 'password', e.target.value)}
                              className={inputClass}
                           />
                        </div>
                     </div>
                  )}
               </div>
            </section>

            {/* Organize Rules Engine */}
            {activeTab !== 'openlist' && (
               <section className={`${glassCardClass} xl:col-span-2 animate-in fade-in slide-in-from-bottom-2 duration-300`}>
                  <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
                     <div className="flex items-center gap-3">
                        <div className="p-2 bg-indigo-50 dark:bg-indigo-900/20 rounded-lg text-indigo-600 dark:text-indigo-400 shadow-inner">
                           <Film size={20} />
                        </div>
                        <h3 className="font-bold text-slate-700 dark:text-slate-200 text-base">分类与重命名规则 (TMDB)</h3>
                     </div>
                     <div className="flex items-center gap-3">
                        <button
                           onClick={handleSave}
                           disabled={isSaving}
                           className={`${actionBtnClass} bg-indigo-50 text-indigo-600 hover:bg-indigo-100 dark:bg-indigo-900/20 dark:text-indigo-400 dark:hover:bg-indigo-900/40 disabled:opacity-50`}
                        >
                           {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                           保存设置
                        </button>
                     </div>
                  </div>

                  <div className="p-6 space-y-8">
                     {/* Source and Target Directories */}
                     <div className="grid grid-cols-1 md:grid-cols-2 gap-8 bg-slate-50/50 dark:bg-slate-900/30 p-6 rounded-xl border-[0.5px] border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-inner">
                        <div>
                           <label className="flex items-center text-xs font-bold text-slate-500 uppercase mb-3">源目录 (Source)</label>
                           <div className="flex gap-3">
                              <div className="flex-1 px-4 py-3 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-700/50 text-slate-700 dark:text-slate-300 text-sm flex items-center gap-3 backdrop-blur-sm">
                                 <FolderInput size={20} />
                                 {config.organize.sourceDirName || '默认下载目录'}
                              </div>
                              <button onClick={() => { setSelectorTarget('source'); setFileSelectorOpen(true); }} className="px-4 py-3 bg-white/50 dark:bg-slate-700/50 border-[0.5px] border-slate-300/50 dark:border-slate-600/50 hover:border-indigo-500 rounded-lg text-sm font-medium transition-colors backdrop-blur-sm">选择</button>
                           </div>
                        </div>
                        <div>
                           <label className="flex items-center text-xs font-bold text-slate-500 uppercase mb-3">目标目录 (Target)</label>
                           <div className="flex gap-3">
                              <div className="flex-1 px-4 py-3 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-700/50 text-slate-700 dark:text-slate-300 text-sm flex items-center gap-3 backdrop-blur-sm">
                                 <FolderOutput size={20} />
                                 {config.organize.targetDirName || '整理存放目录'}
                              </div>
                              <button onClick={() => { setSelectorTarget('target'); setFileSelectorOpen(true); }} className="px-4 py-3 bg-white/50 dark:bg-slate-700/50 border-[0.5px] border-slate-300/50 dark:border-slate-600/50 hover:border-indigo-500 rounded-lg text-sm font-medium transition-colors backdrop-blur-sm">选择</button>
                           </div>
                        </div>
                     </div>

                     <div className="transition-all duration-300">
                        {/* AI Config */}
                        <div className="mb-8 border-b-[0.5px] border-slate-100 dark:border-slate-700/50 pb-8">
                           <div className="flex items-center justify-between mb-4">
                              <div className="flex items-center gap-2">
                                 <BrainCircuit size={20} className="text-pink-500" />
                                 <h4 className="font-bold text-slate-700 dark:text-slate-200">AI 智能重命名 (大模型辅助)</h4>
                              </div>
                              <input
                                 type="checkbox"
                                 checked={config.organize.ai.enabled}
                                 onChange={(e) => updateAiConfig('enabled', e.target.checked)}
                                 className="w-5 h-5 rounded text-pink-600 focus:ring-pink-500"
                              />
                           </div>
                           {config.organize.ai.enabled && (
                              <div className="grid grid-cols-1 md:grid-cols-4 gap-6 bg-pink-50/50 dark:bg-pink-900/10 p-5 rounded-xl border-[0.5px] border-pink-100 dark:border-pink-900/50 backdrop-blur-sm">
                                 <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-2">服务商</label>
                                    <select
                                       value={config.organize.ai.provider}
                                       onChange={(e) => updateAiConfig('provider', e.target.value)}
                                       className="w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-700/50 text-slate-800 dark:text-slate-100 text-sm backdrop-blur-sm"
                                    >
                                       <option value="openai">ChatGPT (OpenAI)</option>
                                       <option value="gemini">Google Gemini</option>
                                       <option value="deepseek">DeepSeek 深度求索</option>
                                       <option value="zhipu">智谱 GLM</option>
                                       <option value="custom">自定义 (Compatible)</option>
                                    </select>
                                 </div>
                                 <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-2">API Key</label>
                                    <SensitiveInput
                                       value={config.organize.ai.apiKey}
                                       onChange={(e) => updateAiConfig('apiKey', e.target.value)}
                                       className={inputClass}
                                    />
                                 </div>
                                 <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-2">Base URL (可选)</label>
                                    <input
                                       type="text"
                                       value={config.organize.ai.baseUrl}
                                       onChange={(e) => updateAiConfig('baseUrl', e.target.value)}
                                       placeholder={config.organize.ai.provider === 'deepseek' ? 'https://api.deepseek.com/v1' : config.organize.ai.provider === 'zhipu' ? 'https://open.bigmodel.cn/api/paas/v4' : 'https://api.openai.com/v1'}
                                       className={inputClass}
                                    />
                                 </div>
                                 <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-2">模型名称</label>
                                    <input
                                       type="text"
                                       value={config.organize.ai.model}
                                       onChange={(e) => updateAiConfig('model', e.target.value)}
                                       placeholder={config.organize.ai.provider === 'openai' ? 'gpt-3.5-turbo' : config.organize.ai.provider === 'gemini' ? 'gemini-pro' : config.organize.ai.provider === 'deepseek' ? 'deepseek-chat' : config.organize.ai.provider === 'zhipu' ? 'glm-4' : 'model-name'}
                                       className={inputClass}
                                    />
                                 </div>
                              </div>
                           )}
                        </div>

                        {/* Global Renaming Settings */}
                        <div className="mb-8 grid grid-cols-1 gap-8 border-b-[0.5px] border-slate-100 dark:border-slate-700/50 pb-8">
                           <div>
                              <label className="block text-xs font-bold text-slate-500 uppercase mb-2">TMDB API 密钥</label>
                              <SensitiveInput
                                 value={config.tmdb.apiKey}
                                 onChange={(e) => updateNested('tmdb', 'apiKey', e.target.value)}
                                 className={inputClass}
                              />
                           </div>

                           <div className="flex items-center justify-between">
                              <label className="text-sm font-bold text-slate-600 dark:text-slate-400">强制赋予 TMDB ID (文件夹名附加 {`{tmdb-id}`})</label>
                              <input
                                 type="checkbox"
                                 checked={config.organize.rename.addTmdbIdToFolder}
                                 onChange={(e) => updateRenameRule('addTmdbIdToFolder', e.target.checked)}
                                 className="w-5 h-5 rounded text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                              />
                           </div>

                           <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                              {/* Movie Template Builder */}
                              <div className="space-y-4">
                                 <label className="flex items-center text-xs font-bold text-slate-500 uppercase tracking-wide">电影重命名规则</label>
                                 <div className="flex flex-wrap gap-2 mb-2">
                                    {RENAME_TAGS.map(tag => (
                                       <button key={tag.value} onClick={() => insertTag(tag.value, 'movie')} className="px-3 py-1.5 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 text-xs rounded-lg hover:bg-indigo-100 hover:text-indigo-600 transition-colors font-medium">
                                          {tag.label}
                                       </button>
                                    ))}
                                 </div>
                                 <input
                                    type="text"
                                    value={config.organize.rename.movieTemplate}
                                    onChange={(e) => updateRenameRule('movieTemplate', e.target.value)}
                                    className={inputClass}
                                 />
                              </div>

                              {/* Series Template Builder */}
                              <div className="space-y-4">
                                 <label className="flex items-center text-xs font-bold text-slate-500 uppercase tracking-wide">剧集重命名规则</label>
                                 <div className="flex flex-wrap gap-2 mb-2">
                                    {RENAME_TAGS.map(tag => (
                                       <button key={tag.value} onClick={() => insertTag(tag.value, 'series')} className="px-3 py-1.5 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 text-xs rounded-lg hover:bg-indigo-100 hover:text-indigo-600 transition-colors font-medium">
                                          {tag.label}
                                       </button>
                                    ))}
                                 </div>
                                 <input
                                    type="text"
                                    value={config.organize.rename.seriesTemplate}
                                    onChange={(e) => updateRenameRule('seriesTemplate', e.target.value)}
                                    className={inputClass}
                                 />
                              </div>
                           </div>
                        </div>

                        {/* Modules / Rules System */}
                        <div>
                           <div className="flex items-center justify-between mb-6">
                              <div className="flex gap-3 bg-slate-100/50 dark:bg-slate-900/50 p-1 rounded-lg backdrop-blur-sm border-[0.5px] border-slate-200/50">
                                 <button
                                    onClick={() => { setActiveRuleTab('movie'); setEditingRuleId(null); }}
                                    className={`px-4 py-2 rounded-lg text-sm font-bold transition-all flex items-center gap-2 ${activeRuleTab === 'movie' ? 'bg-white dark:bg-slate-700 shadow-sm text-indigo-600 dark:text-indigo-400' : 'text-slate-500 hover:text-slate-700'}`}
                                 >
                                    <Film size={16} /> 电影模块
                                 </button>
                                 <button
                                    onClick={() => { setActiveRuleTab('tv'); setEditingRuleId(null); }}
                                    className={`px-4 py-2 rounded-lg text-sm font-bold transition-all flex items-center gap-2 ${activeRuleTab === 'tv' ? 'bg-white dark:bg-slate-700 shadow-sm text-indigo-600 dark:text-indigo-400' : 'text-slate-500 hover:text-slate-700'}`}
                                 >
                                    <Tv size={16} /> 剧集模块
                                 </button>
                              </div>
                              <div className="flex gap-3">
                                 <button
                                    onClick={handleRestorePresets}
                                    className="px-4 py-2 text-xs font-bold text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 rounded-lg flex items-center gap-2 transition-colors"
                                 >
                                    <RotateCcw size={14} /> 恢复预设
                                 </button>
                                 <button
                                    onClick={handleAddRule}
                                    className="px-5 py-2 text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg flex items-center gap-2 shadow-lg shadow-indigo-500/20 transition-all active:scale-95 border-[0.5px] border-white/20"
                                 >
                                    <Plus size={16} /> 添加模块
                                 </button>
                              </div>
                           </div>

                           {/* Modules Grid */}
                           <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                              {getActiveRules().map((rule) => (
                                 <div key={rule.id} className="bg-slate-50/60 dark:bg-slate-900/30 border-[0.5px] border-slate-200 dark:border-slate-700/50 rounded-xl p-5 group hover:border-indigo-400 dark:hover:border-indigo-500 transition-colors relative hover:shadow-lg backdrop-blur-sm">
                                    <div className="flex justify-between items-start mb-3">
                                       <h4 className="font-bold text-slate-700 dark:text-slate-200 text-sm">{rule.name}</h4>
                                       <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                          <button onClick={() => handleEditRule(rule)} className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/30 rounded-lg"><Edit size={16} /></button>
                                          <button onClick={() => handleDeleteRule(rule.id)} className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg"><Trash2 size={16} /></button>
                                       </div>
                                    </div>

                                    {/* Summary Chips */}
                                    <div className="space-y-2">
                                       {/* Genre Summary */}
                                       <div className="flex items-center gap-2 text-xs">
                                          <LayoutList size={14} className="text-slate-400" />
                                          <span className="text-slate-600 dark:text-slate-400 truncate">
                                             {rule.conditions.genre_ids
                                                ? GENRES.filter(g => rule.conditions.genre_ids?.split(',').includes(g.id)).map(g => g.name.split(' ')[0]).join(', ')
                                                : '全部类型'}
                                          </span>
                                       </div>
                                       {/* Region Summary */}
                                       <div className="flex items-center gap-2 text-xs">
                                          <Globe size={14} className="text-slate-400" />
                                          <span className="text-slate-600 dark:text-slate-400 truncate">
                                             {rule.conditions.origin_country
                                                ? (rule.conditions.origin_country.startsWith('!') ? '排除: ' : '') + COUNTRIES.filter(c => rule.conditions.origin_country?.replace('!', '').split(',').includes(c.id)).map(c => c.name.split(' ')[0]).join(', ')
                                                : '全部地区'}
                                          </span>
                                       </div>
                                       {/* Language Summary */}
                                       <div className="flex items-center gap-2 text-xs">
                                          <Type size={14} className="text-slate-400" />
                                          <span className="text-slate-600 dark:text-slate-400 truncate">
                                             {rule.conditions.original_language
                                                ? (rule.conditions.original_language.startsWith('!') ? '排除: ' : '') + LANGUAGES.filter(l => rule.conditions.original_language?.replace('!', '').split(',').includes(l.id)).map(l => l.name.split(' ')[0]).join(', ')
                                                : '全部语言'}
                                          </span>
                                       </div>
                                    </div>
                                 </div>
                              ))}
                           </div>
                        </div>
                     </div>
                  </div>
               </section>
            )}
         </div>

         {/* Edit Rule Modal */}
         {editingRuleId && tempRule && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
               <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-2xl w-full overflow-hidden border-[0.5px] border-slate-200 dark:border-slate-700 flex flex-col max-h-[90vh]">
                  <div className="p-5 border-b-[0.5px] border-slate-100 dark:border-slate-700 flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
                     <h3 className="font-bold text-slate-700 dark:text-slate-200">编辑模块: {tempRule.name}</h3>
                     <button onClick={() => setEditingRuleId(null)} className="p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-full transition-colors"><X size={20} className="text-slate-400" /></button>
                  </div>

                  <div className="p-8 overflow-y-auto custom-scrollbar space-y-8">
                     <div>
                        <label className="block text-xs font-bold text-slate-500 uppercase mb-3">模块名称 (即文件夹名)</label>
                        <input
                           type="text"
                           value={tempRule.name}
                           onChange={(e) => setTempRule({ ...tempRule, name: e.target.value })}
                           className="w-full px-5 py-3 rounded-lg border-[0.5px] border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 outline-none font-bold text-base"
                        />
                     </div>

                     <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        {/* Genre Selection */}
                        <div className="space-y-3">
                           <div className="flex justify-between items-center border-b-[0.5px] border-slate-200 dark:border-slate-700 pb-2">
                              <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1"><LayoutList size={12} /> 类型</label>
                           </div>
                           <div className="max-h-72 overflow-y-auto pr-2 custom-scrollbar space-y-2">
                              {GENRES.map(g => (
                                 <label key={g.id} className={`flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors border-[0.5px] ${isSelected('genre_ids', g.id) ? 'bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800' : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-700/50'}`}>
                                    <input type="checkbox" className="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4" checked={isSelected('genre_ids', g.id)} onChange={() => toggleTempCondition('genre_ids', g.id)} />
                                    <span className="text-xs font-medium text-slate-700 dark:text-slate-300">{g.name}</span>
                                 </label>
                              ))}
                           </div>
                        </div>

                        {/* Region Selection */}
                        <div className="space-y-3">
                           <div className="flex justify-between items-center border-b-[0.5px] border-slate-200 dark:border-slate-700 pb-2">
                              <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1"><Globe size={12} /> 地区</label>
                              <button
                                 onClick={() => toggleExclusive('origin_country')}
                                 className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${isExclusiveMode('origin_country') ? 'bg-red-50 text-red-600 border-red-200 dark:bg-red-900/20 dark:border-red-800' : 'bg-slate-50 text-slate-400 border-slate-200 dark:bg-slate-700 dark:border-slate-600'}`}
                              >
                                 {isExclusiveMode('origin_country') ? '模式: 排除所选' : '模式: 包含所选'}
                              </button>
                           </div>
                           <div className="max-h-72 overflow-y-auto pr-2 custom-scrollbar space-y-2">
                              {COUNTRIES.map(c => (
                                 <label key={c.id} className={`flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors border-[0.5px] ${isSelected('origin_country', c.id) ? 'bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800' : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-700/50'}`}>
                                    <input type="checkbox" className="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4" checked={isSelected('origin_country', c.id)} onChange={() => toggleTempCondition('origin_country', c.id)} />
                                    <span className="text-xs font-medium text-slate-700 dark:text-slate-300">{c.name}</span>
                                 </label>
                              ))}
                           </div>
                        </div>

                        {/* Language Selection */}
                        <div className="space-y-3">
                           <div className="flex justify-between items-center border-b-[0.5px] border-slate-200 dark:border-slate-700 pb-2">
                              <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1"><Type size={12} /> 语言</label>
                              <button
                                 onClick={() => toggleExclusive('original_language')}
                                 className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${isExclusiveMode('original_language') ? 'bg-red-50 text-red-600 border-red-200 dark:bg-red-900/20 dark:border-red-800' : 'bg-slate-50 text-slate-400 border-slate-200 dark:bg-slate-700 dark:border-slate-600'}`}
                              >
                                 {isExclusiveMode('original_language') ? '模式: 排除所选' : '模式: 包含所选'}
                              </button>
                           </div>
                           <div className="max-h-72 overflow-y-auto pr-2 custom-scrollbar space-y-2">
                              {LANGUAGES.map(l => (
                                 <label key={l.id} className={`flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors border-[0.5px] ${isSelected('original_language', l.id) ? 'bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-800' : 'border-transparent hover:bg-slate-50 dark:hover:bg-slate-700/50'}`}>
                                    <input type="checkbox" className="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4" checked={isSelected('original_language', l.id)} onChange={() => toggleTempCondition('original_language', l.id)} />
                                    <span className="text-xs font-medium text-slate-700 dark:text-slate-300">{l.name}</span>
                                 </label>
                              ))}
                           </div>
                        </div>
                     </div>
                  </div>

                  <div className="p-5 border-t-[0.5px] border-slate-100 dark:border-slate-700 flex justify-end gap-3 bg-slate-50 dark:bg-slate-900/50">
                     <button onClick={() => setEditingRuleId(null)} className="px-5 py-2.5 text-slate-500 hover:text-slate-700 text-sm font-medium">取消</button>
                     <button onClick={handleSaveRule} className="px-6 py-2.5 bg-indigo-600/90 hover:bg-indigo-600 backdrop-blur-sm border-[0.5px] border-white/10 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-lg shadow-indigo-500/20 transition-all active:scale-95">
                        <Check size={18} /> 保存模块
                     </button>
                  </div>
               </div>
            </div>
         )}

         <FileSelector
            isOpen={fileSelectorOpen}
            onClose={() => setFileSelectorOpen(false)}
            onSelect={handleDirSelect}
            title={`选择 ${selectorTarget === 'target' ? '存放目录' : selectorTarget === 'source' ? '源目录' : '下载目录'}`}
            cloudType={selectorTarget === 'download123' ? '123' : '115'}
         />
      </div>
   );
};