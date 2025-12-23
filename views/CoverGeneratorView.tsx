import React, { useState, useEffect, useRef } from 'react';
import {
    Download,
    Loader2,
    Server,
    Type,
    Palette,
    History,
    Eye,
    Grid3X3,
    CloudUpload,
    Settings2,
    Library,
    Image as ImageIcon
} from 'lucide-react';
import html2canvas from 'html2canvas';

import { api } from '../services/api';

const DEFAULT_POSTERS = [
    'https://images.unsplash.com/photo-1594908900066-3f47337549d8?auto=format&fit=crop&q=80&w=1200',
    'https://images.unsplash.com/photo-1536440136628-849c177e76a1?auto=format&fit=crop&q=80&w=1200',
    'https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&q=80&w=1200',
    'https://images.unsplash.com/photo-1517604931442-7e0c8ed2963c?auto=format&fit=crop&q=80&w=1200',
    'https://images.unsplash.com/photo-1440404653325-ab127d49abc1?auto=format&fit=crop&q=80&w=1200',
    'https://images.unsplash.com/photo-1485846234645-a62644f84728?auto=format&fit=crop&q=80&w=1200',
];

const THEMES = [
    // 深色混色系 (4个)
    { id: 'noir_deep', name: '暗影', isDark: true, bgStyle: 'linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)', textColor: '#FFFFFF', accent: '#ffffff' },
    { id: 'crimson_dark', name: '红月', isDark: true, bgStyle: 'linear-gradient(135deg, #1a0a0a 0%, #4a0000 70%, #000000 100%)', textColor: '#FFD7D7', accent: '#FF4B4B' },
    { id: 'emerald_mix', name: '深翠', isDark: true, bgStyle: 'linear-gradient(135deg, #0d1b1e 0%, #1b3d3d 60%, #050a0a 100%)', textColor: '#A7FFEB', accent: '#1DE9B6' },
    { id: 'golden_mix', name: '金座', isDark: true, bgStyle: 'linear-gradient(135deg, #1a1610 0%, #3d2b1f 50%, #000000 100%)', textColor: '#D4AF37', accent: '#D4AF37' },
    // 浅色混色系 (4个)
    { id: 'sunset_light', name: '暖阳', isDark: false, bgStyle: 'linear-gradient(135deg, #FFDEE9 0%, #B5FFFC 100%)', textColor: '#2C3E50', accent: '#FF7EB3' },
    { id: 'mint_dream', name: '薄荷', isDark: false, bgStyle: 'linear-gradient(135deg, #D9AFD9 0%, #97D9E1 100%)', textColor: '#1a1a1a', accent: '#74EBD5' },
    { id: 'lavender_sky', name: '薰衣草', isDark: false, bgStyle: 'linear-gradient(135deg, #eecda3 0%, #ef629f 100%)', textColor: '#FFFFFF', accent: '#FFFFFF' },
    { id: 'morni_mist', name: '晨曦', isDark: false, bgStyle: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)', textColor: '#444444', accent: '#333333' },
];

const TEXT_COLORS = [
    { name: 'Pure White', value: '#FFFFFF' },
    { name: 'Deep Black', value: '#000000' },
    { name: 'Movie Gold', value: '#D4AF37' },
    { name: 'Neon Blue', value: '#00D4FF' },
    { name: 'Vibrant Red', value: '#FF4B4B' },
];

const FONTS = [
    { id: 'bebas', name: '电影字体', family: "'Bebas Neue', cursive" },
    { id: 'mashan', name: '草书', family: "'Ma Shan Zheng', cursive" },
    { id: 'inter', name: '现代', family: "'Inter', sans-serif" },
    { id: 'orbitron', name: '科技', family: "'Orbitron', sans-serif" },
];

const LaurelWreath = ({ color }: { color: string }) => (
    <svg width="100%" height="100%" viewBox="0 0 100 100" fill={color}>
        <path d="M50,85 C35,85 20,70 20,40 C20,35 21,30 22,25 C18,30 15,40 15,50 C15,75 35,95 50,95 L50,85 Z" />
        <path d="M50,85 C65,85 80,70 80,40 C80,35 79,30 78,25 C82,30 85,40 85,50 C85,75 65,95 50,95 L50,85 Z" />
    </svg>
);

interface CoverCanvasProps {
    id?: string;
    theme: typeof THEMES[0];
    layoutMode: 'stack' | 'grid';
    libraryName: string;
    subTitle: string;
    posters: string[];
    backdropUrl?: string;
    currentFont: typeof FONTS[0];
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

export const CoverGeneratorView: React.FC = () => {
    const [layoutMode, setLayoutMode] = useState<'stack' | 'grid'>('grid');
    const [libraryName, setLibraryName] = useState('我的电影库');
    const [subTitle, setSubTitle] = useState('Personal Collection');
    const [posters, setPosters] = useState<string[]>(DEFAULT_POSTERS);
    const [backdropUrl, setBackdropUrl] = useState<string | undefined>(undefined);
    const [currentTheme, setCurrentTheme] = useState(THEMES[0]);
    const [currentFont, setCurrentFont] = useState(FONTS[0]);
    const [overrideColor, setOverrideColor] = useState<string | null>(null);
    const [showBulk, setShowBulk] = useState(false);

    // Position & Spacing Adjusters
    const [titleX, setTitleX] = useState(50);
    const [titleY, setTitleY] = useState(50);
    const [titleGap, setTitleGap] = useState(24);
    const [titleSize, setTitleSize] = useState(4.5);

    // Layout Regulators
    const [fanSpread, setFanSpread] = useState(45);
    const [fanRotation, setFanRotation] = useState(6);
    const [posterX, setPosterX] = useState(72);
    const [gridIntensity, setGridIntensity] = useState(80);

    // Emby State
    const [embyUrl, setEmbyUrl] = useState('');
    const [embyKey, setEmbyKey] = useState('');
    const [libraries, setLibraries] = useState<any[]>([]);
    const [selectedLibraryId, setSelectedLibraryId] = useState<string>('');
    const [isFetchingEmby, setIsFetchingEmby] = useState(false);
    const [status, setStatus] = useState<{ type: 'idle' | 'loading' | 'success' | 'error', msg: string }>({ type: 'idle', msg: '' });

    const activeTextColor = overrideColor || currentTheme.textColor;
    const [cycleIndex, setCycleIndex] = useState(0);

    // Load config on mount
    useEffect(() => {
        const loadConfig = async () => {
            try {
                const conf = await api.getConfig();
                if (conf?.emby) {
                    if (conf.emby.serverUrl) setEmbyUrl(conf.emby.serverUrl);
                    if (conf.emby.apiKey) setEmbyKey(conf.emby.apiKey);
                }
            } catch (e) {
                console.error("Failed to load config", e);
            }
        };
        loadConfig();
    }, []);

    useEffect(() => {
        if (layoutMode === 'stack') {
            const timer = setInterval(() => {
                setCycleIndex(prev => (prev + 1) % posters.length);
            }, 4000);
            return () => clearInterval(timer);
        }
    }, [posters.length, layoutMode]);

    const handleConnectEmby = async () => {
        if (!embyUrl || !embyKey) return alert("请完整填写 Emby 地址和 API Key");
        setIsFetchingEmby(true);
        setStatus({ type: 'loading', msg: '正在连接...' });
        try {
            const cleanUrl = embyUrl.replace(/\/$/, '');
            const response = await fetch(`${cleanUrl}/emby/Library/VirtualFolders?api_key=${embyKey}`);
            // Try both with and without /emby if failed
            if (!response.ok) {
                // Retry without /emby if needed? The user provided URL might contain it or not.
                // Standard Emby API usually is at /emby/Library/VirtualFolders ?? No, /Library/VirtualFolders directly?
                // It depends on base url. Let's assume standard behavior or try user input.
                // Actually 123pan might be different. 
                // Let's stick to simple fetch first.
                throw new Error("连接失败: " + response.statusText);
            }
            const data = await response.json();
            setLibraries(data);
            if (data.length > 0) {
                setSelectedLibraryId(data[0].Id);
                setLibraryName(data[0].Name);
                fetchPosters(data[0].Id);
            }
            setStatus({ type: 'success', msg: '同步成功' });
        } catch (e: any) {
            // Retry with/without /emby logic if needed, but for now simple error
            try {
                // Fallback try
                const cleanUrl = embyUrl.replace(/\/$/, '');
                // try without /emby if it was there, or add it?
                // usually http://host:port/emby/Library...
                const url2 = cleanUrl.endsWith('/emby')
                    ? `${cleanUrl.replace('/emby', '')}/Library/VirtualFolders?api_key=${embyKey}`
                    : `${cleanUrl}/emby/Library/VirtualFolders?api_key=${embyKey}`;

                const resp2 = await fetch(url2);
                if (resp2.ok) {
                    const data = await resp2.json();
                    setLibraries(data);
                    if (data.length > 0) {
                        setSelectedLibraryId(data[0].Id);
                        setLibraryName(data[0].Name);
                        // Update embyUrl to working one? maybe not necessary
                        fetchPosters(data[0].Id);
                    }
                    setStatus({ type: 'success', msg: '同步成功' });
                    return;
                }
            } catch (_) { }

            setStatus({ type: 'error', msg: e.message });
        } finally {
            setIsFetchingEmby(false);
        }
    };

    const fetchPosters = async (libraryId: string) => {
        const cleanUrl = embyUrl.replace(/\/$/, '');
        // Need to handle if /emby is part of URL or not.
        // simpler to try one, if fail try other? 
        // Just reuse the working pattern? 
        // Emby API: /Items

        // We will simple construct URL.
        const baseUrl = cleanUrl.includes('/emby') ? cleanUrl : `${cleanUrl}/emby`;
        // Wait, some users don't have /emby.
        // Let's rely on user provided URL mostly.

        try {
            let url = `${cleanUrl}/Items?api_key=${embyKey}&ParentId=${libraryId}&Recursive=true&IncludeItemTypes=Movie,Series&Limit=30&SortBy=Random`;
            // Check if we need to add /emby
            // Best way: use /emby/Items if cleanUrl doesn't end with /emby
            // But standard is http://host:8096/emby/Items if installed with prefix.
            // Or http://host:8096/Items if not? Usually /emby is present.

            const resItems = await fetch(url);
            if (!resItems.ok) {
                // try adding /emby
                url = `${cleanUrl}/emby/Items?api_key=${embyKey}&ParentId=${libraryId}&Recursive=true&IncludeItemTypes=Movie,Series&Limit=30&SortBy=Random`;
                const res2 = await fetch(url);
                if (res2.ok) {
                    const itemsData = await res2.json();
                    if (itemsData.Items && itemsData.Items.length > 0) {
                        setPosters(itemsData.Items.map((it: any) => `${cleanUrl}/emby/Items/${it.Id}/Images/Primary?api_key=${embyKey}&maxWidth=400`));
                    }
                    return;
                }
            } else {
                const itemsData = await resItems.json();
                if (itemsData.Items && itemsData.Items.length > 0) {
                    setPosters(itemsData.Items.map((it: any) => `${cleanUrl}/Items/${it.Id}/Images/Primary?api_key=${embyKey}&maxWidth=400`));
                }
            }

        } catch (e) { console.error(e); }
    };

    const handleApplyToEmby = async () => {
        if (!selectedLibraryId || !embyUrl || !embyKey) return alert("请先同步库");
        const element = document.getElementById('main-preview');
        if (!element) return;
        setStatus({ type: 'loading', msg: '渲染 4K 封面...' });
        try {
            const canvas = await html2canvas(element, { useCORS: true, scale: 2, backgroundColor: null });
            canvas.toBlob(async (blob: Blob | null) => {
                if (!blob) throw new Error("渲染失败");
                const cleanUrl = embyUrl.replace(/\/$/, '');
                let uploadUrl = `${cleanUrl}/Items/${selectedLibraryId}/Images/Primary?api_key=${embyKey}`;

                // Try uploading
                let response = await fetch(uploadUrl, { method: 'POST', headers: { 'Content-Type': 'image/png' }, body: blob });
                if (!response.ok) {
                    uploadUrl = `${cleanUrl}/emby/Items/${selectedLibraryId}/Images/Primary?api_key=${embyKey}`;
                    response = await fetch(uploadUrl, { method: 'POST', headers: { 'Content-Type': 'image/png' }, body: blob });
                }

                if (response.ok) {
                    setStatus({ type: 'success', msg: '上传成功' });
                    setTimeout(() => setStatus({ type: 'idle', msg: '' }), 3000);
                } else throw new Error("上传失败");
            }, 'image/png');
        } catch (e: any) { setStatus({ type: 'error', msg: e.message }); }
    };

    return (
        <div className="flex h-[calc(100vh-64px)] overflow-hidden font-['Inter',_sans-serif] bg-[#050505] text-zinc-100 rounded-xl border border-zinc-800/50 shadow-2xl">
            {/* Sidebar - Compact Layout */}
            <aside className="w-[320px] border-r border-zinc-800/50 p-5 flex flex-col gap-5 z-50 shrink-0 overflow-y-auto scrollbar-hide bg-[#0a0a0a]">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-zinc-100"><Library className="w-4 h-4 text-black" /></div>
                    <div>
                        <span className="text-[10px] font-black tracking-widest uppercase text-white">EMBY COVER</span>
                        <span className="block text-[8px] font-bold text-zinc-600">PRO STUDIO V8.0</span>
                    </div>
                </div>

                {/* Action Status */}
                {status.msg && (
                    <div className={`px-3 py-2 rounded-lg text-[10px] font-bold flex items-center gap-2 border ${status.type === 'error' ? 'bg-red-500/10 text-red-400 border-red-500/20' : status.type === 'success' ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-blue-500/10 text-blue-400 border-blue-500/20'}`}>
                        {status.type === 'loading' && <Loader2 className="w-3 h-3 animate-spin" />}
                        <span>{status.msg}</span>
                    </div>
                )}

                <div className="space-y-6">
                    {/* Section: Emby Connection */}
                    <section className="space-y-3">
                        <div className="flex items-center justify-between text-[9px] font-black text-zinc-500 uppercase tracking-widest"><span className="flex items-center gap-2"><Server className="w-3 h-3" /> 服务器</span></div>
                        <div className="space-y-2 bg-zinc-900/50 p-3 rounded-xl border border-zinc-800/50">
                            <input placeholder="URL" value={embyUrl} onChange={e => setEmbyUrl(e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-lg px-3 py-1.5 text-[10px] outline-none" />
                            <input placeholder="Key" type="password" value={embyKey} onChange={e => setEmbyKey(e.target.value)} className="w-full bg-black/50 border border-zinc-800 rounded-lg px-3 py-1.5 text-[10px] outline-none" />
                            <button onClick={handleConnectEmby} className="w-full py-2 bg-zinc-100 text-black text-[9px] font-black rounded-lg uppercase hover:bg-white active:scale-95 transition-all">同步</button>
                        </div>
                    </section>

                    {/* Section: Library Text */}
                    <section className="space-y-3">
                        <div className="flex items-center justify-between text-[9px] font-black text-zinc-500 uppercase tracking-widest"><span className="flex items-center gap-2"><Type className="w-3 h-3" /> 基础信息</span></div>
                        <div className="space-y-2">
                            <input placeholder="库名称" value={libraryName} onChange={e => setLibraryName(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-[10px] outline-none" />
                            <input placeholder="副标题" value={subTitle} onChange={e => setSubTitle(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-1.5 text-[10px] outline-none" />
                        </div>
                    </section>

                    {/* Section: Themes - 8 Mixed Color Blocks (4 Dark, 4 Light) */}
                    <section className="space-y-3">
                        <div className="flex items-center justify-between text-[9px] font-black text-zinc-500 uppercase tracking-widest"><span className="flex items-center gap-2"><Palette className="w-3 h-3" /> 风格预设</span></div>
                        <div className="grid grid-cols-4 gap-2">
                            {THEMES.map(theme => (
                                <button key={theme.id} onClick={() => setCurrentTheme(theme)} className={`group relative h-10 rounded-lg border-2 overflow-hidden transition-all ${currentTheme.id === theme.id ? 'border-white scale-110 shadow-lg z-10' : 'border-zinc-800 opacity-70 hover:opacity-100'}`} title={theme.name}>
                                    <div className="absolute inset-0" style={{ background: theme.bgStyle }} />
                                    <div className="absolute inset-0 flex items-center justify-center bg-black/10 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <span className="text-[7px] font-black text-white drop-shadow-md uppercase text-center">{theme.name}</span>
                                    </div>
                                    {currentTheme.id === theme.id && <div className="absolute top-0.5 right-0.5 w-1.5 h-1.5 bg-white rounded-full border border-black shadow-sm" />}
                                </button>
                            ))}
                        </div>
                    </section>

                    {/* Section: Precision Adjusters - Kept */}
                    <section className="space-y-3">
                        <div className="flex items-center justify-between text-[9px] font-black text-zinc-500 uppercase tracking-widest"><span className="flex items-center gap-2"><Settings2 className="w-3 h-3" /> 精准调节器</span></div>
                        <div className="bg-zinc-900/30 p-4 rounded-xl border border-zinc-800/50 space-y-4">
                            <div className="space-y-3">
                                <div className="space-y-1">
                                    <div className="flex justify-between text-[8px] uppercase font-bold text-zinc-600"><span>水平坐标 (X)</span><span>{titleX}%</span></div>
                                    <input type="range" min="0" max="100" value={titleX} onChange={e => setTitleX(parseInt(e.target.value))} className="w-full h-1 bg-zinc-800 appearance-none accent-white rounded-full cursor-pointer" />
                                </div>
                                <div className="space-y-1">
                                    <div className="flex justify-between text-[8px] uppercase font-bold text-zinc-600"><span>垂直坐标 (Y)</span><span>{titleY}%</span></div>
                                    <input type="range" min="0" max="100" value={titleY} onChange={e => setTitleY(parseInt(e.target.value))} className="w-full h-1 bg-zinc-800 appearance-none accent-white rounded-full cursor-pointer" />
                                </div>
                                <div className="space-y-1">
                                    <div className="flex justify-between text-[8px] uppercase font-bold text-zinc-600"><span>标题字号</span><span>{titleSize}vw</span></div>
                                    <input type="range" min="1" max="15" step="0.1" value={titleSize} onChange={e => setTitleSize(parseFloat(e.target.value))} className="w-full h-1 bg-zinc-800 appearance-none accent-white rounded-full cursor-pointer" />
                                </div>
                                <div className="space-y-1">
                                    <div className="flex justify-between text-[8px] uppercase font-bold text-zinc-600"><span>文字间距</span><span>{titleGap}px</span></div>
                                    <input type="range" min="0" max="150" value={titleGap} onChange={e => setTitleGap(parseInt(e.target.value))} className="w-full h-1 bg-zinc-800 appearance-none accent-white rounded-full cursor-pointer" />
                                </div>
                            </div>

                            <div className="pt-3 border-t border-zinc-800/50 space-y-3">
                                {layoutMode === 'stack' ? (
                                    <>
                                        <div className="space-y-1">
                                            <div className="flex justify-between text-[8px] uppercase font-bold text-zinc-600"><span>堆叠展开度</span><span>{fanSpread}px</span></div>
                                            <input type="range" min="0" max="150" value={fanSpread} onChange={e => setFanSpread(parseInt(e.target.value))} className="w-full h-1 bg-zinc-800 appearance-none accent-white rounded-full cursor-pointer" />
                                        </div>
                                        <div className="space-y-1">
                                            <div className="flex justify-between text-[8px] uppercase font-bold text-zinc-600"><span>旋转倾角</span><span>{fanRotation}°</span></div>
                                            <input type="range" min="0" max="45" value={fanRotation} onChange={e => setFanRotation(parseInt(e.target.value))} className="w-full h-1 bg-zinc-800 appearance-none accent-white rounded-full cursor-pointer" />
                                        </div>
                                        <div className="space-y-1">
                                            <div className="flex justify-between text-[8px] uppercase font-bold text-zinc-600"><span>海报横移 (X)</span><span>{posterX}%</span></div>
                                            <input type="range" min="0" max="100" value={posterX} onChange={e => setPosterX(parseInt(e.target.value))} className="w-full h-1 bg-zinc-800 appearance-none accent-white rounded-full cursor-pointer" />
                                        </div>
                                    </>
                                ) : (
                                    <div className="space-y-1">
                                        <div className="flex justify-between text-[8px] uppercase font-bold text-zinc-600"><span>墙幕透明度</span><span>{gridIntensity}%</span></div>
                                        <input type="range" min="10" max="100" value={gridIntensity} onChange={e => setGridIntensity(parseInt(e.target.value))} className="w-full h-1 bg-zinc-800 appearance-none accent-white rounded-full cursor-pointer" />
                                    </div>
                                )}
                            </div>
                        </div>
                    </section>

                    {/* Section: Typography & Colors - Kept */}
                    <section className="space-y-3">
                        <div className="flex items-center justify-between text-[9px] font-black text-zinc-500 uppercase tracking-widest"><span className="flex items-center gap-2"><Type className="w-3 h-3" /> 文字样式</span></div>
                        <div className="grid grid-cols-2 gap-2">
                            {FONTS.map(f => (
                                <button key={f.id} onClick={() => setCurrentFont(f)} className={`py-2 rounded-lg border text-[8px] font-black uppercase transition-all ${currentFont.id === f.id ? 'bg-white text-black border-white' : 'bg-zinc-900 text-zinc-500 border-zinc-800'}`} style={{ fontFamily: f.family }}>{f.name}</button>
                            ))}
                        </div>
                        <div className="flex gap-2">
                            {TEXT_COLORS.map(c => (
                                <button key={c.value} onClick={() => setOverrideColor(c.value)} className={`w-full h-5 rounded-md border border-zinc-800 ${overrideColor === c.value ? 'ring-2 ring-white' : ''}`} style={{ backgroundColor: c.value }} />
                            ))}
                            <button onClick={() => { setOverrideColor(null); setBackdropUrl(undefined); }} className="w-full h-5 rounded-md border border-zinc-800 flex items-center justify-center text-[8px] text-zinc-500 bg-zinc-900"><History className="w-2 h-2" /></button>
                        </div>
                    </section>
                </div>

                {/* Global Action */}
                <div className="mt-auto pt-4 border-t border-zinc-800/50">
                    <button onClick={handleApplyToEmby} className="w-full py-3 rounded-xl font-black text-[10px] uppercase bg-green-600 text-white shadow-lg hover:bg-green-500 transition-all flex items-center justify-center gap-2">
                        <CloudUpload className="w-4 h-4" /> 同步至 EMBY
                    </button>
                </div>
            </aside>

            {/* Main Content Area */}
            <main className="flex-1 relative flex flex-col bg-[#050505]">
                <header className="h-16 border-b border-zinc-800/30 flex items-center justify-between px-8 bg-[#0a0a0a]/80 backdrop-blur-md z-40">
                    <div className="flex gap-3">
                        <button onClick={() => setShowBulk(false)} className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-[9px] font-black uppercase transition-all ${!showBulk ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-200'}`}><Eye className="w-3 h-3" /> 画布</button>
                        <button onClick={() => setShowBulk(true)} className={`flex items-center gap-2 px-4 py-1.5 rounded-full text-[9px] font-black uppercase transition-all ${showBulk ? 'bg-white text-black' : 'text-zinc-500 hover:text-zinc-200'}`}><Grid3X3 className="w-3 h-3" /> 预览</button>
                    </div>

                    <div className="flex items-center gap-6">
                        <div className="flex bg-zinc-900 p-1 rounded-full border border-zinc-800">
                            <button onClick={() => setLayoutMode('stack')} className={`px-4 py-1 rounded-full text-[9px] font-black uppercase transition-all ${layoutMode === 'stack' ? 'bg-zinc-700 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}>堆叠</button>
                            <button onClick={() => setLayoutMode('grid')} className={`px-4 py-1 rounded-full text-[9px] font-black uppercase transition-all ${layoutMode === 'grid' ? 'bg-zinc-700 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}>墙幕</button>
                        </div>
                        <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_#22c55e] animate-pulse" />
                    </div>
                </header>

                <div className="flex-1 overflow-y-auto p-12 design-grid scrollbar-hide">
                    {showBulk ? (
                        <div className="grid grid-cols-2 gap-10 max-w-6xl mx-auto pb-20">
                            {THEMES.map(theme => (
                                <div key={theme.id} className="group relative cursor-pointer" onClick={() => { setCurrentTheme(theme); setShowBulk(false); }}>
                                    <div className="scale-95 group-hover:scale-100 transition-all duration-500 shadow-2xl rounded-2xl overflow-hidden">
                                        <CoverCanvas theme={theme} layoutMode={layoutMode} libraryName={libraryName} subTitle={subTitle} posters={posters} backdropUrl={backdropUrl} currentFont={currentFont} activeTextColor={overrideColor || theme.textColor} titleX={titleX} titleY={titleY} titleGap={titleGap} titleSize={titleSize} gridIntensity={gridIntensity} posterX={posterX} fanSpread={fanSpread} fanRotation={fanRotation} cycleIndex={cycleIndex} isSmall />
                                    </div>
                                    <div className="absolute top-4 left-4 text-[9px] font-black uppercase bg-zinc-900 px-2 py-1 rounded border border-zinc-800">{theme.name}</div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex items-center justify-center min-h-full">
                            <div className="w-full max-w-[1000px] group transition-all duration-700">
                                <CoverCanvas id="main-preview" theme={currentTheme} layoutMode={layoutMode} libraryName={libraryName} subTitle={subTitle} posters={posters} backdropUrl={backdropUrl} currentFont={currentFont} activeTextColor={activeTextColor} titleX={titleX} titleY={titleY} titleGap={titleGap} titleSize={titleSize} gridIntensity={gridIntensity} posterX={posterX} fanSpread={fanSpread} fanRotation={fanRotation} cycleIndex={cycleIndex} />
                                <div className="mt-8 flex justify-center gap-4 opacity-0 group-hover:opacity-100 transition-all duration-700 translate-y-4 group-hover:translate-y-0">
                                    <span className="text-[9px] font-black tracking-widest text-zinc-700 uppercase">Studio Engine Active • 4K Ready</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </main>

            <style>{`
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        @keyframes scrollUp { from { transform: translateY(0); } to { transform: translateY(-33.33%); } }
        @keyframes scrollDown { from { transform: translateY(-33.33%); } to { transform: translateY(0); } }
        .animate-scrollUp { animation: scrollUp linear infinite; }
        .animate-scrollDown { animation: scrollDown linear infinite; }
        input[type="range"]::-webkit-slider-thumb { 
          -webkit-appearance: none; width: 12px; height: 12px; 
          background: #fff; border-radius: 50%; border: 2px solid #000;
          cursor: pointer; box-shadow: 0 2px 6px rgba(0,0,0,0.4);
        }
        .design-grid {
          background-image: radial-gradient(#1a1a1a 1px, transparent 1px);
          background-size: 30px 30px;
        }
      `}</style>
        </div>
    );
};
