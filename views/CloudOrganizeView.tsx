import React, { useState, useEffect } from 'react';
import { AppConfig, ClassificationRule, MatchConditionType } from '../types';
import { api } from '../services/api';
// 确保 mockConfig 存在，如果不存在请创建一个空文件或根据需求调整
import { DEFAULT_MOVIE_RULES, DEFAULT_TV_RULES } from '../services/mockConfig';
import { Save, RefreshCw, Cookie, FolderInput, Trash2, Plus, Film, Type, Globe, Tv, LayoutList, FolderOutput, Zap, RotateCcw, X, Edit, Check, BrainCircuit, Loader2, FileText } from 'lucide-react';
import { SensitiveInput } from '../components/SensitiveInput';
import { FileSelector } from '../components/FileSelector';
import { OrganizeLogs } from '../components/OrganizeLogs';


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
   cloud115: { loginMethod: 'cookie', loginApp: 'android', cookies: '', userAgent: '', downloadPath: '0', downloadDirName: '根目录', autoDeleteMsg: false, qps: 1.0 },
   cloud123: { enabled: false, clientId: '', clientSecret: '', passport: '', password: '', downloadPath: '0', downloadDirName: '根目录', qps: 1.0 },
   openList: { enabled: false, url: '', mountPath: '', username: '', password: '' },
   tmdb: { apiKey: '', language: 'zh-CN', includeAdult: false },
   organize: {
      enabled: true,
      sourceCid115: '0',
      sourceDirName115: '根目录',
      targetCid115: '0',
      targetDirName115: '根目录',
      sourceCid123: '0',
      sourceDirName123: '根目录',
      targetCid123: '0',
      targetDirName123: '根目录',
      ai: { enabled: false, provider: 'openai', baseUrl: '', apiKey: '', model: '' },
      rename: {
         enabled: true,
         movieTemplate: '{{title}}{% if year %} ({{year}}){% endif %}{% if part %}-{{part}}{% endif %}{% if tmdbid %} {tmdb-{{tmdbid}}}{% endif %}{% if resolution %} [{{resolution}}]{% endif %}{% if version %} [{{version}}]{% endif %}',
         seriesTemplate: '{{title}} - {{season_episode}}{% if part %}-{{part}}{% endif %}{% if episode %} - 第 {{episode}} 集{% endif %}{% if tmdbid %} {tmdb-{{tmdbid}}}{% endif %}{% if resolution %} [{{resolution}}]{% endif %}{% if version %} [{{version}}]{% endif %}',
         addTmdbIdToFolder: true
      },
      movieRules: DEFAULT_MOVIE_RULES,
      tvRules: DEFAULT_TV_RULES
   }
};

export const CloudOrganizeView: React.FC = () => {
   const [config, setConfig] = useState<AppConfig | null>(null);
   const [loading, setLoading] = useState(true);

   const [isSaving, setIsSaving] = useState(false);
   const [toast, setToast] = useState<string | null>(null);

   const [activeTab, setActiveTab] = useState<'115' | '123'>('115');
   const [activeRuleTab, setActiveRuleTab] = useState<'movie' | 'tv'>('movie');
   const [fileSelectorOpen, setFileSelectorOpen] = useState(false);
   const [selectorTarget, setSelectorTarget] = useState<'download' | 'download123' | 'source115' | 'target115' | 'source123' | 'target123' | null>(null);
   const [showOrganizeLogs, setShowOrganizeLogs] = useState(false);
   const [isRunningWorkflow, setIsRunningWorkflow] = useState(false);
   const [isVerifying123, setIsVerifying123] = useState(false);

   const [editingRuleId, setEditingRuleId] = useState<string | null>(null);
   const [tempRule, setTempRule] = useState<ClassificationRule | null>(null);

   useEffect(() => {
      fetchConfig();
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
         setTimeout(() => setToast(null), 5000);
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

   const AI_PRESETS: Record<string, { baseUrl: string; model: string }> = {
      openai: { baseUrl: 'https://api.openai.com/v1', model: 'gpt-4o-mini' },
      gemini: { baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai', model: 'gemini-2.0-flash-exp' },
      deepseek: { baseUrl: 'https://api.deepseek.com/v1', model: 'deepseek-chat' },
      zhipu: { baseUrl: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash' },
      moonshot: { baseUrl: 'https://api.moonshot.cn/v1', model: 'moonshot-v1-8k' },
      groq: { baseUrl: 'https://api.groq.com/openai/v1', model: 'llama-3.3-70b-versatile' },
      qwen: { baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-turbo-latest' },
      siliconflow: { baseUrl: 'https://api.siliconflow.cn/v1', model: 'Qwen/Qwen2.5-7B-Instruct' },
      openrouter: { baseUrl: 'https://openrouter.ai/api/v1', model: 'google/gemini-2.0-flash-exp:free' },
      custom: { baseUrl: '', model: '' }
   };

   const updateAiConfig = (key: string, value: any) => {
      if (!config) return;
      setConfig(prev => {
         if (!prev) return null;
         const newAi = { ...prev.organize.ai, [key]: value };

         // 如果切换了服务商，自动应用预置值
         if (key === 'provider' && AI_PRESETS[value]) {
            newAi.baseUrl = AI_PRESETS[value].baseUrl;
            newAi.model = AI_PRESETS[value].model;
         }

         return {
            ...prev,
            organize: {
               ...prev.organize,
               ai: newAi
            }
         };
      });
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

   const handleRestoreRenameTemplates = () => {
      if (confirm('确定要恢复默认重命名模板吗？这将覆盖当前的模板设置。')) {
         if (!config) return;
         setConfig(prev => prev ? ({
            ...prev,
            organize: {
               ...prev.organize,
               rename: {
                  ...prev.organize.rename,
                  movieTemplate: `{{title}}{% if year %} ({{year}}){% endif %}{% if part %}-{{part}}{% endif %}{% if tmdbid %} {tmdb-{{tmdbid}}}{% endif %}{% if resolution %} [{{resolution}}]{% endif %}{% if version %} [{{version}}]{% endif %}`,
                  seriesTemplate: `{{title}} - {{season_episode}}{% if part %}-{{part}}{% endif %}{% if episode %} - 第 {{episode}} 集{% endif %}{% if tmdbid %} {tmdb-{{tmdbid}}}{% endif %}{% if resolution %} [{{resolution}}]{% endif %}{% if version %} [{{version}}]{% endif %}`
               }
            }
         }) : null);
         setToast('已恢复默认重命名模板');
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


   const handleRunOrganize = async () => {
      if (!config) return;
      setIsRunningWorkflow(true);
      setToast(`正在启动 ${activeTab === '115' ? '115 网盘' : '123 云盘'} 整理工作流...`);
      try {
         const res = await api.runOrganize(activeTab === '115' ? '115' : '123');
         if (res.success) {
            setToast('整理工作流已启动，请查看日志');
            setShowOrganizeLogs(true);
         } else {
            setToast(`启动失败: ${res.error || '未知错误'}`);
         }
      } catch (e) {
         setToast('启动失败 (网络错误)');
      } finally {
         setIsRunningWorkflow(false);
         setTimeout(() => setToast(null), 5000);
      }
   };

   const handleLogin123 = async () => {
      if (!config) return;
      setIsVerifying123(true);
      try {
         const res = await api.login123WithOAuth(config.cloud123.clientId, config.cloud123.clientSecret);
         if (res.success) {
            setToast('123 云盘 OAuth 凭证验证并保存成功');
         } else {
            setToast(`验证失败: ${res.error || '未知错误'}`);
         }
      } catch (e) {
         setToast('验证失败 (网络错误)');
      } finally {
         setIsVerifying123(false);
         setTimeout(() => setToast(null), 5000);
      }
   };

   const handleDirSelect = (cid: string, name: string) => {
      if (selectorTarget === 'download') { updateNested('cloud115', 'downloadPath', cid); updateNested('cloud115', 'downloadDirName', name); }
      else if (selectorTarget === 'download123') { updateNested('cloud123', 'downloadPath', cid); updateNested('cloud123', 'downloadDirName', name); }
      else if (selectorTarget === 'source115') { updateOrganize('sourceCid115', cid); updateOrganize('sourceDirName115', name); }
      else if (selectorTarget === 'target115') { updateOrganize('targetCid115', cid); updateOrganize('targetDirName115', name); }
      else if (selectorTarget === 'source123') { updateOrganize('sourceCid123', cid); updateOrganize('sourceDirName123', name); }
      else if (selectorTarget === 'target123') { updateOrganize('targetCid123', cid); updateOrganize('targetDirName123', name); }
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
            <button
               onClick={() => setShowOrganizeLogs(true)}
               className="px-4 py-2 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-xl text-sm font-bold flex items-center gap-2 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 transition-colors border border-indigo-200 dark:border-indigo-700"
            >
               <FileText size={16} />
               整理日志
            </button>
         </div>

         <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">

            {/* Connections & Workflow Section */}
            <section className={`${glassCardClass} xl:col-span-2 shadow-xl`}>
               <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between bg-slate-50/50 dark:bg-slate-900/50">
                  <div className="flex items-center gap-3">
                     <div className="p-2 bg-brand-50 dark:bg-brand-900/20 rounded-lg text-brand-600 dark:text-brand-400 shadow-inner">
                        <Globe size={20} />
                     </div>
                     <h3 className="font-bold text-slate-700 dark:text-slate-200 text-base">网盘连接与工作流</h3>
                  </div>
                  <div className="flex items-center gap-3">
                     <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className={`${actionBtnClass} bg-white dark:bg-slate-800 border-[0.5px] border-slate-200 dark:border-slate-700 shadow-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700`}
                     >
                        {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                        保存配置
                     </button>
                     <button
                        onClick={handleRunOrganize}
                        disabled={isRunningWorkflow}
                        className={`${actionBtnClass} bg-indigo-600 text-white hover:bg-indigo-700 shadow-lg shadow-indigo-500/20`}
                     >
                        {isRunningWorkflow ? <Loader2 className="animate-spin" size={12} /> : <Zap size={12} />}
                        立即整理
                     </button>
                  </div>
               </div>
               <div className="p-6">
                  {/* Account Tabs */}
                  <div className="flex gap-6 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 mb-8">
                     <button onClick={() => setActiveTab('115')} className={`pb-3 px-2 font-bold text-sm transition-colors border-b-2 flex items-center gap-2 ${activeTab === '115' ? 'border-brand-600 text-brand-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
                        <Cookie size={16} /> 115 网盘
                     </button>
                     <button onClick={() => setActiveTab('123')} className={`pb-3 px-2 font-bold text-sm transition-colors border-b-2 flex items-center gap-2 ${activeTab === '123' ? 'border-brand-600 text-brand-600' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
                        <LayoutList size={16} /> 123 云盘
                     </button>
                  </div>

                  {activeTab === '115' && (
                     <div className="space-y-8 animate-in fade-in duration-300">
                        {/* 115 Folders */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 bg-blue-50/30 dark:bg-blue-900/10 p-6 rounded-xl border-[0.5px] border-blue-100 dark:border-blue-900/50">
                           <div>
                              <label className="flex items-center text-xs font-bold text-slate-500 uppercase mb-3">115 源目录 (待整理)</label>
                              <div className="flex gap-3">
                                 <div className="flex-1 px-4 py-3 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-800/50 text-slate-700 dark:text-slate-300 text-sm flex items-center gap-3">
                                    <FolderInput size={20} className="text-blue-500" />
                                    {config.organize.sourceDirName115 || '根目录'}
                                 </div>
                                 <button onClick={() => { setSelectorTarget('source115'); setFileSelectorOpen(true); }} className="px-4 py-3 bg-white dark:bg-slate-700 border-[0.5px] border-slate-300/50 dark:border-slate-600/50 hover:border-blue-500 rounded-lg text-sm font-medium shadow-sm transition-all">选择</button>
                              </div>
                           </div>
                           <div>
                              <label className="flex items-center text-xs font-bold text-slate-500 uppercase mb-3">115 目标目录 (已整理)</label>
                              <div className="flex gap-3">
                                 <div className="flex-1 px-4 py-3 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-800/50 text-slate-700 dark:text-slate-300 text-sm flex items-center gap-3">
                                    <FolderOutput size={20} className="text-green-500" />
                                    {config.organize.targetDirName115 || '根目录'}
                                 </div>
                                 <button onClick={() => { setSelectorTarget('target115'); setFileSelectorOpen(true); }} className="px-4 py-3 bg-white dark:bg-slate-700 border-[0.5px] border-slate-300/50 dark:border-slate-600/50 hover:border-green-500 rounded-lg text-sm font-medium shadow-sm transition-all">选择</button>
                              </div>
                           </div>
                        </div>
                     </div>
                  )}

                  {activeTab === '123' && (
                     <div className="space-y-8 animate-in fade-in duration-300">
                        {/* 123 Auth Settings */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                           <div>
                              <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">OAuth Client ID</label>
                              <input
                                 type="text"
                                 value={config.cloud123.clientId}
                                 onChange={(e) => updateNested('cloud123', 'clientId', e.target.value)}
                                 className={inputClass}
                                 placeholder="从 123云盘开放平台获取"
                              />
                           </div>
                           <div>
                              <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">OAuth Client Secret</label>
                              <SensitiveInput
                                 value={config.cloud123.clientSecret}
                                 onChange={(e) => updateNested('cloud123', 'clientSecret', e.target.value)}
                                 className={inputClass}
                              />
                           </div>
                           <div className="md:col-span-2 flex justify-end">
                              <button
                                 onClick={handleLogin123}
                                 disabled={isVerifying123}
                                 className="px-6 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 hover:bg-brand-700 shadow-lg shadow-brand-500/20"
                              >
                                 {isVerifying123 ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
                                 验证并保存 OAuth
                              </button>
                           </div>
                        </div>

                        {/* 123 Folders */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 bg-orange-50/30 dark:bg-orange-900/10 p-6 rounded-xl border-[0.5px] border-orange-100 dark:border-orange-900/50">
                           <div>
                              <label className="flex items-center text-xs font-bold text-slate-500 uppercase mb-3">123 源目录 (待整理)</label>
                              <div className="flex gap-3">
                                 <div className="flex-1 px-4 py-3 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-800/50 text-slate-700 dark:text-slate-300 text-sm flex items-center gap-3">
                                    <FolderInput size={20} className="text-orange-500" />
                                    {config.organize.sourceDirName123 || '根目录'}
                                 </div>
                                 <button onClick={() => { setSelectorTarget('source123'); setFileSelectorOpen(true); }} className="px-4 py-3 bg-white dark:bg-slate-700 border-[0.5px] border-slate-300/50 dark:border-slate-600/50 hover:border-orange-500 rounded-lg text-sm font-medium shadow-sm transition-all">选择</button>
                              </div>
                           </div>
                           <div>
                              <label className="flex items-center text-xs font-bold text-slate-500 uppercase mb-3">123 目标目录 (已整理)</label>
                              <div className="flex gap-3">
                                 <div className="flex-1 px-4 py-3 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-800/50 text-slate-700 dark:text-slate-300 text-sm flex items-center gap-3">
                                    <FolderOutput size={20} className="text-green-500" />
                                    {config.organize.targetDirName123 || '根目录'}
                                 </div>
                                 <button onClick={() => { setSelectorTarget('target123'); setFileSelectorOpen(true); }} className="px-4 py-3 bg-white dark:bg-slate-700 border-[0.5px] border-slate-300/50 dark:border-slate-600/50 hover:border-green-500 rounded-lg text-sm font-medium shadow-sm transition-all">选择</button>
                              </div>
                           </div>
                        </div>
                     </div>
                  )}
               </div>
            </section>

            {/* Shared Rule Engine */}
            <section className={`${glassCardClass} xl:col-span-2 animate-in fade-in slide-in-from-bottom-2 duration-300`}>
               <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between bg-slate-50/50 dark:bg-slate-900/50">
                  <div className="flex items-center gap-3">
                     <div className="p-2 bg-indigo-50 dark:bg-indigo-900/20 rounded-lg text-indigo-600 dark:text-indigo-400 shadow-inner">
                        <Film size={20} />
                     </div>
                     <h3 className="font-bold text-slate-700 dark:text-slate-200 text-base">分类与重命名规则 (TMDB 共享)</h3>
                  </div>
               </div>

               <div className="p-6 space-y-8">
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
                                    <option value="gemini">Google Gemini 🆓</option>
                                    <option value="deepseek">DeepSeek 深度求索</option>
                                    <option value="zhipu">智谱 GLM 🆓</option>
                                    <option value="moonshot">月之暗面 (Kimi)</option>
                                    <option value="groq">Groq (极速推理) 🆓</option>
                                    <option value="qwen">通义千问 (阿里)</option>
                                    <option value="siliconflow">SiliconFlow 硅基流动 🆓</option>
                                    <option value="openrouter">OpenRouter 🆓</option>
                                    <option value="custom">自定义 (OpenAI 兼容)</option>
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
                                    placeholder={AI_PRESETS[config.organize.ai.provider]?.baseUrl || 'https://api.openai.com/v1'}
                                    className={inputClass}
                                 />
                              </div>
                              <div>
                                 <label className="block text-xs font-bold text-slate-500 uppercase mb-2">模型名称</label>
                                 <input
                                    type="text"
                                    value={config.organize.ai.model}
                                    onChange={(e) => updateAiConfig('model', e.target.value)}
                                    placeholder={AI_PRESETS[config.organize.ai.provider]?.model || 'gpt-4o-mini'}
                                    className={inputClass}
                                 />
                              </div>
                           </div>
                        )}
                     </div>

                     {/* Global Renaming Settings */}
                     <div className="mb-8 grid grid-cols-1 gap-8 border-b-[0.5px] border-slate-100 dark:border-slate-700/50 pb-8">
                        <div className="flex items-center justify-between">
                           <label className="text-sm font-bold text-slate-600 dark:text-slate-400">强制赋予 TMDB ID (文件夹名附加 {`{tmdb-id}`})</label>
                           <input
                              type="checkbox"
                              checked={config.organize.rename.addTmdbIdToFolder}
                              onChange={(e) => updateRenameRule('addTmdbIdToFolder', e.target.checked)}
                              className="w-5 h-5 rounded text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                           />
                        </div>

                        <div className="flex justify-between items-center pt-4 border-t border-slate-100 dark:border-slate-800/50">
                           <label className="text-sm font-bold text-slate-600 dark:text-slate-400">重命名模板配置</label>
                           <button
                              onClick={handleRestoreRenameTemplates}
                              className="text-xs text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300 flex items-center gap-1 px-2 py-1 rounded hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors"
                           >
                              <RotateCcw size={12} /> 恢复预设模板
                           </button>
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
         </div>

         {/* Edit Rule Modal */}
         {
            editingRuleId && tempRule && (
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
            )
         }

         <FileSelector
            isOpen={fileSelectorOpen}
            onClose={() => setFileSelectorOpen(false)}
            onSelect={handleDirSelect}
            title={`选择 ${selectorTarget?.includes('target') ? '存放目录' : selectorTarget?.includes('source') ? '源目录' : '下载目录'}`}
            cloudType={selectorTarget?.includes('123') ? '123' : '115'}
         />

         {/* 整理进程日志弹窗 */}
         <OrganizeLogs
            isOpen={showOrganizeLogs}
            onClose={() => setShowOrganizeLogs(false)}
         />
      </div >
   );
};