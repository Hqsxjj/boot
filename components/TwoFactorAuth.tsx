
import React, { useState } from 'react';
import { ShieldCheck, X } from 'lucide-react';
import { verify2FA } from '../services/auth';

interface TwoFactorAuthProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const TwoFactorAuth: React.FC<TwoFactorAuthProps> = ({ isOpen, onClose, onSuccess }) => {
  const [code, setCode] = useState('');
  const [error, setError] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (verify2FA(code)) {
      onSuccess();
      onClose();
      setCode('');
      setError(false);
    } else {
      setError(true);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden border border-slate-200 dark:border-slate-700">
        <div className="p-6">
          <div className="flex justify-between items-start mb-6">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-brand-100 dark:bg-brand-900/30 text-brand-600 dark:text-brand-400 rounded-lg">
                <ShieldCheck size={24} />
              </div>
              <h3 className="text-lg font-bold text-slate-800 dark:text-white">安全验证</h3>
            </div>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
              <X size={20} />
            </button>
          </div>
          
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">
            查看或修改敏感信息需要进行二次验证。请输入您的 2FA 验证码 (测试码: 123456)。
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="text"
              value={code}
              onChange={(e) => { setCode(e.target.value); setError(false); }}
              placeholder="输入 6 位验证码"
              className={`w-full text-center text-2xl tracking-widest font-mono py-3 rounded-xl border ${error ? 'border-red-500 ring-red-500/20' : 'border-slate-300 dark:border-slate-600'} bg-slate-50 dark:bg-slate-900 focus:ring-4 focus:outline-none transition-all`}
              maxLength={6}
              autoFocus
            />
            {error && <p className="text-xs text-red-500 text-center font-medium">验证码错误，请重试。</p>}
            
            <button
              type="submit"
              className="w-full bg-brand-600 hover:bg-brand-700 text-white font-bold py-3 rounded-xl shadow-lg shadow-brand-500/30 active:scale-95 transition-all"
            >
              验证身份
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
