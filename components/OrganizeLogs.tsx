import React, { useEffect, useState, useRef } from 'react';
import { api } from '../services/api';
import { RefreshCw, Trash2, CheckCircle2, XCircle, Clock, FileText, X } from 'lucide-react';

interface OrganizeLogEntry {
    source_dir: string;
    original_name: string;
    new_name: string;
    target_path: string;
    status: 'success' | 'failed';
    error?: string;
    cloud_type: string;
    timestamp: string;
    formatted: string;
}

interface OrganizeLogsProps {
    isOpen: boolean;
    onClose: () => void;
}

export const OrganizeLogs: React.FC<OrganizeLogsProps> = ({ isOpen, onClose }) => {
    const [logs, setLogs] = useState<OrganizeLogEntry[]>([]);
    const [stats, setStats] = useState<{ total: number; success: number; failed: number } | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const logsContainerRef = useRef<HTMLDivElement>(null);

    const fetchLogs = async () => {
        setIsLoading(true);
        try {
            const response = await api.getOrganizeLogs(100);
            if (response.success) {
                setLogs(response.data || []);
                setStats(response.stats || null);
            }
        } catch (e) {
            console.error('获取整理日志失败', e);
        } finally {
            setIsLoading(false);
        }
    };

    const clearLogs = async () => {
        try {
            await api.clearOrganizeLogs();
            setLogs([]);
            setStats({ total: 0, success: 0, failed: 0 });
        } catch (e) {
            console.error('清空日志失败', e);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchLogs();
            // 自动刷新（每5秒）
            const interval = setInterval(fetchLogs, 5000);
            return () => clearInterval(interval);
        }
    }, [isOpen]);

    // 自动滚动到底部
    useEffect(() => {
        if (logsContainerRef.current) {
            logsContainerRef.current.scrollTop = 0;
        }
    }, [logs]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[80] flex items-center justify-center p-4 bg-slate-900/80 backdrop-blur-md animate-in fade-in duration-200">
            <div className="relative w-full max-w-4xl h-[80vh] bg-slate-900 rounded-2xl shadow-2xl border border-slate-700 overflow-hidden flex flex-col animate-in zoom-in-95 duration-300">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700 bg-gradient-to-r from-indigo-900/50 to-purple-900/50">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-indigo-500/20 rounded-lg">
                            <FileText size={20} className="text-indigo-400" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-white">整理进程日志</h2>
                            <p className="text-xs text-slate-400">实时查看文件整理状态</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        {/* Stats */}
                        {stats && (
                            <div className="flex items-center gap-4 px-4 py-2 bg-slate-800/50 rounded-lg text-xs">
                                <span className="text-slate-400">
                                    最近1小时:
                                </span>
                                <span className="flex items-center gap-1 text-green-400">
                                    <CheckCircle2 size={12} />
                                    {stats.success}
                                </span>
                                <span className="flex items-center gap-1 text-red-400">
                                    <XCircle size={12} />
                                    {stats.failed}
                                </span>
                            </div>
                        )}

                        <button
                            onClick={fetchLogs}
                            disabled={isLoading}
                            className="p-2 hover:bg-slate-700 rounded-lg transition-colors text-slate-400 hover:text-white"
                            title="刷新"
                        >
                            <RefreshCw size={18} className={isLoading ? 'animate-spin' : ''} />
                        </button>

                        <button
                            onClick={clearLogs}
                            className="p-2 hover:bg-red-900/50 rounded-lg transition-colors text-slate-400 hover:text-red-400"
                            title="清空日志"
                        >
                            <Trash2 size={18} />
                        </button>

                        <button
                            onClick={onClose}
                            className="p-2 hover:bg-slate-700 rounded-lg transition-colors text-slate-400 hover:text-white"
                        >
                            <X size={20} />
                        </button>
                    </div>
                </div>

                {/* Logs Content */}
                <div
                    ref={logsContainerRef}
                    className="flex-1 overflow-auto p-4 bg-slate-950 font-mono text-sm custom-scrollbar"
                >
                    {logs.length === 0 ? (
                        <div className="h-full flex flex-col items-center justify-center text-slate-500">
                            <FileText size={48} className="mb-3 opacity-30" />
                            <span>暂无整理日志</span>
                            <span className="text-xs mt-1 opacity-50">整理任务执行后将在此显示</span>
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {logs.map((log, index) => (
                                <div
                                    key={index}
                                    className={`px-3 py-2 rounded-lg border-l-2 transition-colors ${log.status === 'success'
                                            ? 'bg-green-950/30 border-green-500 hover:bg-green-950/50'
                                            : 'bg-red-950/30 border-red-500 hover:bg-red-950/50'
                                        }`}
                                >
                                    {/* 时间戳 */}
                                    <div className="flex items-center justify-between mb-1">
                                        <div className="flex items-center gap-2 text-xs">
                                            <Clock size={10} className="text-slate-500" />
                                            <span className="text-slate-500">
                                                {new Date(log.timestamp).toLocaleString('zh-CN', {
                                                    month: '2-digit',
                                                    day: '2-digit',
                                                    hour: '2-digit',
                                                    minute: '2-digit',
                                                    second: '2-digit'
                                                })}
                                            </span>
                                            <span className="px-1.5 py-0.5 rounded bg-slate-700 text-slate-300 text-[10px]">
                                                {log.cloud_type}
                                            </span>
                                        </div>
                                        {log.status === 'success' ? (
                                            <span className="text-xs text-green-400 flex items-center gap-1">
                                                <CheckCircle2 size={12} /> 成功
                                            </span>
                                        ) : (
                                            <span className="text-xs text-red-400 flex items-center gap-1">
                                                <XCircle size={12} /> 失败
                                            </span>
                                        )}
                                    </div>

                                    {/* 格式化的日志内容 */}
                                    <div className="text-slate-300 text-xs leading-relaxed break-all">
                                        <span className="text-slate-500">{log.source_dir}/</span>
                                        <span className="text-yellow-400">{log.original_name}</span>
                                        <span className="text-slate-500 mx-2">》</span>
                                        <span className="text-cyan-400">{log.new_name}</span>
                                        <span className="text-slate-500 mx-2">》</span>
                                        <span className="text-green-400">{log.target_path}</span>
                                    </div>

                                    {/* 错误信息 */}
                                    {log.error && (
                                        <div className="mt-1 text-red-400 text-xs">
                                            ⚠️ {log.error}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
