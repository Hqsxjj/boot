import React, { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';
import {
    Search,
    Film,
    Tv,
    Star,
    Calendar,
    Download,
    Copy,
    RefreshCw,
    X,
    ExternalLink,
    Sparkles,
    TrendingUp,
    Play,
    Info,
    CheckCircle2,
    AlertCircle,
    Loader2
} from 'lucide-react';

interface ShareLink {
    source: string;
    link: string | null;
    code: string | null;
}

interface Resource {
    id: string;
    title: string;
    original_title?: string;
    year: number;
    type: 'movie' | 'tv';
    quality: string;
    poster_url: string;
    backdrop_url?: string;
    rating?: number;
    description?: string;
    share_links?: ShareLink[];
    source?: string;
    share_link?: string | null;
    share_code?: string | null;
}

export const ResourceSearchView: React.FC = () => {
    const [searchQuery, setSearchQuery] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const [searchResults, setSearchResults] = useState<Resource[]>([]);
    const [trendingResources, setTrendingResources] = useState<Resource[]>([]);
    const [isLoadingTrending, setIsLoadingTrending] = useState(true);
    const [selectedResource, setSelectedResource] = useState<Resource | null>(null);
    const [toast, setToast] = useState<string | null>(null);
    const [aiEnabled, setAiEnabled] = useState<boolean | null>(null);
    const [searchMessage, setSearchMessage] = useState<string | null>(null);
    const searchInputRef = useRef<HTMLInputElement>(null);

    useEffect(() => {
        fetchTrending();
    }, []);

    const fetchTrending = async () => {
        setIsLoadingTrending(true);
        try {
            const response = await api.getTrendingResources();
            if (response.success) {
                setTrendingResources(response.data || []);
            }
        } catch (e) {
            console.error('Failed to fetch trending:', e);
        } finally {
            setIsLoadingTrending(false);
        }
    };

    const handleSearch = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!searchQuery.trim()) return;

        setIsSearching(true);
        setSearchResults([]);
        setSearchMessage(null);

        try {
            const response = await api.searchResources(searchQuery);
            if (response.success) {
                setSearchResults(response.data || []);
                setAiEnabled((response as any).ai_enabled);
                if ((response as any).message) {
                    setSearchMessage((response as any).message);
                }
            } else {
                setToast((response as any).error || '搜索失败');
                setTimeout(() => setToast(null), 3000);
            }
        } catch (e: any) {
            console.error('Search failed:', e);
            setToast('搜索请求失败，请检查网络连接');
            setTimeout(() => setToast(null), 3000);
        } finally {
            setIsSearching(false);
        }
    };

    const copyToClipboard = (text: string, label: string = '链接') => {
        navigator.clipboard.writeText(text);
        setToast(`${label}已复制到剪贴板`);
        setTimeout(() => setToast(null), 2000);
    };

    const handleResourceClick = (resource: Resource) => {
        setSelectedResource(resource);
    };

    const closeModal = () => {
        setSelectedResource(null);
    };

    const glassCardClass = "bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl rounded-xl border-[0.5px] border-white/40 dark:border-white/10 shadow-[0_8px_30px_rgb(0,0,0,0.04)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.2)] ring-1 ring-white/50 dark:ring-white/5 inset";
    const inputClass = "w-full px-4 py-3 rounded-xl border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-brand-500 outline-none transition-all placeholder:text-slate-400 text-base backdrop-blur-sm shadow-inner";

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-300">
            {/* Toast Notification */}
            {toast && (
                <div className="fixed top-6 right-6 bg-slate-800/90 backdrop-blur-md text-white px-6 py-3 rounded-xl shadow-2xl z-50 flex items-center gap-3 font-medium border-[0.5px] border-slate-700/50">
                    <CheckCircle2 size={18} className="text-green-400" />
                    {toast}
                </div>
            )}

            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                    <h2 className="text-2xl font-bold text-slate-800 dark:text-white tracking-tight drop-shadow-sm flex items-center gap-3">
                        <div className="p-2 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl text-white shadow-lg shadow-purple-500/20">
                            <Sparkles size={24} />
                        </div>
                        资源搜索
                    </h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                        搜索全网 115 网盘分享链接，支持电影、电视剧资源
                    </p>
                </div>
            </div>

            {/* Search Box */}
            <section className={`${glassCardClass} p-6`}>
                <form onSubmit={handleSearch} className="flex gap-4">
                    <div className="flex-1 relative group">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-brand-500 transition-colors" size={20} />
                        <input
                            ref={searchInputRef}
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="输入电影或电视剧名称搜索资源..."
                            className={`${inputClass} pl-12 pr-4 text-lg`}
                            disabled={isSearching}
                        />
                    </div>
                    <button
                        type="submit"
                        disabled={isSearching || !searchQuery.trim()}
                        className="px-8 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-xl font-bold shadow-lg shadow-purple-500/20 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                        {isSearching ? (
                            <>
                                <Loader2 className="animate-spin" size={18} />
                                搜索中...
                            </>
                        ) : (
                            <>
                                <Search size={18} />
                                搜索
                            </>
                        )}
                    </button>
                </form>

                {/* AI Status Hint */}
                {aiEnabled !== null && (
                    <div className={`mt-4 flex items-center gap-2 text-xs ${aiEnabled ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'}`}>
                        {aiEnabled ? (
                            <>
                                <CheckCircle2 size={14} />
                                AI 搜索已启用 - 使用您配置的 AI 模型进行智能搜索
                            </>
                        ) : (
                            <>
                                <AlertCircle size={14} />
                                AI 未配置 - 请在「网盘整理」页面设置 AI 配置以启用智能搜索
                            </>
                        )}
                    </div>
                )}

                {searchMessage && (
                    <div className="mt-3 p-3 bg-amber-50/50 dark:bg-amber-900/10 rounded-lg border-[0.5px] border-amber-200/50 dark:border-amber-800/50 text-sm text-amber-700 dark:text-amber-300">
                        {searchMessage}
                    </div>
                )}
            </section>

            {/* Search Results */}
            {searchResults.length > 0 && (
                <section className="space-y-4">
                    <h3 className="text-lg font-bold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                        <Search size={20} />
                        搜索结果
                        <span className="text-sm font-normal text-slate-500">({searchResults.length} 条结果)</span>
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                        {searchResults.map((resource, index) => (
                            <ResourceCard
                                key={`search-${index}`}
                                resource={resource}
                                onClick={() => handleResourceClick(resource)}
                            />
                        ))}
                    </div>
                </section>
            )}

            {/* Trending Resources */}
            <section className="space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-bold text-slate-700 dark:text-slate-200 flex items-center gap-2">
                        <TrendingUp size={20} className="text-pink-500" />
                        热门资源
                    </h3>
                    <button
                        onClick={fetchTrending}
                        disabled={isLoadingTrending}
                        className="text-sm text-slate-500 hover:text-brand-600 flex items-center gap-1 transition-colors"
                    >
                        <RefreshCw size={14} className={isLoadingTrending ? 'animate-spin' : ''} />
                        刷新
                    </button>
                </div>

                {isLoadingTrending ? (
                    <div className="flex justify-center items-center py-20">
                        <Loader2 className="animate-spin text-brand-500" size={32} />
                    </div>
                ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
                        {trendingResources.map((resource) => (
                            <ResourceCard
                                key={resource.id}
                                resource={resource}
                                onClick={() => handleResourceClick(resource)}
                            />
                        ))}
                    </div>
                )}
            </section>

            {/* Resource Detail Modal */}
            {selectedResource && (
                <ResourceDetailModal
                    resource={selectedResource}
                    onClose={closeModal}
                    onCopy={copyToClipboard}
                />
            )}
        </div>
    );
};

// Resource Card Component
const ResourceCard: React.FC<{
    resource: Resource;
    onClick: () => void;
}> = ({ resource, onClick }) => {
    const [imageLoaded, setImageLoaded] = useState(false);
    const [imageError, setImageError] = useState(false);

    return (
        <div
            onClick={onClick}
            className="group relative rounded-xl overflow-hidden cursor-pointer transform transition-all duration-300 hover:scale-105 hover:shadow-2xl hover:shadow-black/20"
        >
            {/* Poster */}
            <div className="aspect-[2/3] relative bg-slate-200 dark:bg-slate-800">
                {!imageLoaded && !imageError && (
                    <div className="absolute inset-0 flex items-center justify-center">
                        <Loader2 className="animate-spin text-slate-400" size={24} />
                    </div>
                )}
                {imageError ? (
                    <div className="absolute inset-0 flex flex-col items-center justify-center bg-gradient-to-br from-slate-700 to-slate-900 text-slate-400">
                        <Film size={32} />
                        <span className="text-xs mt-2">暂无海报</span>
                    </div>
                ) : (
                    <img
                        src={resource.poster_url}
                        alt={resource.title}
                        onLoad={() => setImageLoaded(true)}
                        onError={() => setImageError(true)}
                        className={`w-full h-full object-cover transition-opacity duration-300 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
                    />
                )}

                {/* Overlay on hover */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                    <div className="absolute bottom-0 left-0 right-0 p-3">
                        <button className="w-full py-2 bg-white/20 backdrop-blur-sm rounded-lg text-white text-xs font-medium flex items-center justify-center gap-1 hover:bg-white/30 transition-colors">
                            <Play size={14} />
                            查看资源
                        </button>
                    </div>
                </div>

                {/* Quality Badge */}
                <div className="absolute top-2 left-2 px-2 py-0.5 bg-black/60 backdrop-blur-sm rounded text-[10px] font-bold text-white">
                    {resource.quality}
                </div>

                {/* Type Badge */}
                <div className={`absolute top-2 right-2 p-1.5 rounded-full ${resource.type === 'movie' ? 'bg-purple-500' : 'bg-blue-500'} text-white`}>
                    {resource.type === 'movie' ? <Film size={12} /> : <Tv size={12} />}
                </div>

                {/* Rating */}
                {resource.rating && (
                    <div className="absolute bottom-2 left-2 flex items-center gap-1 px-2 py-0.5 bg-black/60 backdrop-blur-sm rounded text-[10px] font-bold text-amber-400">
                        <Star size={10} fill="currentColor" />
                        {resource.rating.toFixed(1)}
                    </div>
                )}
            </div>

            {/* Title */}
            <div className="absolute -bottom-full group-hover:bottom-0 left-0 right-0 bg-gradient-to-t from-black via-black/90 to-transparent p-3 pt-8 transition-all duration-300">
                <h4 className="font-bold text-white text-sm truncate">{resource.title}</h4>
                {resource.original_title && resource.original_title !== resource.title && (
                    <p className="text-[10px] text-slate-400 truncate">{resource.original_title}</p>
                )}
                <div className="flex items-center gap-2 mt-1 text-[10px] text-slate-400">
                    <span className="flex items-center gap-0.5">
                        <Calendar size={10} />
                        {resource.year}
                    </span>
                </div>
            </div>

            {/* Static Title (visible when not hovering) */}
            <div className="group-hover:opacity-0 transition-opacity duration-300 absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/60 to-transparent p-3 pt-10">
                <h4 className="font-bold text-white text-sm truncate">{resource.title}</h4>
                <div className="flex items-center gap-2 mt-0.5 text-[10px] text-slate-400">
                    <Calendar size={10} />
                    {resource.year}
                </div>
            </div>
        </div>
    );
};

// Resource Detail Modal
const ResourceDetailModal: React.FC<{
    resource: Resource;
    onClose: () => void;
    onCopy: (text: string, label?: string) => void;
}> = ({ resource, onClose, onCopy }) => {
    const [imageError, setImageError] = useState(false);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
            {/* Backdrop */}
            <div className="absolute inset-0 bg-black/60 backdrop-blur-md animate-in fade-in duration-300" />

            {/* Modal Content */}
            <div
                onClick={(e) => e.stopPropagation()}
                className="relative w-full max-w-2xl bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl rounded-2xl shadow-2xl overflow-hidden animate-in zoom-in-95 slide-in-from-bottom-4 duration-300 border-[0.5px] border-white/20 dark:border-white/10"
            >
                {/* Close Button */}
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 z-10 p-2 bg-black/40 hover:bg-black/60 text-white rounded-full transition-colors"
                >
                    <X size={20} />
                </button>

                {/* Backdrop Image */}
                <div className="relative h-48 bg-gradient-to-br from-purple-600 to-pink-600">
                    {resource.backdrop_url && !imageError ? (
                        <img
                            src={resource.backdrop_url}
                            alt={resource.title}
                            onError={() => setImageError(true)}
                            className="w-full h-full object-cover opacity-60"
                        />
                    ) : null}
                    <div className="absolute inset-0 bg-gradient-to-t from-white dark:from-slate-900 via-transparent to-transparent" />
                </div>

                {/* Content */}
                <div className="relative -mt-20 px-6 pb-6">
                    <div className="flex gap-5">
                        {/* Poster */}
                        <div className="w-32 shrink-0">
                            <img
                                src={resource.poster_url}
                                alt={resource.title}
                                className="w-full aspect-[2/3] object-cover rounded-xl shadow-xl border-4 border-white dark:border-slate-800"
                            />
                        </div>

                        {/* Info */}
                        <div className="flex-1 pt-16">
                            <h3 className="text-2xl font-bold text-slate-900 dark:text-white">{resource.title}</h3>
                            {resource.original_title && resource.original_title !== resource.title && (
                                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">{resource.original_title}</p>
                            )}

                            <div className="flex flex-wrap items-center gap-3 mt-3">
                                <span className={`px-2 py-1 rounded-full text-xs font-bold ${resource.type === 'movie' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'}`}>
                                    {resource.type === 'movie' ? '电影' : '剧集'}
                                </span>
                                <span className="flex items-center gap-1 text-sm text-slate-600 dark:text-slate-400">
                                    <Calendar size={14} />
                                    {resource.year}
                                </span>
                                <span className="px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded text-xs font-bold text-slate-600 dark:text-slate-300">
                                    {resource.quality}
                                </span>
                                {resource.rating && (
                                    <span className="flex items-center gap-1 text-sm text-amber-600">
                                        <Star size={14} fill="currentColor" />
                                        {resource.rating.toFixed(1)}
                                    </span>
                                )}
                            </div>

                            {resource.description && (
                                <p className="mt-4 text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                                    {resource.description}
                                </p>
                            )}
                        </div>
                    </div>

                    {/* Share Links */}
                    <div className="mt-6">
                        <h4 className="font-bold text-slate-700 dark:text-slate-200 mb-3 flex items-center gap-2">
                            <Download size={18} className="text-brand-500" />
                            资源链接
                        </h4>

                        <div className="space-y-2">
                            {resource.share_links && resource.share_links.length > 0 ? (
                                resource.share_links.map((link, index) => (
                                    <div
                                        key={index}
                                        className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border-[0.5px] border-slate-200 dark:border-slate-700"
                                    >
                                        <div className="flex items-center gap-3">
                                            <div className="p-2 bg-orange-100 dark:bg-orange-900/20 rounded-lg text-orange-600 dark:text-orange-400">
                                                <ExternalLink size={16} />
                                            </div>
                                            <div>
                                                <div className="font-medium text-sm text-slate-700 dark:text-slate-200">
                                                    {link.source}
                                                </div>
                                                {link.code && (
                                                    <div className="text-xs text-slate-500 dark:text-slate-400">
                                                        提取码: <code className="bg-slate-200 dark:bg-slate-700 px-1 rounded">{link.code}</code>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {link.link ? (
                                                <>
                                                    <button
                                                        onClick={() => onCopy(link.link!, '链接')}
                                                        className="px-3 py-1.5 bg-brand-50 dark:bg-brand-900/20 text-brand-600 dark:text-brand-400 rounded-lg text-xs font-medium hover:bg-brand-100 dark:hover:bg-brand-900/40 transition-colors flex items-center gap-1"
                                                    >
                                                        <Copy size={12} />
                                                        复制
                                                    </button>
                                                    <a
                                                        href={link.link}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="px-3 py-1.5 bg-orange-500 text-white rounded-lg text-xs font-medium hover:bg-orange-600 transition-colors flex items-center gap-1"
                                                    >
                                                        <ExternalLink size={12} />
                                                        打开
                                                    </a>
                                                </>
                                            ) : (
                                                <span className="text-xs text-slate-400">链接暂不可用</span>
                                            )}
                                        </div>
                                    </div>
                                ))
                            ) : resource.share_link ? (
                                <div className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border-[0.5px] border-slate-200 dark:border-slate-700">
                                    <div className="flex items-center gap-3">
                                        <div className="p-2 bg-orange-100 dark:bg-orange-900/20 rounded-lg text-orange-600 dark:text-orange-400">
                                            <ExternalLink size={16} />
                                        </div>
                                        <div>
                                            <div className="font-medium text-sm text-slate-700 dark:text-slate-200">
                                                {resource.source || '115 网盘'}
                                            </div>
                                            {resource.share_code && (
                                                <div className="text-xs text-slate-500 dark:text-slate-400">
                                                    提取码: <code className="bg-slate-200 dark:bg-slate-700 px-1 rounded">{resource.share_code}</code>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={() => onCopy(resource.share_link!, '链接')}
                                            className="px-3 py-1.5 bg-brand-50 dark:bg-brand-900/20 text-brand-600 dark:text-brand-400 rounded-lg text-xs font-medium hover:bg-brand-100 dark:hover:bg-brand-900/40 transition-colors flex items-center gap-1"
                                        >
                                            <Copy size={12} />
                                            复制
                                        </button>
                                        <a
                                            href={resource.share_link}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="px-3 py-1.5 bg-orange-500 text-white rounded-lg text-xs font-medium hover:bg-orange-600 transition-colors flex items-center gap-1"
                                        >
                                            <ExternalLink size={12} />
                                            打开
                                        </a>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex items-center justify-center p-6 bg-slate-50 dark:bg-slate-800/30 rounded-xl border-[0.5px] border-dashed border-slate-300 dark:border-slate-700 text-slate-500 dark:text-slate-400">
                                    <Info size={16} className="mr-2" />
                                    暂无可用资源链接
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Tip */}
                    <div className="mt-4 p-3 bg-amber-50/50 dark:bg-amber-900/10 rounded-xl border-[0.5px] border-amber-200/50 dark:border-amber-800/50 text-xs text-amber-700 dark:text-amber-300 flex items-start gap-2">
                        <Info size={14} className="shrink-0 mt-0.5" />
                        <span>
                            提示：资源链接来自全网搜索，请确保在转存前检查资源内容。配置 AI 后可获得更精准的搜索结果。
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
};
