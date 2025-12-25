/**
 * Cloud115Login.tsx - 115 网盘登录组件
 * 
 * 支持三种登录方式：
 * 1. Cookie 导入 - 手动粘贴 Cookie 字符串
 * 2. 扫码登录 - 选择终端类型，生成标准二维码
 * 3. 第三方 App ID - 输入 App ID，生成 PKCE 二维码
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../services/api';
import {
    Cookie,
    QrCode,
    Smartphone,
    RefreshCw,
    Save,
    Check,
    Copy,
    Download,
    Loader2,
    Eye,
    EyeOff,
    CheckCircle2
} from 'lucide-react';

// ==================== 类型定义 ====================

type LoginMethod = 'cookie' | 'qrcode' | 'open_app';
type QrState = 'idle' | 'loading' | 'waiting' | 'scanned' | 'success' | 'expired' | 'error';

interface LoginApp {
    key: string;
    ssoent: string;
    name: string;
}

interface Cloud115LoginProps {
    /** 登录成功回调 */
    onLoginSuccess?: () => void;
    /** 显示 Toast 消息 */
    onToast?: (message: string) => void;
    /** 当前选择的终端类型 */
    selectedApp?: string;
    /** 终端类型变化回调 */
    onAppChange?: (app: string) => void;
    /** 当前 App ID */
    appId?: string;
    /** App ID 变化回调 */
    onAppIdChange?: (id: string) => void;
    /** 当前 Cookie */
    cookies?: string;
    /** Cookie 变化回调 */
    onCookiesChange?: (cookies: string) => void;
    /** 外部控制的 loginMethod */
    loginMethod?: LoginMethod;
    /** loginMethod 变化回调 */
    onLoginMethodChange?: (method: LoginMethod) => void;
    /** 是否已连接 */
    isConnected?: boolean;
}

// ==================== 样式常量 ====================

const inputClass = "w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-brand-500 outline-none transition-all font-mono text-sm backdrop-blur-sm shadow-inner";
const btnPrimaryClass = "px-5 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-lg hover:bg-brand-700 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed";
const btnSecondaryClass = "px-3 py-1.5 bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 rounded-lg text-xs font-medium flex items-center gap-1 hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors";

// ==================== 主组件 ====================

export const Cloud115Login: React.FC<Cloud115LoginProps> = ({
    onLoginSuccess,
    onToast,
    selectedApp = 'android',
    onAppChange,
    appId = '',
    onAppIdChange,
    cookies = '',
    onCookiesChange,
    loginMethod: externalLoginMethod,
    onLoginMethodChange,
    isConnected = false
}) => {
    // ========== 状态管理 ==========
    const [internalLoginMethod, setInternalLoginMethod] = useState<LoginMethod>('qrcode');
    const loginMethod = externalLoginMethod ?? internalLoginMethod;
    // Local connected state (to handle UI updates before parent refresh)
    const [localConnected, setLocalConnected] = useState(isConnected);

    const [loginApps, setLoginApps] = useState<LoginApp[]>([]);
    const [qrState, setQrState] = useState<QrState>('idle');
    const [qrImage, setQrImage] = useState<string>('');
    const [isSaving, setIsSaving] = useState(false);
    const [showCookies, setShowCookies] = useState(false);

    // 长轮询控制标志
    const isPollingRef = useRef<boolean>(false);

    // Sync local connected state with prop
    useEffect(() => {
        setLocalConnected(isConnected);
    }, [isConnected]);

    // ========== 登录方式切换 ==========
    const handleMethodChange = (method: LoginMethod) => {
        if (onLoginMethodChange) {
            onLoginMethodChange(method);
        } else {
            setInternalLoginMethod(method);
        }
        // 切换时重置二维码状态
        stopPolling();
        setQrState('idle');
        setQrImage('');
    };

    // ========== 获取登录终端列表 ==========
    useEffect(() => {
        const fetchApps = async () => {
            try {
                const apps = await api.get115LoginApps();
                if (apps && apps.length > 0) {
                    setLoginApps(apps);
                }
            } catch {
                // 使用默认列表
                setLoginApps([
                    { key: 'android', ssoent: 'F1', name: '安卓' },
                    { key: 'ios', ssoent: 'D1', name: '115生活iPhone版' },
                    { key: 'qios', ssoent: 'D2', name: '115管理iPhone版' },
                    { key: 'ipad', ssoent: 'H1', name: '115生活iPad版' },
                    { key: 'qipad', ssoent: 'H2', name: '115管理iPad版' },
                    { key: 'apple_tv', ssoent: 'J1', name: '115TV苹果版' },
                    { key: 'tv', ssoent: 'I1', name: '电视端' },
                    { key: 'harmony', ssoent: 'S1', name: '鸿蒙' },
                    { key: 'qandroid', ssoent: 'M1', name: '轻量版安卓' },
                ]);
            }
        };
        fetchApps();

        return () => stopPolling();
    }, []);

    // ========== 轮询控制 ==========
    const stopPolling = useCallback(() => {
        isPollingRef.current = false;
    }, []);

    // ========== 长轮询状态检查 ==========
    const pollStatus = useCallback(async (sessionId: string) => {
        if (!isPollingRef.current) return;

        try {
            const statusRes = await api.check115QrStatus(sessionId, 0, '');
            // 后端返回格式: { success: true, data: { status: 'xxx', message: '...' } }
            // 或错误格式: { success: false, status: 'expired', error: '...' }
            const status = statusRes.data?.data?.status || statusRes.data?.status || (statusRes as any).status || 'waiting';
            console.log('[115 QR Poll] statusRes:', statusRes, 'parsed status:', status);

            if (!isPollingRef.current) return; // 检查是否已取消

            switch (status) {
                case 'scanned':
                    setQrState('scanned');
                    // 继续长轮询
                    pollStatus(sessionId);
                    break;
                case 'success':
                    stopPolling();
                    setQrState('success');
                    onToast?.('登录成功，Cookie 已自动保存');
                    setLocalConnected(true);
                    onLoginSuccess?.();
                    break;
                case 'expired':
                    // Keep polling even if expired - user can manually refresh
                    console.log('QR expired, continuing to poll...');
                    setTimeout(() => {
                        if (isPollingRef.current) {
                            pollStatus(sessionId);
                        }
                    }, 3000);
                    break;
                case 'error':
                    // Keep polling on error too
                    console.warn('QR status error, retrying...');
                    setTimeout(() => {
                        if (isPollingRef.current) {
                            pollStatus(sessionId);
                        }
                    }, 3000);
                    break;
                default:
                    // 'waiting' - 继续长轮询
                    pollStatus(sessionId);
            }
        } catch (err) {
            console.error('QR poll error:', err);
            if (isPollingRef.current) {
                // 网络错误时延迟重试
                setTimeout(() => pollStatus(sessionId), 3000);
            }
        }
    }, [onToast, onLoginSuccess, stopPolling]);

    // ========== 生成二维码 ==========
    const generateQrCode = async () => {
        // 验证：open_app 模式必须有 AppID
        if (loginMethod === 'open_app' && !appId) {
            onToast?.('请先填写第三方 App ID');
            return;
        }

        stopPolling();
        setQrState('loading');
        setQrImage('');

        try {
            const targetApp = loginMethod === 'open_app' ? 'open_app' : selectedApp;
            const targetAppId = loginMethod === 'open_app' ? appId : undefined;

            const data = await api.get115QrCode(targetApp, loginMethod, targetAppId);

            setQrImage(data.qrcode);
            setQrState('waiting');

            // 开始长轮询
            isPollingRef.current = true;
            pollStatus(data.sessionId);

        } catch (e: any) {
            console.error('QR generation failed:', e);
            setQrState('error');

            if (e.code === 'ERR_NETWORK') {
                onToast?.('无法连接后端服务器');
            } else if (e.response?.status === 401) {
                onToast?.('登录已过期，请重新登录');
            } else {
                onToast?.(`二维码生成失败: ${e.response?.data?.error || e.message} `);
            }
        }
    };

    // ========== Cookie 导入 ==========
    const handleCookieImport = async () => {
        if (!cookies.trim()) {
            onToast?.('请输入 Cookie');
            return;
        }

        setIsSaving(true);
        try {
            // 调用后端保存 Cookie
            const response = await fetch('/api/115/login/cookie', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')} `,
                },
                body: JSON.stringify({ cookies }),
            });

            const result = await response.json();

            if (result.success) {
                onToast?.('Cookie 导入成功');
                setLocalConnected(true);
                onLoginSuccess?.();
            } else {
                onToast?.(result.error || 'Cookie 导入失败');
            }
        } catch (e: any) {
            onToast?.(`导入失败: ${e.message} `);
        } finally {
            setIsSaving(false);
        }
    };

    // ========== 复制二维码链接 ==========
    const copyQrLink = () => {
        if (qrImage) {
            navigator.clipboard.writeText(qrImage);
            onToast?.('二维码链接已复制');
        }
    };

    // ========== 渲染登录方式 Tabs ==========
    const renderTabs = () => (
        <div className="flex flex-wrap gap-2 mb-6 p-1 bg-slate-100 dark:bg-slate-800 rounded-lg">
            {[
                { id: 'qrcode' as LoginMethod, label: '扫码登录', icon: QrCode },
                { id: 'cookie' as LoginMethod, label: 'Cookie', icon: Cookie },
                { id: 'open_app' as LoginMethod, label: '三方App', icon: Smartphone },
            ].map((tab) => (
                <button
                    key={tab.id}
                    onClick={() => handleMethodChange(tab.id)}
                    className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm font-bold transition-all ${loginMethod === tab.id
                        ? 'bg-white dark:bg-slate-700 text-brand-600 dark:text-brand-400 shadow-sm'
                        : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'
                        }`}
                >
                    <tab.icon size={16} />
                    {tab.label}
                </button>
            ))}
        </div>
    );

    // ========== 渲染 Cookie 导入 ==========
    const renderCookieImport = () => (
        <div className="space-y-4 animate-in fade-in duration-300">
            <div>
                <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-medium text-slate-600 dark:text-slate-400">
                        Cookie 字符串
                    </label>
                    <button
                        type="button"
                        onClick={() => setShowCookies(!showCookies)}
                        className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                        title={showCookies ? '隐藏内容' : '显示内容'}
                    >
                        {showCookies ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                </div>
                <div className="relative">
                    <textarea
                        value={cookies}
                        onChange={(e) => onCookiesChange?.(e.target.value)}
                        placeholder="UID=...; CID=...; SEID=..."
                        rows={4}
                        className={`${inputClass} resize-none ${!showCookies ? 'text-security-disc' : ''}`}
                        style={!showCookies ? {
                            WebkitTextSecurity: 'disc',
                            fontFamily: 'text-security-disc, monospace'
                        } as React.CSSProperties : undefined}
                    />
                </div>
                <p className="text-xs text-slate-400 mt-2">
                    💡 从浏览器开发者工具复制 Cookie，格式如：UID=xxx; CID=xxx; SEID=xxx
                </p>
            </div>

            <button
                onClick={handleCookieImport}
                disabled={isSaving || !cookies.trim()}
                className={btnPrimaryClass}
            >
                {isSaving ? <Loader2 className="animate-spin" size={16} /> : <Save size={16} />}
                验证并保存
            </button>
        </div>
    );

    // ========== 渲染扫码登录 ==========
    const renderQrCodeLogin = () => (
        <div className="space-y-6 animate-in fade-in duration-300">
            {/* 终端选择 */}
            <div className="max-w-xs mx-auto">
                <label className="flex items-center justify-center gap-2 text-xs font-bold text-slate-500 uppercase mb-2">
                    <Smartphone size={12} />
                    选择模拟终端
                </label>
                <select
                    value={selectedApp}
                    onChange={(e) => onAppChange?.(e.target.value)}
                    className={`${inputClass} text-center cursor-pointer`}
                >
                    {loginApps.map((app) => (
                        <option key={app.key} value={app.key}>
                            {app.name}
                        </option>
                    ))}
                </select>
            </div>

            {/* 二维码区域 */}
            {renderQrCodeArea()}
        </div>
    );

    // ========== 渲染第三方 App 登录 ==========
    const renderOpenAppLogin = () => (
        <div className="space-y-6 animate-in fade-in duration-300">
            {/* App ID 输入 */}
            <div>
                <label className="block text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">
                    第三方 App ID
                </label>
                <input
                    type="text"
                    value={appId}
                    onChange={(e) => onAppIdChange?.(e.target.value)}
                    placeholder="请输入 App ID，如 100197531"
                    className={inputClass}
                />
                <p className="text-xs text-slate-400 mt-2">
                    💡 使用 115 开放平台申请的第三方应用 ID
                </p>
            </div>

            {/* 二维码区域 */}
            {renderQrCodeArea()}
        </div>
    );

    // ========== 渲染二维码区域（共用） ==========
    const renderQrCodeArea = () => (
        <div className="flex flex-col items-center py-4">
            {qrState === 'idle' && (
                <button onClick={generateQrCode} className={btnPrimaryClass}>
                    <QrCode size={18} />
                    点击生成二维码
                </button>
            )}

            {qrState === 'loading' && (
                <div className="w-48 h-48 flex items-center justify-center bg-slate-50 dark:bg-slate-800 rounded-xl">
                    <Loader2 className="animate-spin text-brand-500" size={32} />
                </div>
            )}

            {qrImage && qrState !== 'loading' && (
                <div className="text-center w-full">
                    {/* 二维码图片 */}
                    <div className="relative inline-block mb-4">
                        <img
                            src={qrImage}
                            alt="115 登录二维码"
                            className={`w-48 h-48 rounded-xl border-4 border-white shadow-xl transition-all ${qrState === 'expired' ? 'opacity-20 grayscale' : ''
                                } ${qrState === 'success' ? 'ring-4 ring-green-400 ring-offset-2' : ''} `}
                        />

                        {/* 状态覆盖层 */}
                        {qrState === 'success' && (
                            <div className="absolute inset-0 flex items-center justify-center bg-green-500/80 rounded-xl animate-in fade-in zoom-in">
                                <Check size={64} className="text-white" />
                            </div>
                        )}

                        {qrState === 'scanned' && (
                            <div className="absolute -top-2 -right-2 bg-amber-500 text-white px-3 py-1 rounded-full text-xs font-bold animate-pulse shadow-lg">
                                已扫描
                            </div>
                        )}

                        {(qrState === 'expired' || qrState === 'error') && (
                            <div
                                className="absolute inset-0 flex items-center justify-center cursor-pointer"
                                onClick={generateQrCode}
                            >
                                <div className="bg-slate-800/90 text-white px-4 py-2 rounded-full text-sm font-bold flex items-center gap-2 hover:scale-105 transition-transform">
                                    <RefreshCw size={14} />
                                    点击刷新
                                </div>
                            </div>
                        )}
                    </div>

                    {/* 状态文字 */}
                    <p className="text-sm text-slate-600 dark:text-slate-300 font-medium mb-1">
                        请使用 115 App 扫码登录
                    </p>
                    <p className={`text-xs font-bold ${qrState === 'success' ? 'text-green-500' :
                        qrState === 'scanned' ? 'text-amber-500' :
                            qrState === 'expired' ? 'text-red-400' :
                                qrState === 'error' ? 'text-red-400' :
                                    'text-slate-400'
                        } `}>
                        {qrState === 'waiting' && '等待扫描...'}
                        {qrState === 'scanned' && '✓ 已扫描，请在手机上确认'}
                        {qrState === 'success' && '✓ 登录成功！'}
                        {qrState === 'expired' && '二维码已过期'}
                        {qrState === 'error' && '获取失败，请重试'}
                    </p>

                    {/* 操作按钮 */}
                    {qrState !== 'success' && qrImage && (
                        <div className="flex gap-2 justify-center mt-4">
                            <button onClick={generateQrCode} className={btnSecondaryClass}>
                                <RefreshCw size={14} />
                                刷新
                            </button>
                            <a
                                href={qrImage}
                                download={`115_qrcode_${Date.now()}.png`}
                                className={btnSecondaryClass}
                            >
                                <Download size={14} />
                                保存
                            </a>
                        </div>
                    )}
                </div>
            )}
        </div>
    );

    // ========== 主渲染 ==========

    // 如果已连接并显示 Connected UI
    if (localConnected) {
        return (
            <div className="bg-green-50 dark:bg-green-900/20 rounded-xl p-8 border border-green-200 dark:border-green-800 text-center space-y-4 animate-in fade-in zoom-in duration-300">
                <div className="w-16 h-16 bg-green-100 dark:bg-green-900/40 rounded-full flex items-center justify-center mx-auto text-green-600 dark:text-green-400 shadow-inner">
                    <CheckCircle2 size={32} />
                </div>
                <div>
                    <h4 className="font-bold text-lg text-green-700 dark:text-green-300">已成功连接</h4>
                    <p className="text-sm text-green-600/80 dark:text-green-400/80 mt-1">115 网盘服务运行正常</p>
                </div>
                <button
                    onClick={() => {
                        setLocalConnected(false);
                        stopPolling();
                        setQrState('idle');
                        setQrImage('');
                    }}
                    className="px-6 py-2 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 rounded-lg text-sm font-bold shadow-sm border border-slate-200 dark:border-slate-700 hover:text-red-600 hover:border-red-200 transition-colors mt-2"
                >
                    切换账号 / 重新登录
                </button>
            </div>
        );
    }

    return (
        <div className="w-full">
            {renderTabs()}

            <div className="min-h-[300px] flex flex-col">
                {loginMethod === 'cookie' && renderCookieImport()}
                {loginMethod === 'qrcode' && renderQrCodeLogin()}
                {loginMethod === 'open_app' && renderOpenAppLogin()}
            </div>
        </div>
    );
};

export default Cloud115Login;
