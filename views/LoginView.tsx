
import React, { useState, useEffect } from 'react';
import { Logo } from '../components/Logo';
import { login, isLocked, getFailedAttempts } from '../services/auth';
import { User, KeyRound, AlertOctagon, ArrowRight } from 'lucide-react';

interface LoginViewProps {
  onLoginSuccess: () => void;
}

export const LoginView: React.FC<LoginViewProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [locked, setLocked] = useState(isLocked());
  
  useEffect(() => {
    if (locked) {
      setError('系统已锁定');
    }
  }, [locked]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (locked) return;

    const result = await login(username, password);

    if (result.success) {
      onLoginSuccess();
      return;
    }

    if (result.locked) {
      setLocked(true);
      setError('已锁定');
      return;
    }

    if (result.error === 'network') {
      setError('连接服务器失败');
      return;
    }

    setError(`登录失败 (剩余次数: ${5 - getFailedAttempts()})`);
    setPassword('');
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden z-10">
      <div className="max-w-md w-full relative z-20 animate-in fade-in zoom-in duration-500">
        
        {/* Brand Header */}
        <div className="text-center mb-10 flex flex-col items-center">
          <div className="scale-150 mb-6 drop-shadow-2xl filter hover:brightness-110 transition-all">
             <Logo />
          </div>
        </div>

        {/* Login Card (Glassmorphism) */}
        <div className="bg-black/40 backdrop-blur-2xl rounded-3xl shadow-2xl border border-white/10 overflow-hidden relative">
          
          {/* Lockout Overlay */}
          {locked && (
            <div className="absolute inset-0 bg-red-950/90 z-30 flex flex-col items-center justify-center p-8 text-center animate-in fade-in duration-300">
               <div className="w-16 h-16 bg-red-500/20 text-red-200 rounded-full flex items-center justify-center mb-4 border border-red-500/50">
                 <AlertOctagon size={32} />
               </div>
               <h3 className="text-xl font-bold text-white mb-2">已锁定</h3>
               <div className="bg-black/50 border border-red-500/30 rounded-lg p-4 w-full text-left">
                 <code className="block text-green-400 font-mono text-xs">
                   docker restart 115-bot
                 </code>
               </div>
            </div>
          )}

          <div className="p-8">
            <h2 className="text-2xl font-bold text-white mb-6 text-center">管理员登录</h2>
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-4">
                <div className="relative group">
                    <User className="absolute left-4 top-3.5 text-slate-400 group-focus-within:text-brand-300 transition-colors" size={18} />
                    <input 
                    type="text" 
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="用户名"
                    className="w-full pl-11 pr-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder:text-slate-500 focus:ring-2 focus:ring-brand-500/50 focus:bg-white/10 outline-none transition-all"
                    disabled={locked}
                    />
                </div>

                <div className="relative group">
                    <KeyRound className="absolute left-4 top-3.5 text-slate-400 group-focus-within:text-brand-300 transition-colors" size={18} />
                    <input 
                    type="password" 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="密码"
                    className="w-full pl-11 pr-4 py-3 rounded-xl border border-white/10 bg-white/5 text-white placeholder:text-slate-500 focus:ring-2 focus:ring-brand-500/50 focus:bg-white/10 outline-none transition-all"
                    disabled={locked}
                    />
                </div>
              </div>

              {error && (
                <div className="text-red-300 bg-red-900/40 py-2 rounded-lg text-xs font-medium text-center border border-red-500/30 animate-in slide-in-from-top-1">
                  {error}
                </div>
              )}

              <button 
                type="submit" 
                disabled={locked}
                className="w-full bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 text-white font-bold py-3.5 rounded-xl shadow-lg shadow-brand-900/50 transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed mt-2 border border-white/10 flex items-center justify-center gap-2 group"
              >
                进入系统 <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform"/>
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
