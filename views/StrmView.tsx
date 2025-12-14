
import React, { useState, useEffect } from 'react';
import { AppConfig, StrmConfig } from '../types';
import { api } from '../services/api';
import { Save, RefreshCw, HardDrive, Globe, Cloud, Zap, Server, Network, Lock, Play } from 'lucide-react';
import { SensitiveInput } from '../components/SensitiveInput';
import { FileSelector } from '../components/FileSelector';

const DEFAULT_STRM_CONFIG: StrmConfig = {
  enabled: false,
  outputDir: '/strm',
  sourceCid115: '0',
  urlPrefix115: '',
  sourceDir123: '/',
  urlPrefix123: '',
  sourcePathOpenList: '/',
  urlPrefixOpenList: '',
  webdav: {
    enabled: false,
    port: '18080',
    username: 'admin',
    password: '',
    readOnly: true
  }
};

export const StrmView: React.FC = () => {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [toast, setToast] = useState<string | null>(null);
  const [generating, setGenerating] = useState<string | null>(null);

  // File Selector
  const [fileSelectorOpen, setFileSelectorOpen] = useState(false);
  const [activeModule, setActiveModule] = useState<'115' | '123' | 'openlist' | null>(null);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    setIsLoading(true);
    try {
      const data = await api.getConfig();
      setConfig(data);
    } catch (e) {
      // 使用默认配置
      setConfig({ strm: DEFAULT_STRM_CONFIG } as AppConfig);
    } finally {
      setIsLoading(false);
    }
  };

  const updateStrm = (key: string, value: any) => {
    if (!config) return;
    setConfig(prev => prev ? ({
      ...prev,
      strm: { ...prev.strm, [key]: value }
    }) : null);
  };

  const updateWebdav = (key: string, value: any) => {
    if (!config) return;
    setConfig(prev => prev ? ({
      ...prev,
      strm: {
        ...prev.strm,
        webdav: { ...prev.strm.webdav, [key]: value }
      }
    }) : null);
  };

  const handleSave = async () => {
    if (!config) return;
    setIsSaving(true);
    try {
      await api.saveConfig(config);
      setToast('STRM 生成配置已保存');
    } catch (e) {
      setToast('保存失败');
    } finally {
      setIsSaving(false);
      setTimeout(() => setToast(null), 3000);
    }
  };

  const handleGenerate = async (type: string) => {
    setGenerating(type);
    setToast(`正在生成 ${type} STRM 文件...`);
    try {
      const generConfig = {
        type,
        sourceCid: config?.strm?.[`sourceCid${type}` as keyof any] || '0',
        outputDir: config?.strm?.outputDir || '/strm'
      };
      await api.generateStrmJob(type, generConfig);
      setGenerating(null);
      setToast(`${type} STRM 生成任务已提交`);
    } catch (e) {
      setGenerating(null);
      setToast(`${type} STRM 生成失败`);
    }
    setTimeout(() => setToast(null), 3000);
  };

  const openSelector = (module: '115' | '123' | 'openlist') => {
    setActiveModule(module);
    setFileSelectorOpen(true);
  };

  const handleFileSelect = (id: string, name: string) => {
    if (activeModule === '115') updateStrm('sourceCid115', id);
    if (activeModule === '123') updateStrm('sourceDir123', id === '0' ? '/' : `/${name}`);
    if (activeModule === 'openlist') updateStrm('sourcePathOpenList', id === '0' ? '/' : `/${name}`);
  };

  const fillLocalIp = (key: string, port: string, suffix: string) => {
    const ip = window.location.hostname;
    updateStrm(key, `http://${ip}:${port}${suffix}`);
  };

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500 gap-2 bg-slate-50 dark:bg-slate-900">
        <RefreshCw className="animate-spin" /> 正在加载配置...
      </div>
    );
  }

  if (!config) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500 gap-2 bg-slate-50 dark:bg-slate-900">
        配置加载失败
      </div>
    );
  }

  const glassCardClass = "bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border-[0.5px] border-white/40 dark:border-white/10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.2)] ring-1 ring-white/50 dark:ring-white/5 inset";
  const inputClass = "w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-slate-800 dark:text-slate-100 font-mono text-sm backdrop-blur-sm shadow-inner focus:ring-2 outline-none transition-all";
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
        <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight drop-shadow-sm">STRM 生成</h2>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

        {/* Global Config */}
        <div className="lg:col-span-2 bg-slate-50/80 dark:bg-slate-800/50 backdrop-blur-md rounded-xl border-[0.5px] border-slate-200/50 dark:border-slate-700/50 shadow-sm overflow-hidden ring-1 ring-white/20 inset">
          <div className="p-6 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <label className="text-sm font-semibold text-slate-700 dark:text-slate-300">本地输出目录</label>
              <input
                type="text"
                value={config.strm.outputDir}
                onChange={(e) => updateStrm('outputDir', e.target.value)}
                className={`${inputClass} w-96 focus:ring-teal-500`}
              />
            </div>
            <div className="flex items-center gap-3 ml-auto">
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
        </div>

        {/* 115 Module */}
        <section className={`${glassCardClass} overflow-hidden transition-all duration-300`}>
          <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <HardDrive size={18} className="text-orange-500" />
              <h3 className="font-bold text-slate-700 dark:text-slate-200">115 网盘模块</h3>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleGenerate('115')}
                disabled={generating === '115'}
                className={`${actionBtnClass} bg-orange-50 text-orange-600 hover:bg-orange-100 dark:bg-orange-900/20 dark:text-orange-400 dark:hover:bg-orange-900/40 disabled:opacity-50`}
              >
                {generating === '115' ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
                立即生成
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className={`${actionBtnClass} bg-orange-50 text-orange-600 hover:bg-orange-100 dark:bg-orange-900/20 dark:text-orange-400 dark:hover:bg-orange-900/40 disabled:opacity-50`}
              >
                {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                保存设置
              </button>
            </div>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-2">STRM生成文件夹</label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={config.strm.sourceCid115}
                  onChange={(e) => updateStrm('sourceCid115', e.target.value)}
                  className={`${inputClass} flex-1 focus:ring-orange-500`}
                />
                <button onClick={() => openSelector('115')} className="px-4 py-2.5 bg-slate-100/50 dark:bg-slate-700/50 rounded-lg text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors backdrop-blur-sm border-[0.5px] border-slate-200/50">选择</button>
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-xs font-bold text-slate-500 uppercase">路径前缀</label>
                <button onClick={() => fillLocalIp('urlPrefix115', '9527', '/d/115')} className="text-xs text-brand-600 hover:text-brand-500 flex items-center gap-1 font-medium"><Zap size={12} /> 自动填入</button>
              </div>
              <input
                type="text"
                value={config.strm.urlPrefix115}
                onChange={(e) => updateStrm('urlPrefix115', e.target.value)}
                className={`${inputClass} focus:ring-orange-500`}
              />
            </div>
          </div>
        </section>

        {/* 123 Module */}
        <section className={`${glassCardClass} overflow-hidden transition-all duration-300`}>
          <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Cloud size={18} className="text-blue-500" />
              <h3 className="font-bold text-slate-700 dark:text-slate-200">123 云盘模块</h3>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleGenerate('123')}
                disabled={generating === '123'}
                className={`${actionBtnClass} bg-blue-50 text-blue-600 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400 dark:hover:bg-blue-900/40 disabled:opacity-50`}
              >
                {generating === '123' ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
                立即生成
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className={`${actionBtnClass} bg-blue-50 text-blue-600 hover:bg-blue-100 dark:bg-blue-900/20 dark:text-blue-400 dark:hover:bg-blue-900/40 disabled:opacity-50`}
              >
                {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                保存设置
              </button>
            </div>
          </div>
          <div className="p-6 space-y-6">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-2">STRM生成文件夹</label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={config.strm.sourceDir123}
                  onChange={(e) => updateStrm('sourceDir123', e.target.value)}
                  className={`${inputClass} flex-1 focus:ring-blue-500`}
                />
                <button onClick={() => openSelector('123')} className="px-4 py-2.5 bg-slate-100/50 dark:bg-slate-700/50 rounded-lg text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors backdrop-blur-sm border-[0.5px] border-slate-200/50">选择</button>
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-xs font-bold text-slate-500 uppercase">路径前缀</label>
                <button onClick={() => fillLocalIp('urlPrefix123', '9527', '/d/123')} className="text-xs text-brand-600 hover:text-brand-500 flex items-center gap-1 font-medium"><Zap size={12} /> 自动填入</button>
              </div>
              <input
                type="text"
                value={config.strm.urlPrefix123}
                onChange={(e) => updateStrm('urlPrefix123', e.target.value)}
                className={`${inputClass} focus:ring-blue-500`}
              />
            </div>
          </div>
        </section>

        {/* OpenList Module */}
        <section className={`${glassCardClass} overflow-hidden transition-all duration-300`}>
          <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Globe size={18} className="text-cyan-500" />
              <h3 className="font-bold text-slate-700 dark:text-slate-200">OpenList 挂载模块</h3>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleGenerate('openlist')}
                disabled={generating === 'openlist'}
                className={`${actionBtnClass} bg-cyan-50 text-cyan-600 hover:bg-cyan-100 dark:bg-cyan-900/20 dark:text-cyan-400 dark:hover:bg-cyan-900/40 disabled:opacity-50`}
              >
                {generating === 'openlist' ? <RefreshCw size={12} className="animate-spin" /> : <Play size={12} />}
                立即生成
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className={`${actionBtnClass} bg-cyan-50 text-cyan-600 hover:bg-cyan-100 dark:bg-cyan-900/20 dark:text-cyan-400 dark:hover:bg-cyan-900/40 disabled:opacity-50`}
              >
                {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />}
                保存设置
              </button>
            </div>
          </div>
          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-2">STRM生成文件夹</label>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={config.strm.sourcePathOpenList}
                  onChange={(e) => updateStrm('sourcePathOpenList', e.target.value)}
                  className={`${inputClass} flex-1 focus:ring-cyan-500`}
                />
                <button onClick={() => openSelector('openlist')} className="px-4 py-2.5 bg-slate-100/50 dark:bg-slate-700/50 rounded-lg text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors backdrop-blur-sm border-[0.5px] border-slate-200/50">选择</button>
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center mb-2">
                <label className="block text-xs font-bold text-slate-500 uppercase">路径前缀</label>
                <button onClick={() => fillLocalIp('urlPrefixOpenList', '5244', '/d')} className="text-xs text-brand-600 hover:text-brand-500 flex items-center gap-1 font-medium"><Zap size={12} /> 自动填入</button>
              </div>
              <input
                type="text"
                value={config.strm.urlPrefixOpenList}
                onChange={(e) => updateStrm('urlPrefixOpenList', e.target.value)}
                className={`${inputClass} focus:ring-cyan-500`}
              />
            </div>
          </div>
        </section>

        {/* WebDAV Server */}
        <section className={`${glassCardClass} overflow-hidden transition-all duration-300`}>
          <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Network size={18} className="text-teal-500" />
              <h3 className="font-bold text-slate-700 dark:text-slate-200">WebDAV 服务 (挂载 STRM)</h3>
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

          <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="md:col-span-2 bg-teal-50/50 dark:bg-teal-900/10 p-3 rounded-xl border-[0.5px] border-teal-100/50 dark:border-teal-900/30 text-sm text-teal-700 dark:text-teal-400 mb-2 flex items-center gap-3 backdrop-blur-sm shadow-inner">
              <Server size={18} />
              <span>
                WebDAV 挂载地址: <strong>http://{window.location.hostname}:18080/dav</strong>，映射目录: <code className="bg-teal-100 dark:bg-teal-900/30 px-1.5 py-0.5 rounded text-xs">/strm</code>
              </span>
            </div>

            <div className="flex items-end mb-3">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="webdavReadOnly"
                  checked={config.strm.webdav?.readOnly || false}
                  onChange={(e) => updateWebdav('readOnly', e.target.checked)}
                  className="w-4 h-4 rounded text-teal-600 focus:ring-teal-500"
                />
                <label htmlFor="webdavReadOnly" className="text-sm font-medium text-slate-700 dark:text-slate-300 cursor-pointer select-none flex items-center gap-2">
                  <Lock size={16} className="text-slate-400" />
                  只读模式
                </label>
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-2">用户名</label>
              <input
                type="text"
                value={config.strm.webdav?.username}
                onChange={(e) => updateWebdav('username', e.target.value)}
                className={`${inputClass} focus:ring-teal-500`}
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase mb-2">密码</label>
              <SensitiveInput
                value={config.strm.webdav?.password || ''}
                onChange={(e) => updateWebdav('password', e.target.value)}
                className={`${inputClass} focus:ring-teal-500`}
              />
            </div>
          </div>
        </section>
      </div>

      <FileSelector
        isOpen={fileSelectorOpen}
        onClose={() => setFileSelectorOpen(false)}
        onSelect={handleFileSelect}
        title={`选择 ${activeModule === '115' ? '115 网盘文件夹' : activeModule === '123' ? '123 云盘文件夹' : 'OpenList 目录'}`}
        cloudType={activeModule === '115' ? '115' : activeModule === '123' ? '123' : 'openlist'}
      />
    </div>
  );
};
