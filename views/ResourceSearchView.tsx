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
    Loader2,
    Bell,
    Plus,
    Trash2,
    FileText,
    CheckSquare,
    Square,
    Save
} from 'lucide-react';

interface ShareFile {
    id: string;
    name: string;
    size: number;
    is_directory: boolean;
    time: string;
}

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
    cloud_type?: string;
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
    const [activeTab, setActiveTab] = useState<'search' | 'subscription'>('search');

    const searchInputRef = useRef<HTMLInputElement>(null);

    // Share File Modal State
    const [showFileModal, setShowFileModal] = useState(false);
    const [shareFiles, setShareFiles] = useState<ShareFile[]>([]);
    const [selectedFileIds, setSelectedFileIds] = useState<Set<string>>(new Set());
    const [isFileLoading, setIsFileLoading] = useState(false);
    const [sharingResource, setSharingResource] = useState<{ shareCode: string; accessCode: string; resourceTitle: string } | null>(null);


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

    const handlePreviewContent = async (resource: Resource) => {
        const link = resource.share_link || resource.share_links?.[0]?.link;
        if (!link) return;

        // Simple parsing for 115 links
        // Format: https://115.com/s/sw3xxxx?password=yyyy
        const match = link.match(/115\.com\/s\/([a-z0-9]+)/i);
        if (!match) {
            setToast('不支持的链接格式');
            setTimeout(() => setToast(null), 3000);
            return;
        }

        const shareCode = match[1];
        let accessCode = '';
        try {
            const urlObj = new URL(link);
            accessCode = urlObj.searchParams.get('password') || '';
        } catch (e) {
            // URL parse error, maybe partial url
        }

        setSharingResource({ shareCode, accessCode, resourceTitle: resource.title });
        setShowFileModal(true);
        setIsFileLoading(true);
        setShareFiles([]);
        setSelectedFileIds(new Set());

        try {
            const response = await api.get115ShareFiles(shareCode, accessCode);
            if (response.success) {
                setShareFiles(response.data || []);
                // Default select all
                const allIds = new Set((response.data || []).map(f => f.id));
                setSelectedFileIds(allIds);
            } else {
                setToast(response.error || '获取文件列表失败');
                setTimeout(() => setToast(null), 3000);
                setShowFileModal(false);
            }
        } catch (e) {
            console.error(e);
            setToast('获取文件列表失败');
            setTimeout(() => setToast(null), 3000);
            setShowFileModal(false);
        } finally {
            setIsFileLoading(false);
        }
    };

    const handleSaveSelectedFiles = async () => {
        if (!sharingResource || selectedFileIds.size === 0) return;

        try {
            const response = await api.save115Share(
                sharingResource.shareCode,
                sharingResource.accessCode,
                undefined, // default cid
                Array.from(selectedFileIds)
            );

            if (response.success) {
                setToast(`成功转存 ${response.data.count} 个文件`);
                setShowFileModal(false);
            } else {
                setToast(response.error || '转存失败');
            }
            setTimeout(() => setToast(null), 3000);
        } catch (e) {
            console.error(e);
            setToast('转存失败');
            setTimeout(() => setToast(null), 3000);
        }
    };

    const toggleFileSelection = (id: string) => {
        const newSet = new Set(selectedFileIds);
        if (newSet.has(id)) {
            newSet.delete(id);
        } else {
            newSet.add(id);
        }
        setSelectedFileIds(newSet);
    };

    const toggleSelectAll = () => {
        if (selectedFileIds.size === shareFiles.length) {
            setSelectedFileIds(new Set());
        } else {
            setSelectedFileIds(new Set(shareFiles.map(f => f.id)));
        }
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

                {/* Tab Switcher */}
                <div className="flex bg-slate-100 dark:bg-slate-800/50 p-1 rounded-xl">
                    <button
                        onClick={() => setActiveTab('search')}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'search'
                            ? 'bg-white dark:bg-slate-700 text-brand-600 dark:text-brand-400 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
                            }`}
                    >
                        资源搜索
                    </button>
                    <button
                        onClick={() => setActiveTab('subscription')}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${activeTab === 'subscription'
                            ? 'bg-white dark:bg-slate-700 text-brand-600 dark:text-brand-400 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200'
                            }`}
                    >
                        <Bell size={14} />
                        订阅管理
                    </button>
                </div>
            </div>

            {activeTab === 'search' ? (
                <>
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
                                        onClick={() => setSelectedResource(resource)}
                                        onPreview={handlePreviewContent}
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

                    {/* Share File Selection Modal */}
                    {showFileModal && (
                        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
                            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowFileModal(false)} />
                            <div className="relative w-full max-w-2xl bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 animate-in zoom-in-95 duration-200 flex flex-col max-h-[80vh]">
                                <div className="flex items-center justify-between mb-4">
                                    <h3 className="text-xl font-bold text-slate-800 dark:text-white flex items-center gap-2">
                                        <FileText className="text-brand-500" />
                                        {sharingResource?.resourceTitle} - 文件列表
                                    </h3>
                                    <button onClick={() => setShowFileModal(false)} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                                        <X size={24} />
                                    </button>
                                </div>

                                <div className="flex-1 overflow-y-auto min-h-[200px] border border-slate-200 dark:border-slate-700 rounded-lg p-2">
                                    {isFileLoading ? (
                                        <div className="flex items-center justify-center h-full">
                                            <Loader2 className="animate-spin text-brand-500" size={32} />
                                        </div>
                                    ) : shareFiles.length === 0 ? (
                                        <div className="flex items-center justify-center h-full text-slate-500">
                                            没有找到文件
                                        </div>
                                    ) : (
                                        <div className="space-y-1">
                                            <div className="flex items-center justify-between p-2 border-b border-slate-100 dark:border-slate-800">
                                                <button
                                                    onClick={toggleSelectAll}
                                                    className="flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-brand-500"
                                                >
                                                    {selectedFileIds.size === shareFiles.length ? <CheckSquare size={18} /> : <Square size={18} />}
                                                    全选 ({selectedFileIds.size}/{shareFiles.length})
                                                </button>
                                            </div>
                                            {shareFiles.map(file => (
                                                <div
                                                    key={file.id}
                                                    onClick={() => toggleFileSelection(file.id)}
                                                    className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-colors ${selectedFileIds.has(file.id)
                                                        ? 'bg-brand-50 dark:bg-brand-900/20 border border-brand-200 dark:border-brand-800'
                                                        : 'hover:bg-slate-50 dark:hover:bg-slate-800/50 border border-transparent'
                                                        }`}
                                                >
                                                    <div className={`text-brand-500 ${selectedFileIds.has(file.id) ? 'opacity-100' : 'opacity-40'}`}>
                                                        {selectedFileIds.has(file.id) ? <CheckSquare size={18} /> : <Square size={18} />}
                                                    </div>
                                                    <div className="flex-1 overflow-hidden">
                                                        <div className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate" title={file.name}>
                                                            {file.name}
                                                        </div>
                                                        <div className="text-xs text-slate-500 flex gap-3 mt-0.5">
                                                            <span>{file.is_directory ? '文件夹' : '文件'}</span>
                                                            {file.size > 0 && <span>{(file.size / 1024 / 1024).toFixed(2)} MB</span>}
                                                            <span>{file.time ? new Date(file.time).toLocaleDateString() : ''}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                <div className="flex justify-end gap-3 mt-6">
                                    <button
                                        onClick={() => setShowFileModal(false)}
                                        className="px-4 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
                                    >
                                        取消
                                    </button>
                                    <button
                                        onClick={handleSaveSelectedFiles}
                                        disabled={selectedFileIds.size === 0}
                                        className="px-6 py-2 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 transition-colors disabled:opacity-50 flex items-center gap-2"
                                    >
                                        <Save size={18} />
                                        转存选中 ({selectedFileIds.size})
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </>
            ) : (
                <SubscriptionManager glassCardClass={glassCardClass} inputClass={inputClass} />
            )}
        </div>
    );
};

// Subscription Manager Component
const SubscriptionManager: React.FC<{ glassCardClass: string; inputClass: string }> = ({ glassCardClass, inputClass }) => {
    const [subscriptions, setSubscriptions] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isAdding, setIsAdding] = useState(false);
    const [isRunning, setIsRunning] = useState(false);
    const [newSub, setNewSub] = useState({ keyword: '', cloud_type: '115', include: '', exclude: '' });
    const [showAddModal, setShowAddModal] = useState(false);
    const [toast, setToast] = useState<string | null>(null);
    const [editingSub, setEditingSub] = useState<any | null>(null);

    useEffect(() => {
        fetchSubscriptions();
    }, []);

    const fetchSubscriptions = async () => {
        setIsLoading(true);
        try {
            const data = await api.getSubscriptions();
            setSubscriptions(data || []);
        } catch (e) {
            console.error(e);
            showToast('获取订阅列表失败');
        } finally {
            setIsLoading(false);
        }
    };

    const handleAdd = async () => {
        if (!newSub.keyword.trim()) return;
        setIsAdding(true);
        try {
            const filter_config = {
                include: newSub.include.split(/[,，]/).map(s => s.trim()).filter(Boolean),
                exclude: newSub.exclude.split(/[,，]/).map(s => s.trim()).filter(Boolean)
            };

            await api.addSubscription({
                keyword: newSub.keyword,
                cloud_type: newSub.cloud_type,
                filter_config
            });

            setShowAddModal(false);
            setNewSub({ keyword: '', cloud_type: '115', include: '', exclude: '' });
            showToast('添加订阅成功');
            fetchSubscriptions();
        } catch (e) {
            console.error(e);
            showToast('添加订阅失败');
        } finally {
            setIsAdding(false);
        }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('确定要删除这个订阅吗？')) return;
        try {
            await api.deleteSubscription(id);
            setSubscriptions(prev => prev.filter(s => s.id !== id));
            showToast('订阅已删除');
        } catch (e) {
            console.error(e);
            showToast('删除失败');
        }
    };

    const handleRunNow = async () => {
        setIsRunning(true);
        showToast('正在后台运行订阅检查...');
        try {
            await api.runSubscriptionChecks();
            showToast('检查任务已触发，请稍后刷新查看结果');
            setTimeout(fetchSubscriptions, 2000); // Wait a bit then refresh
        } catch (e) {
            console.error(e);
            showToast('触发检查失败');
        } finally {
            setIsRunning(false);
        }
    };





    const showToast = (msg: string) => {
        setToast(msg);
        setTimeout(() => setToast(null), 3000);
    };

    return (
        <div className="space-y-6">
            {toast && (
                <div className="fixed top-6 right-6 bg-slate-800/90 backdrop-blur-md text-white px-6 py-3 rounded-xl shadow-2xl z-50 flex items-center gap-3 font-medium border-[0.5px] border-slate-700/50 animate-in slide-in-from-top-2">
                    <CheckCircle2 size={18} className="text-green-400" />
                    {toast}
                </div>
            )}

            <div className="flex justify-between items-center">
                <div>
                    <h3 className="text-lg font-bold text-slate-700 dark:text-slate-200">我的订阅</h3>
                    <p className="text-sm text-slate-500">自动搜索并下载符合条件的资源</p>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={handleRunNow}
                        disabled={isRunning}
                        className="px-4 py-2 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 rounded-lg text-sm font-medium hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-2"
                    >
                        <RefreshCw size={14} className={isRunning ? 'animate-spin' : ''} />
                        立即检查
                    </button>
                    <button
                        onClick={() => setShowAddModal(true)}
                        className="px-4 py-2 bg-brand-600 text-white rounded-lg text-sm font-medium hover:bg-brand-700 transition-colors flex items-center gap-2 shadow-lg shadow-brand-500/20"
                    >
                        <Plus size={16} />
                        新建订阅
                    </button>
                </div>
            </div>

            {isLoading ? (
                <div className="flex justify-center py-20">
                    <Loader2 className="animate-spin text-brand-500" size={32} />
                </div>
            ) : subscriptions.length === 0 ? (
                <div className={`${glassCardClass} p-10 flex flex-col items-center justify-center text-slate-400`}>
                    <Bell size={48} className="mb-4 opacity-50" />
                    <p>暂无订阅，点击右上角添加</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {subscriptions.map(sub => (
                        <div key={sub.id} className={`${glassCardClass} p-5 group flex flex-col h-full bg-white/40 dark:bg-slate-900/40`}>
                            <div className="flex justify-between items-start mb-3">
                                <div className="flex items-center gap-2">
                                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold text-white font-mono ${sub.cloud_type === '115' ? 'bg-orange-500' : 'bg-blue-500'}`}>
                                        {sub.cloud_type}
                                    </span>
                                    <h4 className="font-bold text-slate-800 dark:text-white text-lg">{sub.keyword}</h4>
                                </div>
                                <button
                                    onClick={() => handleDelete(sub.id)}
                                    className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>

                            <div className="space-y-2 mb-4 flex-1">
                                <div className="flex flex-wrap gap-2 text-xs">
                                    {(sub.filter_config?.include || []).map((tag: string, i: number) => (
                                        <span key={`inc-${i}`} className="px-1.5 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded border border-green-200 dark:border-green-800/50">
                                            +{tag}
                                        </span>
                                    ))}
                                    {(sub.filter_config?.exclude || []).map((tag: string, i: number) => (
                                        <span key={`exc-${i}`} className="px-1.5 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded border border-red-200 dark:border-red-800/50">
                                            -{tag}
                                        </span>
                                    ))}
                                    {(!sub.filter_config?.include?.length && !sub.filter_config?.exclude?.length) && (
                                        <span className="text-slate-400 italic">无过滤规则</span>
                                    )}
                                </div>

                                <div className="flex items-center gap-2 mt-3 pt-2 border-t border-slate-100 dark:border-slate-800/50">
                                    <span className="text-xs text-slate-500">当前进度:</span>
                                    <button
                                        onClick={() => setEditingSub(sub)}
                                        className="text-xs font-mono font-bold text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-900/20 px-2 py-0.5 rounded border border-brand-200 dark:border-brand-800/50 hover:bg-brand-100 dark:hover:bg-brand-900/40 transition-colors flex items-center gap-1"
                                        title="点击修改进度"
                                    >
                                        <span className="opacity-50">S</span>{(sub.current_season || 0).toString().padStart(2, '0')}
                                        <span className="opacity-50 ml-1">E</span>{(sub.current_episode || 0).toString().padStart(2, '0')}
                                    </button>
                                </div>
                            </div>

                            <div className="pt-3 border-t border-slate-200/50 dark:border-slate-700/50 text-xs text-slate-500 flex justify-between items-center">
                                <span>上次检查: {sub.last_check ? new Date(sub.last_check).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '从未'}</span>
                            </div>
                            {sub.last_message && (
                                <div className="mt-2 text-xs text-slate-500 truncate" title={sub.last_message}>
                                    {sub.last_message}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* Add Modal */}
            {showAddModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowAddModal(false)} />
                    <div className="relative w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 animate-in zoom-in-95 duration-200">
                        <h3 className="text-xl font-bold mb-4 text-slate-800 dark:text-white">新建订阅</h3>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                                    搜索关键词 <span className="text-red-500">*</span>
                                </label>
                                <input
                                    type="text"
                                    value={newSub.keyword}
                                    onChange={e => setNewSub({ ...newSub, keyword: e.target.value })}
                                    className={inputClass}
                                    placeholder="例如：盗梦空间 4K"
                                    autoFocus
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                                    目标网盘
                                </label>
                                <select
                                    value={newSub.cloud_type}
                                    onChange={e => setNewSub({ ...newSub, cloud_type: e.target.value })}
                                    className={inputClass}
                                >
                                    <option value="115">115 网盘</option>
                                    <option value="123">123 云盘</option>
                                </select>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                                    包含规则 (逗号分隔)
                                </label>
                                <input
                                    type="text"
                                    value={newSub.include}
                                    onChange={e => setNewSub({ ...newSub, include: e.target.value })}
                                    className={inputClass}
                                    placeholder="例如：HDR, 60FPS"
                                />
                                <p className="text-xs text-slate-500 mt-1">必须包含所有规则才会被选中</p>
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">
                                    排除规则 (逗号分隔)
                                </label>
                                <input
                                    type="text"
                                    value={newSub.exclude}
                                    onChange={e => setNewSub({ ...newSub, exclude: e.target.value })}
                                    className={inputClass}
                                    placeholder="例如：CAM, TC"
                                />
                                <p className="text-xs text-slate-500 mt-1">包含任一规则将被排除</p>
                            </div>
                        </div>
                        <div className="flex justify-end gap-3 mt-6">
                            <button
                                onClick={() => setShowAddModal(false)}
                                className="px-4 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
                            >
                                取消
                            </button>
                            <button
                                onClick={handleAdd}
                                disabled={isAdding || !newSub.keyword.trim()}
                                className="px-6 py-2 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 transition-colors disabled:opacity-50"
                            >
                                {isAdding ? '添加中...' : '确定添加'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Edit Progress Modal */}
            {editingSub && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setEditingSub(null)} />
                    <div className="relative w-full max-w-sm bg-white dark:bg-slate-900 rounded-2xl shadow-2xl p-6 animate-in zoom-in-95 duration-200">
                        <h3 className="text-xl font-bold mb-4 text-slate-800 dark:text-white">修改进度: {editingSub.keyword}</h3>
                        <form onSubmit={async (e) => {
                            e.preventDefault();
                            const formData = new FormData(e.currentTarget);
                            const season = parseInt(formData.get('season') as string);
                            const episode = parseInt(formData.get('episode') as string);

                            try {
                                await api.updateSubscription(editingSub.id, { current_season: season, current_episode: episode });
                                setSubscriptions(prev => prev.map(s => s.id === editingSub.id ? { ...s, current_season: season, current_episode: episode } : s));
                                setEditingSub(null);
                                showToast('进度已更新');
                            } catch (err) {
                                console.error(err);
                                showToast('更新失败');
                            }
                        }}>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">当前季 (Season)</label>
                                    <input name="season" type="number" defaultValue={editingSub.current_season || 0} min="0" className={inputClass} />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">当前集 (Episode)</label>
                                    <input name="episode" type="number" defaultValue={editingSub.current_episode || 0} min="0" className={inputClass} />
                                </div>
                                <div className="flex justify-end gap-3 mt-6">
                                    <button type="button" onClick={() => setEditingSub(null)} className="px-4 py-2 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors">取消</button>
                                    <button type="submit" className="px-6 py-2 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 transition-colors">保存</button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

// Resource Card Component
const ResourceCard: React.FC<{
    resource: Resource;
    onClick: () => void;
    onPreview?: (resource: Resource) => void;
}> = ({ resource, onClick, onPreview }) => {
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
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col justify-end p-3 gap-2">

                    {/* Direct Save Button */}
                    {(resource.share_link || (resource.share_links && resource.share_links[0]?.link)) && (
                        <div className="flex gap-2 w-full">
                            {/* 115 Preview Button */}
                            {resource.cloud_type === '115' && onPreview && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onPreview(resource);
                                    }}
                                    className="flex-1 py-2 backdrop-blur-sm rounded-lg text-white text-xs font-bold flex items-center justify-center gap-1 transition-colors shadow-lg bg-orange-500/90 hover:bg-orange-600"
                                >
                                    <FileText size={14} />
                                    预览
                                </button>
                            )}

                            <a
                                href={resource.share_link || resource.share_links?.[0]?.link || '#'}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className={`py-2 backdrop-blur-sm rounded-lg text-white text-xs font-bold flex items-center justify-center gap-1 transition-colors shadow-lg ${resource.cloud_type === '115' ? 'bg-orange-500/90 hover:bg-orange-600 flex-1' : 'bg-brand-500/90 hover:bg-brand-600 w-full'}`}
                            >
                                <ExternalLink size={14} />
                                {resource.cloud_type === '115' ? '直存' : '转存'}
                            </a>
                        </div>
                    )}

                    <button className="w-full py-2 bg-white/20 backdrop-blur-sm rounded-lg text-white text-xs font-medium flex items-center justify-center gap-1 hover:bg-white/30 transition-colors">
                        <Info size={14} />
                        查看详情
                    </button>
                </div>

                {/* Quality Badge */}
                <div className="absolute top-2 left-2 px-2 py-0.5 bg-black/60 backdrop-blur-sm rounded text-[10px] font-bold text-white">
                    {resource.quality}
                </div>

                {/* Type Badge */}
                <div className={`absolute top-2 right-2 p-1.5 rounded-full ${resource.type === 'movie' ? 'bg-purple-500' : 'bg-blue-500'} text-white`}>
                    {resource.type === 'movie' ? <Film size={12} /> : <Tv size={12} />}
                </div>

                {resource.rating && (
                    <div className="absolute bottom-2 left-2 flex items-center gap-1 px-2 py-0.5 bg-black/60 backdrop-blur-sm rounded text-[10px] font-bold text-amber-400">
                        <Star size={10} fill="currentColor" />
                        {resource.rating.toFixed(1)}
                    </div>
                )}

                {/* Cloud Source Badge */}
                {resource.cloud_type && (
                    <div className={`absolute bottom-2 right-2 px-1.5 py-0.5 rounded text-[10px] font-bold text-white shadow-sm font-mono tracking-tighter ${resource.cloud_type === '115' ? 'bg-orange-500/90' : resource.cloud_type === '123' ? 'bg-blue-500/90' : 'bg-slate-500/90'}`}>
                        {resource.cloud_type === '115' ? '115' : resource.cloud_type === '123' ? '123' : resource.cloud_type}
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
