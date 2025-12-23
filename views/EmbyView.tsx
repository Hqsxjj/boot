import React, { useState, useEffect, useRef } from 'react';
import { AppConfig } from '../types';
import { api } from '../services/api';
import {
    Save, RefreshCw, BarChart3, Clock, Zap, Bell, Copy, FileWarning, Search, CheckCircle2,
    Image, Download, Palette, Settings2, Library as LibraryIcon, Eye, Grid3X3, CloudUpload,
    Type, History, Server, Loader2
} from 'lucide-react';
import html2canvas from 'html2canvas';

// === Shared Constants & Components for Studio Generator ===

const DEFAULT_POSTERS = [
    'https://images.unsplash.com/photo-1594908900066-3f47337549d8?auto=format&fit=crop&q=80&w=1200',
    'https://images.unsplash.com/photo-1536440136628-849c177e76a1?auto=format&fit=crop&q=80&w=1200',
    'https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&q=80&w=1200',
    'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?auto=format&fit=crop&q=80&w=1200',
    'https://images.unsplash.com/photo-1440404653325-ab127d49abc1?auto=format&fit=crop&q=80&w=1200',
    'https://images.unsplash.com/photo-1485846234645-a62644f84728?auto=format&fit=crop&q=80&w=1200',
];

const STUDIO_THEMES = [
    // 深色混色系
    { id: 'noir_deep', name: '暗影', isDark: true, bgStyle: 'linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)', textColor: '#FFFFFF', accent: '#ffffff' },
    { id: 'crimson_dark', name: '红月', isDark: true, bgStyle: 'linear-gradient(135deg, #1a0a0a 0%, #4a0000 70%, #000000 100%)', textColor: '#FFD7D7', accent: '#FF4B4B' },
    { id: 'emerald_mix', name: '深翠', isDark: true, bgStyle: 'linear-gradient(135deg, #0d1b1e 0%, #1b3d3d 60%, #050a0a 100%)', textColor: '#A7FFEB', accent: '#1DE9B6' },
    { id: 'golden_mix', name: '金座', isDark: true, bgStyle: 'linear-gradient(135deg, #1a1610 0%, #3d2b1f 50%, #000000 100%)', textColor: '#D4AF37', accent: '#D4AF37' },
    // 浅色混色系
    { id: 'sunset_light', name: '暖阳', isDark: false, bgStyle: 'linear-gradient(135deg, #FFDEE9 0%, #B5FFFC 100%)', textColor: '#2C3E50', accent: '#FF7EB3' },
    { id: 'mint_dream', name: '薄荷', isDark: false, bgStyle: 'linear-gradient(135deg, #D9AFD9 0%, #97D9E1 100%)', textColor: '#1a1a1a', accent: '#74EBD5' },
    { id: 'lavender_sky', name: '薰衣草', isDark: false, bgStyle: 'linear-gradient(135deg, #eecda3 0%, #ef629f 100%)', textColor: '#FFFFFF', accent: '#FFFFFF' },
    { id: 'morni_mist', name: '晨曦', isDark: false, bgStyle: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)', textColor: '#444444', accent: '#333333' },
];

const STUDIO_FONTS = [
    { id: 'bebas', name: '电影字体', family: "'Bebas Neue', cursive" },
    { id: 'mashan', name: '草书', family: "'Ma Shan Zheng', cursive" },
    { id: 'inter', name: '现代', family: "'Inter', sans-serif" },
    { id: 'orbitron', name: '科技', family: "'Orbitron', sans-serif" },
];

const STUDIO_TEXT_COLORS = [
    { name: 'Pure White', value: '#FFFFFF' },
    { name: 'Deep Black', value: '#000000' },
    { name: 'Movie Gold', value: '#D4AF37' },
    { name: 'Neon Blue', value: '#00D4FF' },
    { name: 'Vibrant Red', value: '#FF4B4B' },
];

const LaurelWreath = ({ color }: { color: string }) => (
    <svg width="100%" height="100%" viewBox="0 0 100 100" fill={color}>
        <path d="M50,85 C35,85 20,70 20,40 C20,35 21,30 22,25 C18,30 15,40 15,50 C15,75 35,95 50,95 L50,85 Z" />
        <path d="M50,85 C65,85 80,70 80,40 C80,35 79,30 78,25 C82,30 85,40 85,50 C85,75 65,95 50,95 L50,85 Z" />
    </svg>
);

interface CoverCanvasProps {
    id?: string;
    theme: typeof STUDIO_THEMES[0];
    layoutMode: 'stack' | 'grid';
    libraryName: string;
    subTitle: string;
    posters: string[];
    backdropUrl?: string;
    currentFont: typeof STUDIO_FONTS[0];
    activeTextColor: string;
    titleX: number;
    titleY: number;
    titleGap: number;
    titleSize: number;
    gridIntensity: number;
    posterX: number;
    fanSpread: number;
    fanRotation: number;
    cycleIndex: number;
    isSmall?: boolean;
}

const CoverCanvas: React.FC<CoverCanvasProps> = (props) => {
    const {
        id, theme, layoutMode, libraryName, subTitle, posters, backdropUrl, currentFont, activeTextColor,
        titleX, titleY, titleGap, titleSize, gridIntensity, posterX, fanSpread, fanRotation, cycleIndex, isSmall
    } = props;

    const bgImage = backdropUrl || 'https://image.tmdb.org/t/p/original/8uS6B0KbhDZ3G9689br09v9I7xy.jpg';

    const renderFlowingColumns = () => {
        const colCount = 6;
        return Array.from({ length: colCount }, (_, i) => {
            const items = [...posters, ...posters, ...posters];
            const duration = 120 + (i * 20);
            return (
                <div key={i} className="relative flex-1 h-full overflow-hidden">
                    <div className={`flex flex-col gap-2 ${i % 2 === 0 ? 'animate-scrollUp' : 'animate-scrollDown'}`} style={{ animationDuration: `${duration}s` }}>
                        {items.map((url, idx) => (
                            <div key={idx} className="aspect-[2/3] w-full rounded-sm overflow-hidden border border-black/20 shadow-xl shrink-0 bg-black">
                                <img src={url} className="w-full h-full object-cover block" loading="lazy" crossOrigin="anonymous" />
                            </div>
                        ))}
                    </div>
                </div>
            );
        });
    };

    return (
        <div id={id} className={`relative w-full aspect-video shadow-2xl rounded-2xl overflow-hidden transition-all duration-500`} style={{ background: theme.bgStyle }}>
            {layoutMode === 'grid' ? (
                <div className="absolute inset-0">
                    <div className="absolute inset-0 flex gap-2 p-3 scale-110 z-10" style={{ opacity: gridIntensity / 100 }}>
                        {renderFlowingColumns()}
                    </div>
                    <div className="absolute z-30 flex flex-col items-center justify-center pointer-events-none transition-all duration-300 ease-out" style={{ left: `${titleX}%`, top: `${titleY}%`, transform: 'translate(-50%, -50%)', width: 'auto' }}>
                        <div className="flex items-center gap-10">
                            <div className="scale-x-[-1]" style={{ color: activeTextColor, width: isSmall ? '1.5vw' : '3vw', height: isSmall ? '1.5vw' : '3vw' }}><LaurelWreath color="currentColor" /></div>
                            <h2 className="font-black leading-none uppercase whitespace-nowrap" style={{ fontSize: `${titleSize}vw`, fontFamily: currentFont.family, color: activeTextColor, textShadow: activeTextColor === '#000000' ? '0 5px 15px rgba(255,255,255,0.4)' : '0 10px 50px rgba(0,0,0,0.9)' }}>{libraryName}</h2>
                            <div style={{ color: activeTextColor, width: isSmall ? '1.5vw' : '3vw', height: isSmall ? '1.5vw' : '3vw' }}><LaurelWreath color="currentColor" /></div>
                        </div>
                        <div className="flex flex-col items-center" style={{ marginTop: `${titleGap * (isSmall ? 0.4 : 1)}px` }}>
                            <div className="w-24 h-[2px] rounded-full mb-6 opacity-80" style={{ backgroundColor: activeTextColor }} />
                            <span className="font-black tracking-[0.8em] uppercase block whitespace-nowrap" style={{ fontSize: '1.4vw', color: activeTextColor, opacity: 0.85 }}>{subTitle}</span>
                        </div>
                    </div>
                </div>
            ) : (
                <div className="absolute inset-0">
                    <img src={bgImage} className={`absolute inset-0 w-full h-full object-cover z-10 pointer-events-none transition-opacity duration-1000 ${theme.isDark ? 'opacity-30' : 'opacity-15'}`} crossOrigin="anonymous" />
                    <div className={`absolute inset-0 z-20 pointer-events-none ${theme.isDark ? 'bg-gradient-to-r from-black/80 via-black/30 to-transparent' : 'bg-gradient-to-r from-white/70 via-white/20 to-transparent'}`} />
                    <div className="absolute z-40 flex flex-col items-start pointer-events-none transition-all duration-300 ease-out" style={{ left: `${titleX}%`, top: `${titleY}%`, transform: 'translate(-50%, -50%)', minWidth: '40%' }}>
                        <h2 className="font-black leading-[0.85] tracking-tight uppercase whitespace-nowrap" style={{ fontSize: `${titleSize}vw`, fontFamily: currentFont.family, color: activeTextColor, textShadow: activeTextColor === '#000000' ? '0 5px 20px rgba(255,255,255,0.5)' : '0 20px 80px rgba(0,0,0,1)' }}>{libraryName}</h2>
                        <span className="font-black tracking-[1.5em] uppercase block whitespace-nowrap" style={{ marginTop: `${titleGap * (isSmall ? 0.4 : 1)}px`, fontSize: '1.2vw', color: activeTextColor, opacity: 0.9 }}>{subTitle}</span>
                    </div>
                    <div className="absolute z-30 w-[30%] h-[85%] transition-all duration-500" style={{ left: `${posterX}%`, top: '50%', transform: 'translate(-50%, -50%)' }}>
                        <div className="relative w-full h-full">
                            {posters.slice(0, 6).map((url, i) => {
                                const idx = (i - cycleIndex + 6) % 6;
                                const op = 1 - (idx * 0.15);
                                const sc = 1 - (idx * 0.08);
                                const trans = `translateX(${-idx * fanSpread * (isSmall ? 0.4 : 1)}px) rotate(${-idx * fanRotation}deg) scale(${sc})`;
                                return (
                                    <div key={i} className="absolute inset-0 transition-all duration-[1200ms] ease-[cubic-bezier(0.16,1,0.3,1)]" style={{ zIndex: 10 - idx, opacity: op, transform: trans }}>
                                        <div className="w-full h-full rounded-2xl overflow-hidden shadow-xl border border-white/10 bg-black">
                                            <img src={url} className="w-full h-full object-cover block" crossOrigin="anonymous" />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

// === End of Shared Components ===

const DEFAULT_CONFIG: AppConfig = {
    emby: {
        serverUrl: "",
        apiKey: "",
        refreshAfterOrganize: false,
        notifications: {
            forwardToTelegram: true,  // 默认启用
            playbackReportingFreq: "daily"
        },
        missingEpisodes: {
            cronSchedule: "0 0 * * *"
        }
    }
} as any;

type GeneratorMode = 'classic' | 'studio_stack' | 'studio_grid';

export const EmbyView: React.FC = () => {
    const [config, setConfig] = useState<AppConfig | null>(null);
    const [isSaving, setIsSaving] = useState(false);
    const [isScanning, setIsScanning] = useState(false);
    const [toast, setToast] = useState<string | null>(null);
    const [missingData, setMissingData] = useState<any[]>([]);

    // === Shared States ===
    const [selectedLibraries, setSelectedLibraries] = useState<Set<string>>(new Set());
    const [currentPreviewLib, setCurrentPreviewLib] = useState<string>(''); // 当前预览的媒体库
    const [coverTitle, setCoverTitle] = useState('电影收藏');
    const [coverSubtitle, setCoverSubtitle] = useState('MOVIE COLLECTION');
    const [coverLibraries, setCoverLibraries] = useState<Array<{ id: string; name: string; type: string }>>([]);
    const [isLoadingLibraries, setIsLoadingLibraries] = useState(false);
    const [isUploading, setIsUploading] = useState(false);

    // === Classic Generator States ===
    const [coverThemes, setCoverThemes] = useState<Array<{ index: number; name: string; colors: string[] }>>([]);
    const [selectedTheme, setSelectedTheme] = useState(0);
    const [coverFormat, setCoverFormat] = useState<'png' | 'gif'>('png');
    const [coverPreview, setCoverPreview] = useState<string | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);
    // Parameters for Classic
    const [titleSize, setTitleSize] = useState(192);
    const [offsetX, setOffsetX] = useState(40);
    const [posterScale, setPosterScale] = useState(30);
    const [vAlign, setVAlign] = useState(60);
    const [spacing, setSpacing] = useState(3.0);
    const [angleScale, setAngleScale] = useState(1.0);
    const [posterCount, setPosterCount] = useState(3);
    const [useBackdrop, setUseBackdrop] = useState(false);
    // Batch
    const [batchSelection, setBatchSelection] = useState<Set<string>>(new Set());
    const [batchPreviews, setBatchPreviews] = useState<Record<string, string>>({});

    // === Studio Generator States ===
    const [generatorMode, setGeneratorMode] = useState<GeneratorMode>('classic');
    const [studioPosters, setStudioPosters] = useState<string[]>(DEFAULT_POSTERS);
    const [studioTheme, setStudioTheme] = useState(STUDIO_THEMES[0]);
    const [studioFont, setStudioFont] = useState(STUDIO_FONTS[0]);
    const [studioOverrideColor, setStudioOverrideColor] = useState<string | null>(null);
    const [studioBackdropUrl, setStudioBackdropUrl] = useState<string | undefined>(undefined);

    // Studio Precision Params
    const [sTitleX, setSTitleX] = useState(50);
    const [sTitleY, setSTitleY] = useState(50);
    const [sTitleGap, setSTitleGap] = useState(24);
    const [sTitleSize, setSTitleSize] = useState(4.5);
    const [fanSpread, setFanSpread] = useState(45);
    const [fanRotation, setFanRotation] = useState(6);
    const [sPosterX, setSPosterX] = useState(72);
    const [gridIntensity, setGridIntensity] = useState(80);
    const [cycleIndex, setCycleIndex] = useState(0);

    const activeStudioTextColor = studioOverrideColor || studioTheme.textColor;

    // Load Config & Missing Data
    useEffect(() => {
        const init = async () => {
            try {
                const data = await api.getConfig();
                if (data?.emby) {
                    setConfig(data);
                    if (data.emby.serverUrl && data.emby.apiKey) {
                        loadCoverData(); // Classic & Shared data
                    }
                } else {
                    setConfig(DEFAULT_CONFIG);
                }
            } catch (err) {
                console.error("加载配置失败:", err);
                setConfig(DEFAULT_CONFIG);
            }
        };
        init();

        const fetchMissingData = async () => {
            const res = await api.getMissingEpisodes();
            if (res.success && res.data) setMissingData(res.data);
        };
        fetchMissingData();
        const interval = setInterval(fetchMissingData, 3000);
        return () => clearInterval(interval);
    }, []);

    // Studio Cycle Animation
    useEffect(() => {
        if (generatorMode === 'studio_stack') {
            const timer = setInterval(() => {
                setCycleIndex(prev => (prev + 1) % studioPosters.length);
            }, 4000);
            return () => clearInterval(timer);
        }
    }, [studioPosters.length, generatorMode]);

    // Update Studio Layout Mode derived from Tab
    const studioLayoutMode = generatorMode === 'studio_grid' ? 'grid' : 'stack';

    // Helper Functions
    const showToast = (msg: string, isError = false) => {
        setToast(msg);
        setTimeout(() => setToast(null), 3000);
    };

    const handleSave = async () => {
        if (!config) return;
        setIsSaving(true);
        try {
            await api.saveConfig(config);
            showToast('配置已保存');
        } catch (e: any) {
            showToast('保存失败: ' + e.message, true);
        } finally {
            setIsSaving(false);
        }
    };

    // Config Updaters
    const updateNotifications = (key: string, value: any) => {
        if (!config) return;
        setConfig(prev => prev ? ({ ...prev, emby: { ...prev.emby, notifications: { ...prev.emby.notifications, [key]: value } } }) : null);
    };
    const updateNested = (section: keyof AppConfig, key: string, value: any) => {
        if (!config) return;
        setConfig(prev => prev ? ({ ...prev, [section]: { ...(prev[section] as any), [key]: value } }) : null);
    };
    const updateMissing = (key: string, value: any) => {
        if (!config) return;
        setConfig(prev => prev ? ({ ...prev, emby: { ...prev.emby, missingEpisodes: { ...prev.emby.missingEpisodes, [key]: value } } }) : null);
    };

    const handleScan = async () => {
        setIsScanning(true);
        setMissingData([]);
        try {
            const result = await api.startMissingScanBackground();
            if (!result.success && !result.error?.includes('正在进行中')) {
                showToast(result.error || '失败', true);
            } else {
                showToast('扫描已在后台启动');
            }
        } catch (e) { showToast('扫描失败', true); }
        finally { setIsScanning(false); }
    };

    // === Logic for Cover Generators ===

    const loadCoverData = async () => {
        setIsLoadingLibraries(true);
        try {
            // Load Themes (Classic)
            const themesRes = await api.getCoverThemes();
            if (themesRes.success) setCoverThemes(themesRes.data);

            // Load Libraries (Shared)
            const librariesRes = await api.getCoverLibraries();
            if (librariesRes.success) {
                setCoverLibraries(librariesRes.data);
                if (librariesRes.data.length > 0) {
                    const firstLib = librariesRes.data[0];
                    setCurrentPreviewLib(firstLib.id);
                    setSelectedLibraries(new Set([firstLib.id])); // 默认选中第一个
                    setCoverTitle(firstLib.name);
                    updateSubtitle(firstLib.type);

                    // If Studio mode is active, fetch detailed posters too
                    fetchStudioPosters(firstLib.id);
                }
            }
        } catch (e) { console.error(e); }
        finally { setIsLoadingLibraries(false); }
    };

    const updateSubtitle = (type?: string) => {
        const typeMap: Record<string, string> = {
            'movies': 'MOVIE COLLECTION', 'tvshows': 'TV SHOWS',
            'music': 'MUSIC COLLECTION', 'homevideos': 'HOME VIDEOS',
            'books': 'BOOK COLLECTION', 'photos': 'PHOTO ALBUM', 'musicvideos': 'MUSIC VIDEOS'
        };
        setCoverSubtitle(typeMap[type?.toLowerCase() || ''] || type?.toUpperCase() || 'MEDIA COLLECTION');
    };

    const fetchStudioPosters = async (libId: string) => {
        // 使用后端代理获取 Base64 图片，避免 html2canvas 的 CORS 问题
        if (!libId) return;

        try {
            // 请求 25 张海报以填充 5x5 的网格或 6 张堆叠图
            const res = await api.getLibraryPosters(libId, 25);
            if (res.success && res.data && res.data.length > 0) {
                setStudioPosters(res.data);
            } else {
                setStudioPosters(DEFAULT_POSTERS);
            }
        } catch (e) {
            console.error("获取海报失败:", e);
            setStudioPosters(DEFAULT_POSTERS);
        }
    };

    // Classic Generator Trigger (预览当前媒体库)
    const handleGenerateClassic = async () => {
        if (!currentPreviewLib) return showToast('请先预览一个媒体库');
        setIsGenerating(true);
        try {
            const coverConfig = {
                title: coverTitle, subtitle: coverSubtitle,
                titleSize, offsetX, posterScale, vAlign, spacing, angleScale, posterCount, useBackdrop,
                format: coverFormat, theme: selectedTheme
            };
            const result = await api.generateCover({ libraryId: currentPreviewLib, config: coverConfig });
            if (result.success) {
                setCoverPreview(result.data.image);
                showToast('预览生成成功');
            } else {
                showToast(result.error || '生成失败', true);
            }
        } catch (e) { showToast('生成失败', true); }
        finally { setIsGenerating(false); }
    };

    // 批量上传到选中的媒体库
    const handleBatchUpload = async () => {
        if (selectedLibraries.size === 0) return showToast('请先勾选要上传的媒体库');
        if (!coverPreview && generatorMode === 'classic') return showToast('请先生成预览图');

        setIsUploading(true);
        const libs = Array.from(selectedLibraries);
        let successCount = 0;

        for (const libId of libs) {
            try {
                const lib = coverLibraries.find(l => l.id === libId);
                const libName = lib?.name ?? libId;
                showToast(`正在处理: ${libName}...`);

                // 为每个库获取海报并生成封面
                const coverConfig = {
                    title: lib?.name ?? coverTitle,
                    subtitle: lib?.type?.toUpperCase() ?? coverSubtitle,
                    titleSize, offsetX, posterScale, vAlign, spacing, angleScale, posterCount, useBackdrop,
                    format: coverFormat, theme: selectedTheme
                };

                const result = await api.generateCover({ libraryId: libId, config: coverConfig });
                if (result.success) {
                    successCount++;
                }
            } catch (e) {
                console.error(`上传 ${libId} 失败:`, e);
            }
        }

        setIsUploading(false);
        showToast(`成功上传 ${successCount}/${libs.length} 个媒体库封面`);
    };


    // Studio Generator Trigger (Upload)
    const handleGenerateStudio = async () => {
        if (!currentPreviewLib) return showToast('请先预览一个媒体库');
        const element = document.getElementById('studio-canvas');
        if (!element) return;

        setIsGenerating(true);
        showToast('正在渲染封面...');
        try {
            const canvas = await html2canvas(element, { useCORS: true, backgroundColor: null });

            canvas.toBlob(async (blob) => {
                if (!blob) {
                    showToast("渲染失败: 无法生成图片 Blob", true);
                    setIsGenerating(false);
                    return;
                }

                try {
                    const res = await api.uploadRenderedCover(currentPreviewLib, blob, coverTitle);
                    if (res.success) {
                        showToast('已上传并备份到本地');
                    } else {
                        showToast(res.error || '上传失败', true);
                    }
                } catch (e: any) {
                    showToast('上传失败: ' + (e.message || '网络错误'), true);
                } finally {
                    setIsGenerating(false);
                }

            }, 'image/png');
        } catch (e: any) {
            showToast(e.message, true);
            setIsGenerating(false);
        }
    };

    // 多选/单选媒体库处理
    const toggleLibrarySelection = (libId: string) => {
        setSelectedLibraries(prev => {
            const next = new Set(prev);
            if (next.has(libId)) {
                next.delete(libId);
            } else {
                next.add(libId);
            }
            return next;
        });
    };

    const selectAllLibraries = () => {
        if (selectedLibraries.size === coverLibraries.length) {
            setSelectedLibraries(new Set());
        } else {
            setSelectedLibraries(new Set(coverLibraries.map(l => l.id)));
        }
    };

    // 预览指定媒体库
    const handlePreviewLibrary = (libId: string) => {
        setCurrentPreviewLib(libId);
        const lib = coverLibraries.find(l => l.id === libId);
        if (lib) {
            setCoverTitle(lib.name);
            updateSubtitle(lib.type);
            fetchStudioPosters(libId);
        }
    };

    const copyWebhook = async () => {
        const port = window.location.port || '18080';
        const webhookUrl = `http://${window.location.hostname}:${port}/api/emby/webhook`;
        try {
            await navigator.clipboard.writeText(webhookUrl);
            showToast('已复制');
        } catch { showToast('复制失败', true); }
    };

    if (!config) return <div className="p-10 flex justify-center text-slate-500"><RefreshCw className="animate-spin" /></div>;

    const glassCardClass = "bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border-[0.5px] border-white/40 dark:border-white/10 shadow-sm ring-1 ring-white/50 dark:ring-white/5";
    const inputClass = "w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-green-500 outline-none text-sm font-mono backdrop-blur-sm shadow-inner";
    const actionBtnClass = "px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1 transition-colors";

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
            {/* Styles for Animations */}
            <style>{`
                .scrollbar-hide::-webkit-scrollbar { display: none; }
                @keyframes scrollUp { from { transform: translateY(0); } to { transform: translateY(-33.33%); } }
                @keyframes scrollDown { from { transform: translateY(-33.33%); } to { transform: translateY(0); } }
                .animate-scrollUp { animation: scrollUp linear infinite; }
                .animate-scrollDown { animation: scrollDown linear infinite; }
                /* Custom Range Slider for Studio */
                .studio-range::-webkit-slider-thumb { 
                    -webkit-appearance: none; width: 12px; height: 12px; 
                    background: #fff; border-radius: 50%; border: 2px solid #000;
                    cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.4);
                }
            `}</style>

            {toast && (
                <div className={`fixed top-6 right-6 px-6 py-3 rounded-xl shadow-2xl z-50 flex items-center gap-3 font-medium border-[0.5px] backdrop-blur-md ${toast.includes('失败') ? 'bg-red-500/90 text-white border-red-400' : 'bg-slate-800/90 text-white border-slate-700'}`}>
                    <CheckCircle2 size={18} /> {toast}
                </div>
            )}

            <div className="flex flex-col md:flex-row justify-between items-center pb-2 gap-4">
                <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight drop-shadow-sm">Emby 联动</h2>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
                {/* Notifications & Reporting */}
                <section className={`${glassCardClass} overflow-hidden h-fit`}>
                    <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-sky-50 dark:bg-sky-900/20 rounded-lg text-sky-600 dark:text-sky-400 shadow-inner"><Bell size={20} /></div>
                            <h3 className="font-bold text-slate-700 dark:text-slate-200">通知与报告</h3>
                        </div>
                        <button onClick={handleSave} disabled={isSaving} className={`${actionBtnClass} bg-sky-50 text-sky-600 hover:bg-sky-100 disabled:opacity-50`}>
                            {isSaving ? <RefreshCw className="animate-spin" size={12} /> : <Save size={12} />} 保存
                        </button>
                    </div>
                    <div className="p-6 space-y-4">
                        <div className="bg-slate-50/50 dark:bg-slate-900/30 p-4 rounded-xl border border-slate-200/50 dark:border-slate-700/50">
                            <div className="flex justify-between mb-2">
                                <label className="text-xs font-bold text-slate-500 uppercase flex gap-1"><Zap size={12} /> Webhook 地址</label>
                                <button onClick={copyWebhook} className="text-xs text-sky-600 font-bold flex gap-1"><Copy size={12} /> 复制</button>
                            </div>
                            <code className="block w-full px-3 py-2 bg-white/50 dark:bg-slate-900/50 rounded-lg text-xs font-mono text-slate-600 dark:text-slate-400 break-all border border-slate-200/50 shadow-inner">
                                http://{window.location.hostname}:{window.location.port || '18080'}/api/emby/webhook
                            </code>
                        </div>
                    </div>
                </section>

                {/* Missing Episodes */}
                <section className={`${glassCardClass} overflow-hidden h-fit`}>
                    <div className="px-6 py-4 border-b-[0.5px] border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded-lg text-purple-600 dark:text-purple-400"><FileWarning size={20} /></div>
                            <h3 className="font-bold text-slate-700 dark:text-slate-200">缺集检测</h3>
                        </div>
                        <button onClick={handleScan} disabled={isScanning} className={`${actionBtnClass} bg-purple-50 text-purple-600 hover:bg-purple-100 disabled:opacity-50`}>
                            {isScanning ? <RefreshCw className="animate-spin" size={12} /> : <Search size={12} />} 检测
                        </button>
                    </div>
                    <div className="p-6">
                        <div className="flex items-center gap-4 mb-4">
                            <input type="text" value={config.emby.missingEpisodes?.cronSchedule} onChange={e => updateMissing('cronSchedule', e.target.value)} className={inputClass} placeholder="Cron Expression" />
                        </div>
                        <div className="bg-slate-50/50 dark:bg-slate-900/30 rounded-xl border border-slate-200/50 h-[150px] overflow-y-auto p-4 text-sm text-slate-600 dark:text-slate-400">
                            {missingData.length > 0 ? (
                                <ul className="space-y-2">
                                    {missingData.map(m => (
                                        <li key={m.id} className="flex justify-between"><span>{m.name}</span> <span className="text-red-500 font-bold">缺 {m.missing} 集</span></li>
                                    ))}
                                </ul>
                            ) : <div className="text-center py-4">暂无缺集数据</div>}
                        </div>
                    </div>
                </section>

                {/* === Unified Cover Generator === */}
                <section className={`${glassCardClass} overflow-hidden xl:col-span-2 flex flex-col`}>
                    <div className="px-6 py-4 border-b border-slate-200/50 dark:border-slate-700/50 flex flex-col md:flex-row gap-4 justify-between items-center bg-slate-50/30 dark:bg-slate-800/20">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-amber-50 dark:bg-amber-900/20 rounded-lg text-amber-600 dark:text-amber-400"><Image size={20} /></div>
                            <h3 className="font-bold text-slate-700 dark:text-slate-200">封面生成器</h3>
                        </div>

                        {/* Mode Switcher Tabs */}
                        <div className="flex p-1 bg-slate-200/50 dark:bg-black/30 rounded-lg border border-slate-200 dark:border-slate-700">
                            <button
                                onClick={() => setGeneratorMode('classic')}
                                className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${generatorMode === 'classic' ? 'bg-white dark:bg-slate-800 shadow text-amber-600' : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'}`}
                            >
                                经典 3D
                            </button>
                            <button
                                onClick={() => setGeneratorMode('studio_stack')}
                                className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${generatorMode === 'studio_stack' ? 'bg-white dark:bg-slate-800 shadow text-amber-600' : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'}`}
                            >
                                动态堆叠
                            </button>
                            <button
                                onClick={() => setGeneratorMode('studio_grid')}
                                className={`px-4 py-1.5 rounded-md text-xs font-bold transition-all ${generatorMode === 'studio_grid' ? 'bg-white dark:bg-slate-800 shadow text-amber-600' : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'}`}
                            >
                                流体墙幕
                            </button>
                        </div>

                        <div className="flex items-center gap-2">
                            <button onClick={loadCoverData} disabled={isLoadingLibraries} className={`${actionBtnClass} bg-slate-100 text-slate-600`}>
                                <RefreshCw size={12} className={isLoadingLibraries ? 'animate-spin' : ''} /> 刷新库
                            </button>
                            <button
                                onClick={generatorMode === 'classic' ? handleGenerateClassic : handleGenerateStudio}
                                disabled={isGenerating}
                                className={`${actionBtnClass} bg-amber-500 text-white hover:bg-amber-600 shadow-md shadow-amber-500/20`}
                            >
                                {isGenerating ? <Loader2 className="animate-spin" size={14} /> : <CloudUpload size={14} />}
                                {generatorMode === 'classic' ? '生成并上传' : '渲染并同步'}
                            </button>
                        </div>
                    </div>

                    <div className="flex flex-col xl:flex-row h-auto min-h-[900px] xl:h-[800px] divide-y xl:divide-y-0 xl:divide-x divide-slate-200/50 dark:divide-slate-700/50">
                        {/* Left: Controls Pane */}
                        <div className="w-full xl:w-[400px] flex flex-col bg-slate-50/50 dark:bg-slate-900/30 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-700">
                            {/* Library Selector - 多选模式 */}
                            <div className="p-4 border-b border-slate-200/50 dark:border-slate-700/50">
                                <div className="flex items-center justify-between mb-2">
                                    <label className="text-xs font-bold text-slate-500 uppercase">选择媒体库</label>
                                    <button
                                        onClick={selectAllLibraries}
                                        className="text-[10px] text-amber-600 font-bold hover:underline"
                                    >
                                        {selectedLibraries.size === coverLibraries.length ? '取消全选' : '全选'}
                                    </button>
                                </div>
                                <div className="space-y-1 max-h-[200px] overflow-y-auto">
                                    {coverLibraries.map(lib => (
                                        <div
                                            key={lib.id}
                                            className={`px-3 py-2 rounded-lg flex items-center gap-3 transition-colors ${currentPreviewLib === lib.id ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400' : 'hover:bg-slate-200 dark:hover:bg-slate-800'}`}
                                        >
                                            {/* 勾选框 */}
                                            <input
                                                type="checkbox"
                                                checked={selectedLibraries.has(lib.id)}
                                                onChange={() => toggleLibrarySelection(lib.id)}
                                                className="accent-amber-500 w-4 h-4 cursor-pointer"
                                                onClick={e => e.stopPropagation()}
                                            />
                                            {/* 点击名称则预览 */}
                                            <div
                                                onClick={() => handlePreviewLibrary(lib.id)}
                                                className="flex-1 flex items-center justify-between cursor-pointer"
                                            >
                                                <span className={`text-sm ${currentPreviewLib === lib.id ? 'font-bold' : ''}`}>{lib.name}</span>
                                                <span className="text-[10px] opacity-70 uppercase border border-current px-1 rounded">{lib.type}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                                {/* 选中统计 */}
                                <div className="mt-2 text-xs text-slate-500">
                                    已选: {selectedLibraries.size}/{coverLibraries.length} |
                                    预览: {currentPreviewLib ? coverLibraries.find(l => l.id === currentPreviewLib)?.name : '无'}
                                </div>
                            </div>

                            {/* Shared Title Inputs */}
                            <div className="p-4 border-b border-slate-200/50 dark:border-slate-700/50 space-y-3">
                                <label className="text-xs font-bold text-slate-500 uppercase block">标题设置</label>
                                <input value={coverTitle} onChange={e => setCoverTitle(e.target.value)} className={inputClass} placeholder="主标题" />
                                <input value={coverSubtitle} onChange={e => setCoverSubtitle(e.target.value)} className={inputClass} placeholder="副标题" />
                            </div>

                            {/* Dynamic Controls based on Mode */}
                            <div className="flex-1 p-4 space-y-6">
                                {generatorMode === 'classic' ? (
                                    <>
                                        {/* Classic Controls */}
                                        <div className="space-y-3">
                                            <label className="text-xs font-bold text-slate-500 uppercase flex gap-1"><Palette size={12} /> 主题预设 (Classic)</label>
                                            <div className="flex flex-wrap gap-2">
                                                <button onClick={() => setSelectedTheme(-1)} className={`px-2 py-1 text-[10px] border rounded ${selectedTheme === -1 ? 'bg-amber-500 text-white' : ''}`}>自动</button>
                                                {coverThemes.map(t => (
                                                    <button key={t.index} onClick={() => setSelectedTheme(t.index)} className={`w-6 h-6 rounded-full border ${selectedTheme === t.index ? 'ring-2 ring-amber-500' : ''}`} style={{ background: `linear-gradient(45deg, ${t.colors[0]}, ${t.colors[1]})` }} title={t.name} />
                                                ))}
                                            </div>
                                        </div>

                                        <div className="space-y-4">
                                            <div>
                                                <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-1"><span>海报数量</span><span>{posterCount}</span></div>
                                                <input type="range" min="1" max="7" value={posterCount} onChange={e => setPosterCount(Number(e.target.value))} className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500" />
                                            </div>
                                            <div>
                                                <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-1"><span>字号大小</span><span>{titleSize}</span></div>
                                                <input type="range" min="50" max="300" value={titleSize} onChange={e => setTitleSize(Number(e.target.value))} className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500" />
                                            </div>
                                            <div>
                                                <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-1"><span>水平偏移 X</span><span>{offsetX}</span></div>
                                                <input type="range" min="0" max="500" value={offsetX} onChange={e => setOffsetX(Number(e.target.value))} className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500" />
                                            </div>
                                            <div className="flex items-center justify-between pt-2">
                                                <div className="flex items-center gap-2">
                                                    <input type="checkbox" checked={useBackdrop} onChange={e => setUseBackdrop(e.target.checked)} className="accent-amber-500" />
                                                    <span className="text-xs text-slate-600 dark:text-slate-400 font-bold">使用横幅背景</span>
                                                </div>
                                                <div className="flex bg-slate-200 dark:bg-slate-700 rounded-lg p-0.5">
                                                    <button onClick={() => setCoverFormat('png')} className={`px-2 py-0.5 text-[10px] font-bold rounded-md transition-all ${coverFormat === 'png' ? 'bg-white text-amber-600 shadow' : 'text-slate-500 hover:text-slate-300'}`}>静态</button>
                                                    <button onClick={() => setCoverFormat('gif')} className={`px-2 py-0.5 text-[10px] font-bold rounded-md transition-all ${coverFormat === 'gif' ? 'bg-white text-amber-600 shadow' : 'text-slate-500 hover:text-slate-300'}`}>动态</button>
                                                </div>
                                            </div>
                                        </div>
                                    </>
                                ) : (
                                    <>
                                        {/* Studio Controls */}
                                        <div className="space-y-3">
                                            <label className="text-xs font-bold text-slate-500 uppercase flex gap-1"><Palette size={12} /> 风格预设 (Studio)</label>
                                            <div className="grid grid-cols-4 gap-2">
                                                {STUDIO_THEMES.map(t => (
                                                    <button key={t.id} onClick={() => setStudioTheme(t)} className={`h-8 rounded-md border-2 overflow-hidden transition-all ${studioTheme.id === t.id ? 'border-amber-500 scale-105 shadow' : 'border-transparent opacity-70 hover:opacity-100'}`}>
                                                        <div className="w-full h-full" style={{ background: t.bgStyle }} />
                                                    </button>
                                                ))}
                                            </div>
                                        </div>

                                        <div className="space-y-3">
                                            <label className="text-xs font-bold text-slate-500 uppercase flex gap-1"><Type size={12} /> 字体与颜色</label>
                                            <div className="flex gap-2">
                                                {STUDIO_FONTS.map(f => (
                                                    <button key={f.id} onClick={() => setStudioFont(f)} className={`flex-1 py-1 text-[10px] border rounded ${studioFont.id === f.id ? 'bg-slate-700 text-white' : 'bg-slate-100 dark:bg-slate-800'}`} style={{ fontFamily: f.family }}>{f.name}</button>
                                                ))}
                                            </div>
                                            <div className="flex gap-1 justify-between">
                                                {STUDIO_TEXT_COLORS.map(c => (
                                                    <button key={c.value} onClick={() => setStudioOverrideColor(c.value)} className={`w-6 h-6 rounded-full border ${studioOverrideColor === c.value ? 'ring-2 ring-amber-500' : ''}`} style={{ backgroundColor: c.value }} />
                                                ))}
                                                <button onClick={() => setStudioOverrideColor(null)} className="w-6 h-6 rounded-full border flex items-center justify-center bg-slate-100 text-slate-400"><History size={12} /></button>
                                            </div>
                                        </div>

                                        <div className="space-y-4 pt-2 border-t border-slate-200/50 dark:border-slate-700/50">
                                            <div>
                                                <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-1"><span>标题位置 X / Y</span><span>{sTitleX}% / {sTitleY}%</span></div>
                                                <div className="flex gap-2">
                                                    <input type="range" min="0" max="100" value={sTitleX} onChange={e => setSTitleX(Number(e.target.value))} className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500 studio-range" />
                                                    <input type="range" min="0" max="100" value={sTitleY} onChange={e => setSTitleY(Number(e.target.value))} className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500 studio-range" />
                                                </div>
                                            </div>
                                            <div>
                                                <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-1"><span>标题字号</span><span>{sTitleSize}vw</span></div>
                                                <input type="range" min="1" max="15" step="0.1" value={sTitleSize} onChange={e => setSTitleSize(Number(e.target.value))} className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500 studio-range" />
                                            </div>

                                            {generatorMode === 'studio_stack' ? (
                                                <>
                                                    <div>
                                                        <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-1"><span>展开度 & 旋转</span></div>
                                                        <div className="flex gap-2">
                                                            <input type="range" min="0" max="150" value={fanSpread} onChange={e => setFanSpread(Number(e.target.value))} className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500 studio-range" title="展开" />
                                                            <input type="range" min="0" max="45" value={fanRotation} onChange={e => setFanRotation(Number(e.target.value))} className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500 studio-range" title="旋转" />
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-1"><span>海报位置 X</span><span>{sPosterX}%</span></div>
                                                        <input type="range" min="0" max="100" value={sPosterX} onChange={e => setSPosterX(Number(e.target.value))} className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500 studio-range" />
                                                    </div>
                                                </>
                                            ) : (
                                                <div>
                                                    <div className="flex justify-between text-[10px] font-bold text-slate-500 mb-1"><span>墙幕透明度</span><span>{gridIntensity}%</span></div>
                                                    <input type="range" min="10" max="100" value={gridIntensity} onChange={e => setGridIntensity(Number(e.target.value))} className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-amber-500 studio-range" />
                                                </div>
                                            )}
                                            {/* Use Library Backdrop Toggle for Studio */}
                                            <div className="flex items-center gap-2 pt-2">
                                                <input
                                                    type="checkbox"
                                                    checked={!!studioBackdropUrl}
                                                    onChange={e => {
                                                        if (e.target.checked) {
                                                            alert("Studio 模式下暂未完全实装Emby背景图自动获取，将使用默认演示背景。");
                                                            setStudioBackdropUrl('https://image.tmdb.org/t/p/original/8uS6B0KbhDZ3G9689br09v9I7xy.jpg');
                                                        } else {
                                                            setStudioBackdropUrl(undefined);
                                                        }
                                                    }}
                                                    className="accent-amber-500"
                                                />
                                                <span className="text-xs text-slate-600 dark:text-slate-400 font-bold">使用横幅背景 (演示)</span>
                                            </div>
                                        </div>
                                    </>
                                )}
                            </div>
                        </div>

                        {/* Right: Preview Pane */}
                        <div className="flex-1 bg-slate-100 dark:bg-black p-2 flex items-center justify-center relative overflow-hidden">
                            {/* Background Grid Pattern */}
                            <div className="absolute inset-0 opacity-10 pointer-events-none" style={{ backgroundImage: 'radial-gradient(#888 1px, transparent 1px)', backgroundSize: '20px 20px' }}></div>

                            <div className="w-full h-full max-w-none shadow-2xl rounded-2xl overflow-hidden ring-4 ring-slate-900/10 dark:ring-white/10 transition-all duration-500 hover:scale-[1.005]">
                                {generatorMode === 'classic' ? (
                                    <div className="aspect-video bg-black flex items-center justify-center relative">
                                        {coverPreview ? (
                                            <img src={coverPreview} className="w-full h-full object-cover" />
                                        ) : (
                                            <div className="text-slate-500 text-sm font-mono flex flex-col items-center gap-2">
                                                <Image size={48} className="opacity-20" />
                                                <span>等待生成...</span>
                                            </div>
                                        )}
                                    </div>
                                ) : (
                                    /* Studio Preview */
                                    <div id="studio-canvas">
                                        <CoverCanvas
                                            theme={studioTheme}
                                            layoutMode={studioLayoutMode}
                                            libraryName={coverTitle}
                                            subTitle={coverSubtitle}
                                            posters={studioPosters}
                                            backdropUrl={studioBackdropUrl}
                                            currentFont={studioFont}
                                            activeTextColor={activeStudioTextColor}
                                            titleX={sTitleX}
                                            titleY={sTitleY}
                                            titleGap={sTitleGap}
                                            titleSize={sTitleSize}
                                            gridIntensity={gridIntensity}
                                            posterX={sPosterX}
                                            fanSpread={fanSpread}
                                            fanRotation={fanRotation}
                                            cycleIndex={cycleIndex}
                                        />
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