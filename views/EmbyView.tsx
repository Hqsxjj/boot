import React, { useState, useEffect } from 'react';
import { AppConfig } from '../types';
import { api } from '../services/api';
import { Save, RefreshCw, Clapperboard, BarChart3, Clock, Zap, Bell, Copy, FileWarning, Search, CheckCircle2, Image, Download, Palette } from 'lucide-react';
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

    // 缺集扫描进度状态
    const [scanProgress, setScanProgress] = useState<{ current: number; total: number; currentShow: string } | null>(null);

    // Cover Generator State
    const [coverLibraries, setCoverLibraries] = useState<Array<{ id: string; name: string; type: string }>>([]);
    const [coverThemes, setCoverThemes] = useState<Array<{ index: number; name: string; colors: string[] }>>([]);
    const [selectedLibrary, setSelectedLibrary] = useState<string>('');
    const [coverTitle, setCoverTitle] = useState('电影收藏');
    const [coverSubtitle, setCoverSubtitle] = useState('MOVIE COLLECTION');
    const [selectedTheme, setSelectedTheme] = useState(0);
    const [coverFormat, setCoverFormat] = useState<'png' | 'gif'>('png');
    const [coverPreview, setCoverPreview] = useState<string | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isLoadingLibraries, setIsLoadingLibraries] = useState(false);
    // 参数滑块 (匹配 Python Tkinter 参数)
    const [titleSize, setTitleSize] = useState(172);     // 主标题文字大小 9.0vw (1920*0.09 ~= 172)
    const [offsetX, setOffsetX] = useState(40);          // 海报水平位移 (X) 默认 40
    const [posterScale, setPosterScale] = useState(32);  // 整体缩放比例 32% (保持不变)
    const [vAlign, setVAlign] = useState(60);            // 标题纵向对齐 60%
    const [spacing, setSpacing] = useState(1.0);         // 堆叠间距系数
    const [angleScale, setAngleScale] = useState(1.0);   // 旋转角度系数
    const [useBackdrop, setUseBackdrop] = useState(false); // 是否使用横幅背景

    // 批量选择 (用 Set 存储选中的 ID)
    const [batchSelection, setBatchSelection] = useState<Set<string>>(new Set());

    // 加载配置
    useEffect(() => {
        const initConfig = async () => {
            try {
                const data = await api.getConfig();
                if (data?.emby) {
                    setConfig(data);
                    // 如果获取到了配置，并行测试连接和加载媒体库 (不阻塞)
                    if (data.emby.serverUrl && data.emby.apiKey) {
                        // 并行执行，不等待结果
                        testConnectionOnly();
                        loadCoverData();
                    }
                } else {
                    setConfig(DEFAULT_CONFIG);
                }
            } catch (err) {
                console.error("加载配置失败:", err);
                setConfig(DEFAULT_CONFIG);
            }
        };

        initConfig();
    }, []);

    // 仅测试连接 (不保存配置，用于初始化)
    const testConnectionOnly = async () => {
        try {
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

    // 测试 Emby 连接 (保存配置后测试，用于手动保存)
    const checkConnection = async (cfg: AppConfig = config!) => {
        if (!cfg?.emby?.serverUrl) return;
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

    // 批量生成并替换封面 (后台静默处理)
    const handleBatchApply = async () => {
        if (batchSelection.size === 0) {
            setToast('请至少选择一个媒体库');
            return;
        }

        if (!confirm(`确定要为选中的 ${batchSelection.size} 个媒体库生成并覆盖现有封面吗？此操作不可逆。`)) {
            return;
        }

        setIsGenerating(true);
        setToast('正在后台处理封面生成，请稍候...');

        try {
            const libraryIds = Array.from(batchSelection);

            // 构建配置参数
            const coverConfig = {
                titleSize,
                offsetX,
                posterScale,
                vAlign,
                spacing,
                angleScale,
                useBackdrop,
                format: coverFormat,
                theme: selectedTheme
            };

            // 一次性提交所有库，后端逐个处理并记录日志
            const result = await api.batchApplyCovers(libraryIds, coverConfig) as any;

            if (result.success) {
                setToast(`处理完成: 成功 ${result.success_count} / ${result.processed}`);
            } else {
                setToast(`处理失败: ${result.error || '未知错误'}`);
            }
        } catch (e: any) {
            const errorMsg = e.response?.data?.error || e.message || '网络错误';
            setToast(`操作失败: ${errorMsg}`);
        } finally {
            setIsGenerating(false);
            setTimeout(() => setToast(null), 5000);
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
        } catch (e: any) {
            const errorMsg = e.response?.data?.error || e.message || '保存失败';
            console.error("Config save failed:", e);
            setToast(`保存失败: ${errorMsg}`);
        } finally {
            setIsSaving(false);
        }
    };

    // 扫描缺集 (按电视剧逐个处理)
    const handleScan = async () => {
        setIsScanning(true);
        setMissingData([]);  // 清空之前的结果

        try {
            // 1. 获取所有电视剧列表
            const listResult = await api.getSeriesList();
            if (!listResult.success || !listResult.data) {
                setToast(`获取剧集列表失败: ${(listResult as any).error || '未知错误'}`);
                setIsScanning(false);
                return;
            }

            const seriesList = listResult.data;
            const total = seriesList.length;

            if (total === 0) {
                setToast('未找到任何电视剧');
                setIsScanning(false);
                return;
            }

            let foundMissingCount = 0;

            // 2. 逐个扫描每部剧
            for (let i = 0; i < seriesList.length; i++) {
                const series = seriesList[i];

                // 更新进度
                setScanProgress({ current: i + 1, total, currentShow: series.name });

                try {
                    const scanResult = await api.scanSingleSeries(series.id);

                    if (scanResult.success && scanResult.data && scanResult.data.length > 0) {
                        // 有缺集，追加到结果列表
                        setMissingData(prev => [...prev, ...scanResult.data]);
                        foundMissingCount += scanResult.data.length;
                    }
                } catch (err) {
                    console.error(`扫描 ${series.name} 失败:`, err);
                }

                // 短暂延迟避免请求过快
                await new Promise(resolve => setTimeout(resolve, 100));
            }

            setToast(`扫描完成: 共检查 ${total} 部剧，发现 ${foundMissingCount} 个缺集`);
        } catch (e: any) {
            const errorMsg = e?.response?.data?.error || e?.message || '网络错误';
            setToast(`扫描失败: ${errorMsg}`);
            console.error('Scan error:', e);
        } finally {
            setIsScanning(false);
            setScanProgress(null);
            setTimeout(() => setToast(null), 4000);
        }
    };

    // 辅助更新函数
    const updateNested = (section: keyof AppConfig, key: string, value: any) => {
        if (!config) return;
        setConfig(prev => prev ? ({
            ...prev,
            [section]: { ...(prev[section] as any), [key]: value }
        }) : null);
    };

    const updateNotifications = (key: string, value: any) => {
        if (!config) return;
        setConfig(prev => prev ? ({
            ...prev,
            emby: {
                ...prev.emby,
                notifications: { ...prev.emby.notifications, [key]: value }
            }
        }) : null);
    };

    const updateMissing = (key: string, value: any) => {
        if (!config) return;
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

    const copyWebhook = async () => {
        const port = window.location.port || '18080';
        const webhookUrl = `http://${window.location.hostname}:${port}/api/emby/webhook`;

        try {
            // 尝试使用现代 Clipboard API
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(webhookUrl);
                setToast('Emby Webhook 地址已复制');
            } else {
                // Fallback: 使用 execCommand
                const textArea = document.createElement('textarea');
                textArea.value = webhookUrl;
                textArea.style.position = 'fixed';
                textArea.style.left = '-9999px';
                textArea.style.top = '0';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();

                const success = document.execCommand('copy');
                document.body.removeChild(textArea);

                if (success) {
                    setToast('Emby Webhook 地址已复制');
                } else {
                    setToast('复制失败，请手动复制');
                }
            }
        } catch (err) {
            console.error('复制失败:', err);
            // 最终 fallback: 显示提示让用户手动复制
            setToast('请手动复制上方地址');
        }
        setTimeout(() => setToast(null), 2000);
    };

    // Cover Generator Functions
    const loadCoverData = async () => {
        setIsLoadingLibraries(true);
        try {
            const [themesRes, librariesRes] = await Promise.all([
                api.getCoverThemes(),
                api.getCoverLibraries()
            ]);
            if (themesRes.success) setCoverThemes(themesRes.data);
            if (librariesRes.success) {
                setCoverLibraries(librariesRes.data);
                if (librariesRes.data.length > 0) {
                    const firstLib = librariesRes.data[0];
                    setSelectedLibrary(firstLib.id);
                    // 自动填充标题
                    setCoverTitle(firstLib.name);
                    const typeMap: Record<string, string> = {
                        'movies': 'MOVIE COLLECTION',
                        'tvshows': 'TV SHOWS',
                        'music': 'MUSIC COLLECTION',
                        'homevideos': 'HOME VIDEOS',
                        'books': 'BOOK COLLECTION',
                        'photos': 'PHOTO ALBUM',
                        'musicvideos': 'MUSIC VIDEOS'
                    };
                    setCoverSubtitle(typeMap[firstLib.type?.toLowerCase()] || firstLib.type?.toUpperCase() || 'MEDIA COLLECTION');
                }
            }
        } catch (e) {
            console.error('加载封面生成器数据失败:', e);
        } finally {
            setIsLoadingLibraries(false);
        }
    };

    const handleGenerateCover = async () => {
        if (!selectedLibrary) {
            setToast('请先选择媒体库');
            setTimeout(() => setToast(null), 3000);
            return;
        }
        setIsGenerating(true);
        try {
            // 构建配置参数
            const coverConfig = {
                title: coverTitle,
                subtitle: coverSubtitle,
                titleSize,
                offsetX,
                posterScale,
                vAlign,
                spacing,
                angleScale,
                useBackdrop,
                format: coverFormat,
                theme: selectedTheme
            };

            const result = await api.generateCover({
                libraryId: selectedLibrary,
                config: coverConfig
            });
            if (result.success) {
                setCoverPreview(result.data.image);
                setToast('封面生成成功！');
            } else {
                setToast(result.error || '生成失败');
            }
            setTimeout(() => setToast(null), 3000);
        } catch (e) {
            setToast('生成失败');
            setTimeout(() => setToast(null), 3000);
        } finally {
            setIsGenerating(false);
        }
    };

    const downloadCover = () => {
        if (!coverPreview) return;
        const link = document.createElement('a');
        link.href = coverPreview;
        link.download = `emby-cover.${coverFormat}`;
        link.click();
    };

    // === Loading 状态判断 ===
    // 只有当 config 真的是 null 时才显示 Loading
    // 现在因为有了 catch -> setConfig(DEFAULT)，除非 JS 报错，否则几乎不会一直卡在这里
    if (!config) return <div className="p-10 flex justify-center text-slate-500"><RefreshCw className="animate-spin" /></div>;

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


            {/* 缺集扫描进度显示 */}
            {scanProgress && (
                <div className="fixed top-6 left-1/2 -translate-x-1/2 bg-purple-600/95 backdrop-blur-md text-white px-8 py-4 rounded-xl shadow-2xl z-50 border-[0.5px] border-purple-500/50 min-w-[300px]">
                    <div className="flex items-center gap-3 mb-2">
                        <RefreshCw size={18} className="animate-spin" />
                        <span className="font-bold">正在扫描缺集...</span>
                    </div>
                    <div className="text-sm opacity-90 mb-2">
                        当前: <span className="font-medium">{scanProgress.currentShow}</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="flex-1 bg-purple-800/50 rounded-full h-2 overflow-hidden">
                            <div
                                className="bg-white h-full transition-all duration-300 rounded-full"
                                style={{ width: `${(scanProgress.current / scanProgress.total) * 100}%` }}
                            />
                        </div>
                        <span className="text-xs font-mono">{scanProgress.current}/{scanProgress.total}</span>
                    </div>
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
                            <div className={`flex items-center gap-2 px-3 py-1 rounded-full border-[0.5px] ${connectionStatus.success === true ? 'bg-green-50/50 border-green-200 dark:bg-green-900/10 dark:border-green-800' :
                                connectionStatus.success === false ? 'bg-red-50/50 border-red-200 dark:bg-red-900/10 dark:border-red-800' :
                                    'bg-slate-100/50 border-slate-200 dark:bg-slate-800/50 dark:border-slate-700'
                                }`}>
                                <div className={`w-1.5 h-1.5 rounded-full ${connectionStatus.success === true ? 'bg-green-500 animate-pulse' :
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
                                <label className="text-xs font-bold text-slate-500 uppercase flex items-center gap-1"><Zap size={12} /> Emby Webhook 回调地址</label>
                                <button onClick={copyWebhook} className="text-xs text-sky-600 hover:text-sky-500 flex items-center gap-1 font-bold"><Copy size={12} /> 复制</button>
                            </div>
                            <code className="block w-full px-3 py-2 bg-white/50 dark:bg-slate-900/50 rounded-lg text-xs font-mono text-slate-600 dark:text-slate-400 break-all border-[0.5px] border-slate-200/50 dark:border-slate-800/50 select-all shadow-inner">
                                http://{window.location.hostname}:{window.location.port || '18080'}/api/emby/webhook
                            </code>
                            <p className="text-[10px] text-slate-400 mt-2">将此地址填入 Emby 服务器的 Webhook 设置中，可接收新媒体入库、播放开始/停止等通知</p>
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
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-2 flex items-center gap-1"><Clock size={12} /> 检测计划 (Cron 表达式)</label>
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
                                        {isScanning ? <RefreshCw className="animate-spin" size={12} /> : <Search size={12} />}
                                        {isScanning ? "扫描中..." : "立即检测"}
                                    </button>
                                </div>

                                <div className="overflow-x-auto max-h-[500px] overflow-y-auto scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-600">
                                    {missingData.length === 0 && !isScanning && (
                                        <div className="p-8 text-center text-slate-400 text-xs">
                                            暂无数据，请点击右上角"立即检测"
                                        </div>
                                    )}

                                    {missingData.length > 0 && (
                                        <table className="w-full text-left text-sm">
                                            <thead className="text-slate-500 dark:text-slate-400 bg-white/20 dark:bg-white/5 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 sticky top-0 backdrop-blur-sm">
                                                <tr>
                                                    <th className="p-4 font-medium w-24">海报</th>
                                                    <th className="p-4 font-medium min-w-[140px]">剧集名称</th>
                                                    <th className="p-4 font-medium w-24 text-center">季</th>
                                                    <th className="p-4 font-medium w-24 text-center">总集数</th>
                                                    <th className="p-4 font-medium w-24 text-center">已有</th>
                                                    <th className="p-4 font-medium text-red-500 min-w-[140px]">缺失集数</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                                {missingData.map((item) => (
                                                    <tr key={item.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/30 transition-colors">
                                                        <td className="p-4">
                                                            <div className="w-16 h-24 bg-gradient-to-br from-slate-200 to-slate-300 dark:from-slate-700 dark:to-slate-800 rounded-lg overflow-hidden shadow-lg flex-shrink-0">
                                                                {item.poster ? (
                                                                    <img src={item.poster} alt="poster" className="w-full h-full object-cover" />
                                                                ) : (
                                                                    <div className="w-full h-full flex items-center justify-center text-slate-400 text-xs">N/A</div>
                                                                )}
                                                            </div>
                                                        </td>
                                                        <td className="p-4">
                                                            <span className="font-semibold text-slate-800 dark:text-slate-200 text-base">{item.name}</span>
                                                        </td>
                                                        <td className="p-4 text-center">
                                                            <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-full bg-sky-100 dark:bg-sky-900/30 text-sky-700 dark:text-sky-300 text-xs font-bold">
                                                                S{String(item.season).padStart(2, '0')}
                                                            </span>
                                                        </td>
                                                        <td className="p-4 text-center text-slate-600 dark:text-slate-400 font-medium text-base">{item.totalEp}</td>
                                                        <td className="p-4 text-center">
                                                            <span className="inline-flex items-center justify-center px-2 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-xs font-bold">
                                                                {item.localEp}
                                                            </span>
                                                        </td>
                                                        <td className="p-4">
                                                            <span className="text-red-500 dark:text-red-400 font-mono font-bold text-sm bg-red-50 dark:bg-red-900/20 px-3 py-1.5 rounded">
                                                                {item.missing}
                                                            </span>
                                                        </td>
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

                {/* Cover Generator */}
                <section className={`${glassCardClass} overflow-hidden xl:col-span-2`}>
                    <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-amber-50 dark:bg-amber-900/20 rounded-lg text-amber-600 dark:text-amber-400 shadow-inner">
                                <Image size={20} />
                            </div>
                            <h3 className="font-bold text-slate-700 dark:text-slate-200">封面图生成器</h3>
                        </div>
                        <div className="flex items-center gap-3 hidden">
                            <button
                                onClick={loadCoverData}
                                disabled={isLoadingLibraries}
                                className={`${actionBtnClass} bg-amber-50 text-amber-600 hover:bg-amber-100 dark:bg-amber-900/20 dark:text-amber-400 dark:hover:bg-amber-900/40 disabled:opacity-50`}
                            >
                                {isLoadingLibraries ? <RefreshCw className="animate-spin" size={12} /> : <RefreshCw size={12} />}
                                加载媒体库
                            </button>
                        </div>
                    </div>

                    <div className="p-6 transition-all duration-300">
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                            {/* Left: Controls */}
                            <div className="space-y-5">
                                <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-2 flex items-center justify-between">
                                        <span>选择媒体库 (已选 {batchSelection.size})</span>
                                        <button
                                            onClick={() => {
                                                if (batchSelection.size === coverLibraries.length) {
                                                    setBatchSelection(new Set());
                                                } else {
                                                    setBatchSelection(new Set(coverLibraries.map(l => l.id)));
                                                }
                                            }}
                                            className="text-amber-500 hover:text-amber-600 text-xs"
                                        >
                                            {batchSelection.size === coverLibraries.length ? '全不选' : '全选'}
                                        </button>
                                    </label>
                                    <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden max-h-[180px] overflow-y-auto">
                                        {coverLibraries.length === 0 && (
                                            <div className="p-4 text-center text-slate-400 text-sm">请先点击"加载媒体库"</div>
                                        )}
                                        {coverLibraries.map(lib => (
                                            <label
                                                key={lib.id}
                                                className={`flex items-center gap-3 p-3 hover:bg-slate-50 dark:hover:bg-slate-800 cursor-pointer border-b last:border-0 border-slate-100 dark:border-slate-800 transition-colors ${selectedLibrary === lib.id ? 'bg-amber-50 dark:bg-amber-900/10' : ''}`}
                                                onClick={() => {
                                                    // 防止触发两次
                                                    // 点击行也能切换预览选中态，但 checkbox 是独立的
                                                }}
                                            >
                                                <input
                                                    type="checkbox"
                                                    checked={batchSelection.has(lib.id)}
                                                    onChange={(e) => {
                                                        const newSet = new Set(batchSelection);
                                                        if (e.target.checked) {
                                                            newSet.add(lib.id);
                                                        } else {
                                                            newSet.delete(lib.id);
                                                        }
                                                        setBatchSelection(newSet);
                                                    }}
                                                    className="w-4 h-4 rounded text-amber-500 focus:ring-amber-500 border-slate-300 dark:border-slate-600"
                                                />
                                                <div
                                                    className="flex-1"
                                                    onClick={(e) => {
                                                        e.preventDefault(); // 防止 checkbox 联动

                                                        // 点击文字切换为当前预览对象
                                                        setSelectedLibrary(lib.id);
                                                        // 自动填充标题逻辑
                                                        setCoverTitle(lib.name);
                                                        const typeMap: Record<string, string> = {
                                                            'movies': 'MOVIE COLLECTION',
                                                            'tvshows': 'TV SHOWS',
                                                            'music': 'MUSIC COLLECTION',
                                                            'homevideos': 'HOME VIDEOS',
                                                            'books': 'BOOK COLLECTION',
                                                            'photos': 'PHOTO ALBUM',
                                                            'musicvideos': 'MUSIC VIDEOS'
                                                        };
                                                        const typeEn = typeMap[lib.type?.toLowerCase()] || lib.type?.toUpperCase() || 'MEDIA COLLECTION';
                                                        setCoverSubtitle(typeEn);
                                                    }}
                                                >
                                                    <div className="text-sm font-medium text-slate-700 dark:text-slate-200">{lib.name}</div>
                                                    <div className="text-xs text-slate-400">{lib.type || '未知类型'}</div>
                                                </div>
                                                {selectedLibrary === lib.id && <div className="w-2 h-2 rounded-full bg-amber-500"></div>}
                                            </label>
                                        ))}
                                    </div>
                                </div>

                                {/* 标题由媒体库自动填充，隐藏手动输入 */}

                                <div>
                                    <label className="block text-xs font-bold text-slate-500 uppercase mb-2 flex items-center gap-1">
                                        <Palette size={12} /> 主题配色
                                    </label>
                                    <div className="flex flex-wrap gap-2">
                                        <button
                                            key="auto"
                                            onClick={() => setSelectedTheme(-1)}
                                            className={`px-3 py-1 rounded-lg text-xs font-bold transition-all border ${selectedTheme === -1 ? 'bg-gradient-to-r from-pink-500 via-purple-500 to-indigo-500 text-white border-transparent ring-2 ring-offset-2 ring-purple-500' : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:border-purple-500'}`}
                                            title="自动从海报提取颜色"
                                        >
                                            自动混色
                                        </button>
                                        {coverThemes.map(theme => (
                                            <button
                                                key={theme.index}
                                                onClick={() => setSelectedTheme(theme.index)}
                                                className={`w-8 h-8 rounded-lg transition-all ${selectedTheme === theme.index ? 'ring-2 ring-offset-2 ring-amber-500 scale-110' : 'opacity-80 hover:opacity-100'}`}
                                                style={{ background: `linear-gradient(135deg, ${theme.colors[0]}, ${theme.colors[theme.colors.length - 1]})` }}
                                                title={theme.name}
                                            />
                                        ))}
                                    </div>
                                </div>

                                <div className="flex items-center gap-2">
                                    <input
                                        type="checkbox"
                                        id="useBackdrop"
                                        checked={useBackdrop}
                                        onChange={(e) => setUseBackdrop(e.target.checked)}
                                        className="w-4 h-4 rounded text-amber-500 focus:ring-amber-500 border-slate-300 dark:border-slate-600"
                                    />
                                    <label htmlFor="useBackdrop" className="text-xs font-bold text-slate-600 dark:text-slate-400 cursor-pointer select-none">
                                        使用媒体库横幅做背景 (Use Library Backdrop)
                                    </label>
                                </div>

                                {/* 参数滑块 - 匹配 Python Tkinter 参数 */}
                                <div className="space-y-4 pt-2 border-t border-slate-200 dark:border-slate-700">
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                                            主标题文字大小: {titleSize} (约 {(titleSize / 19.2).toFixed(1)}vw)
                                        </label>
                                        <input
                                            type="range"
                                            min={58}
                                            max={192}
                                            value={titleSize}
                                            onChange={(e) => setTitleSize(Number(e.target.value))}
                                            className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                                            海报水平位移 (X): {offsetX}
                                        </label>
                                        <input
                                            type="range"
                                            min={0}
                                            max={225}
                                            value={offsetX}
                                            onChange={(e) => setOffsetX(Number(e.target.value))}
                                            className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                                            整体缩放比例 (%): {posterScale}
                                        </label>
                                        <input
                                            type="range"
                                            min={25}
                                            max={35}
                                            value={posterScale}
                                            onChange={(e) => setPosterScale(Number(e.target.value))}
                                            className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                                            标题纵向对齐 (%): {vAlign}
                                        </label>
                                        <input
                                            type="range"
                                            min={5}
                                            max={65}
                                            value={vAlign}
                                            onChange={(e) => setVAlign(Number(e.target.value))}
                                            className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                                            堆叠间距系数: {spacing}x
                                        </label>
                                        <input
                                            type="range"
                                            min={0.5}
                                            max={2.0}
                                            step={0.1}
                                            value={spacing}
                                            onChange={(e) => setSpacing(Number(e.target.value))}
                                            className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-1">
                                            旋转角度系数: {angleScale}x
                                        </label>
                                        <input
                                            type="range"
                                            min={0.0}
                                            max={2.0}
                                            step={0.1}
                                            value={angleScale}
                                            onChange={(e) => setAngleScale(Number(e.target.value))}
                                            className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-lg appearance-none cursor-pointer accent-amber-500"
                                        />
                                    </div>
                                </div>

                                <div className="flex items-center gap-4">
                                    <div className="flex-1">
                                        <label className="block text-xs font-bold text-slate-500 uppercase mb-2">输出格式</label>
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => setCoverFormat('png')}
                                                className={`flex-1 px-4 py-2 rounded-lg text-sm font-bold transition-all ${coverFormat === 'png' ? 'bg-amber-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'}`}
                                            >
                                                PNG 静态
                                            </button>
                                            <button
                                                onClick={() => setCoverFormat('gif')}
                                                className={`flex-1 px-4 py-2 rounded-lg text-sm font-bold transition-all ${coverFormat === 'gif' ? 'bg-amber-500 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'}`}
                                            >
                                                GIF 动图
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                <div className="flex gap-3 pt-2">
                                    <button
                                        onClick={handleGenerateCover}
                                        disabled={isGenerating || !selectedLibrary}
                                        className="flex-1 px-4 py-3 bg-gradient-to-r from-amber-500 to-orange-500 text-white rounded-xl font-bold flex items-center justify-center gap-2 hover:from-amber-600 hover:to-orange-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-amber-500/20"
                                    >
                                        {isGenerating ? <RefreshCw className="animate-spin" size={16} /> : <Image size={16} />}
                                        {isGenerating ? '生成中...' : '生成当前预览'}
                                    </button>

                                    <button
                                        onClick={handleBatchApply}
                                        disabled={isGenerating || batchSelection.size === 0}
                                        className="flex-1 px-4 py-3 bg-gradient-to-r from-emerald-500 to-teal-500 text-white rounded-xl font-bold flex items-center justify-center gap-2 hover:from-emerald-600 hover:to-teal-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-emerald-500/20"
                                        title="为所有勾选的库生成并覆盖现有封面"
                                    >
                                        {isGenerating ? <RefreshCw className="animate-spin" size={16} /> : <Zap size={16} />}
                                        批量覆盖 ({batchSelection.size})
                                    </button>

                                    {coverPreview && (
                                        <button
                                            onClick={downloadCover}
                                            className="px-4 py-3 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-xl font-bold flex items-center gap-2 hover:bg-slate-200 dark:hover:bg-slate-700 transition-all"
                                        >
                                            <Download size={16} />
                                        </button>
                                    )}
                                </div>
                            </div>

                            {/* Right: Preview (16:9 Rounded Box) */}
                            <div className="bg-slate-100 dark:bg-slate-800/50 rounded-2xl p-6 border border-slate-200 dark:border-slate-700 flex items-center justify-center min-h-[400px]">
                                {coverPreview ? (
                                    <div className="relative w-full aspect-video rounded-xl overflow-hidden shadow-2xl ring-1 ring-black/10 group">
                                        <img
                                            src={coverPreview}
                                            alt="Cover Preview"
                                            className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                                        />
                                        {/* 模拟 Emby 选中态边框效果 (Hover) */}
                                        <div className="absolute inset-0 border-4 border-transparent group-hover:border-white/20 transition-colors pointer-events-none rounded-xl" />
                                    </div>
                                ) : (
                                    <div className="text-center text-slate-400">
                                        <Image size={48} className="mx-auto mb-2 opacity-50" />
                                        <p className="text-sm">选择媒体库并点击生成预览</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </section>

            </div>
        </div>
    );
};