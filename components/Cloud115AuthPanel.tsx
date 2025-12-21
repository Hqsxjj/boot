
import React, { useState, useEffect, useRef } from 'react';
import { AppConfig } from '../types';
import { api } from '../services/api';
import { Save, RefreshCw, Cookie, QrCode, Smartphone, RotateCcw, Check, SaveAll } from 'lucide-react';
import { SensitiveInput } from './SensitiveInput';

interface Cloud115AuthPanelProps {
    config: AppConfig;
    onUpdateConfig: (section: keyof AppConfig, key: string, value: any) => void;
    onSave: () => Promise<void>;
    isSaving: boolean;
    loginApps: Array<{ key: string; name: string }>;
}

export const Cloud115AuthPanel: React.FC<Cloud115AuthPanelProps> = ({
    config,
    onUpdateConfig,
    onSave,
    isSaving,
    loginApps
}) => {
    const [qrState, setQrState] = useState<'idle' | 'loading' | 'waiting' | 'scanned' | 'success' | 'expired' | 'error'>('idle');
    const [qrImage, setQrImage] = useState<string>('');
    const [qrSessionId, setQrSessionId] = useState<string>('');
    const qrTimerRef = useRef<any>(null);
    const [toast, setToast] = useState<string | null>(null);

    useEffect(() => {
        return () => stopQrCheck();
    }, []);

    const stopQrCheck = () => {
        if (qrTimerRef.current) {
            clearInterval(qrTimerRef.current);
            qrTimerRef.current = null;
        }
    };

    const updateNested = (key: string, value: any) => {
        onUpdateConfig('cloud115', key, value);
    };

    const generateRealQr = async () => {
        if (config.cloud115.loginMethod === 'open_app' && !config.cloud115.appId) {
            setToast('请先填写第三方 AppID');
            return;
        }

        stopQrCheck();
        setQrState('loading');
        setQrImage('');
        setQrSessionId('');

        try {
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
                    const statusRes = await api.check115QrStatus(data.sessionId, 0, '');
                    const status = statusRes.data?.status || (statusRes as any).status || 'waiting';

                    switch (status) {
                        case 'scanned': setQrState('scanned'); break;
                        case 'success':
                            stopQrCheck();
                            setQrState('success');
                            // Notify parent to reload config or just show success
                            // Ideally we should reload config here but we rely on parent refetch or optimistically update
                            setToast('登录成功，Cookie 已自动保存');
                            break;
                        case 'expired':
                            stopQrCheck();
                            setQrState('expired');
                            break;
                        case 'error':
                            stopQrCheck();
                            setQrState('error');
                            break;
                    }
                } catch (err) {
                    console.error('QR Poll failed', err);
                }
            }, 3000);
        } catch (e: any) {
            console.error('QR Code generation failed:', e);
            setQrState('error');
            setToast(`生成失败: ${e.response?.data?.error || e.message}`);
            stopQrCheck();
        }
    };

    const inputClass = "w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-900/50 text-slate-800 dark:text-slate-100 focus:ring-2 focus:ring-brand-500 outline-none transition-all font-mono text-sm backdrop-blur-sm shadow-inner";

    return (
        <div className="space-y-6">
            {toast && (
                <div className="fixed top-6 right-6 bg-slate-800/90 backdrop-blur-md text-white px-6 py-3 rounded-xl shadow-2xl z-50 flex items-center gap-3 font-medium border-[0.5px] border-slate-700/50 animation-fade-in">
                    <RefreshCw size={18} className="text-brand-400" />
                    {toast}
                </div>
            )}

            {/* Login Method Tabs */}
            <div className="flex flex-wrap gap-3 mb-6">
                {[
                    { id: 'cookie', label: 'Cookie 导入', icon: Cookie },
                    { id: 'qrcode', label: '扫码获取', icon: QrCode },
                    { id: 'open_app', label: '第三方 App ID', icon: Smartphone }
                ].map((tab) => (
                    <button
                        key={tab.id}
                        onClick={() => updateNested('loginMethod', tab.id)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border-[0.5px] transition-all shadow-sm ${config.cloud115.loginMethod === tab.id
                                ? 'bg-brand-50 border-brand-200 text-brand-600 dark:bg-brand-900/20 dark:border-brand-800 dark:text-brand-400'
                                : 'bg-white/50 dark:bg-slate-800/50 border-slate-200 dark:border-slate-600 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-700/50'
                            }`}
                    >
                        <tab.icon size={16} /> {tab.label}
                    </button>
                ))}
            </div>

            {/* Cookie Method */}
            {config.cloud115.loginMethod === 'cookie' && (
                <div className="space-y-3 animate-in fade-in slide-in-from-bottom-2">
                    <label className="text-sm font-medium text-slate-600 dark:text-slate-400">Cookie 字符串</label>
                    <SensitiveInput
                        multiline
                        value={config.cloud115.cookies}
                        onChange={(e) => updateNested('cookies', e.target.value)}
                        placeholder="UID=...; CID=...; SEID=..."
                        className={inputClass}
                    />
                    <button
                        onClick={onSave}
                        disabled={isSaving || !config.cloud115.cookies}
                        className="px-5 py-2.5 bg-brand-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-lg hover:bg-brand-700 transition-colors disabled:opacity-50"
                    >
                        {isSaving ? <RefreshCw className="animate-spin" size={16} /> : <Save size={16} />}
                        登录 / 保存 Cookie
                    </button>
                </div>
            )}

            {/* QR / App ID Method */}
            {(config.cloud115.loginMethod === 'qrcode' || config.cloud115.loginMethod === 'open_app') && (
                <div className="border-[0.5px] border-dashed border-slate-300 dark:border-slate-700 rounded-xl p-8 flex flex-col items-center justify-center bg-slate-50/50 dark:bg-slate-900/30 animate-in fade-in slide-in-from-bottom-2">

                    {/* App ID Input */}
                    {config.cloud115.loginMethod === 'open_app' && (
                        <div className="w-full max-w-sm mb-6">
                            <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">App ID</label>
                            <SensitiveInput
                                value={config.cloud115.appId || ''}
                                onChange={(e) => updateNested('appId', e.target.value)}
                                className={inputClass}
                                placeholder="填写第三方应用的 AppID"
                            />
                        </div>
                    )}

                    {/* Standard QR App Selector */}
                    {config.cloud115.loginMethod === 'qrcode' && (
                        <div className="w-full max-w-sm mb-6">
                            <label className="text-xs font-bold text-slate-500 uppercase mb-3 block flex items-center gap-1">
                                <Smartphone size={14} /> 模拟登录终端
                            </label>
                            <select
                                value={config.cloud115.loginApp || 'android'}
                                onChange={(e) => updateNested('loginApp', e.target.value)}
                                className="w-full px-4 py-2.5 rounded-lg border-[0.5px] border-slate-300/50 dark:border-slate-600/50 bg-white/50 dark:bg-slate-700/50 text-slate-800 dark:text-slate-100 text-sm focus:ring-2 focus:ring-brand-500 outline-none backdrop-blur-sm"
                            >
                                {loginApps.map(app => (
                                    <option key={app.key} value={app.key}>{app.name}</option>
                                ))}
                                {!loginApps.length && <option value="android">安卓</option>}
                            </select>
                        </div>
                    )}

                    {/* Generate Button or QR Display */}
                    {!qrImage && qrState !== 'loading' ? (
                        <button onClick={generateRealQr} className="px-6 py-3 bg-brand-600 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-lg hover:bg-brand-700 transition-colors">
                            <QrCode size={18} />
                            {config.cloud115.loginMethod === 'qrcode' ? '生成二维码' : '获取授权二维码'}
                        </button>
                    ) : (
                        <div className="text-center relative">
                            {qrState === 'loading' ? (
                                <div className="w-48 h-48 flex items-center justify-center"><RefreshCw className="animate-spin text-brand-500" size={32} /></div>
                            ) : (
                                <div className="relative inline-block">
                                    <img
                                        src={qrImage}
                                        alt="QR"
                                        className={`w-48 h-48 rounded-lg border-4 border-white shadow-xl mx-auto mb-2 ${qrState === 'expired' ? 'opacity-20' : ''} ${qrState === 'success' ? 'ring-4 ring-green-400 ring-offset-2' : ''}`}
                                    />
                                    {qrState === 'success' && (
                                        <div className="absolute inset-0 flex items-center justify-center bg-green-500/80 rounded-lg animate-in fade-in zoom-in">
                                            <Check size={64} className="text-white" />
                                        </div>
                                    )}
                                    {qrState === 'scanned' && (
                                        <div className="absolute -top-2 -right-2 bg-yellow-500 text-white px-2 py-1 rounded-full text-xs font-bold animate-pulse shadow-lg">
                                            已扫描
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Status Message */}
                            <p className={`text-xs mt-3 font-bold ${qrState === 'success' ? 'text-green-500' : qrState === 'scanned' ? 'text-yellow-500' : 'text-slate-400'}`}>
                                {qrState === 'scanned' ? '✓ 已扫描，请在手机上确认' :
                                    qrState === 'success' ? '✓ 登录成功' :
                                        qrState === 'expired' ? '二维码已过期' :
                                            qrState === 'error' ? '生成失败' : '请使用 115 App 扫码'}
                            </p>

                            {(qrState === 'expired' || qrState === 'error') && (
                                <button onClick={generateRealQr} className="mt-3 text-xs bg-slate-800 text-white px-3 py-1.5 rounded-full flex items-center gap-1 mx-auto hover:scale-105 transition-transform">
                                    <RotateCcw size={12} /> 刷新
                                </button>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
