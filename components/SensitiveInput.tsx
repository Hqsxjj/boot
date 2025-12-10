
import React, { useState, useEffect } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';
import { check2FA } from '../services/auth';
import { TwoFactorAuth } from './TwoFactorAuth';

interface SensitiveInputProps {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  placeholder?: string;
  className?: string;
  multiline?: boolean;
}

export const SensitiveInput: React.FC<SensitiveInputProps> = ({ value, onChange, placeholder, className, multiline }) => {
  const [isRevealed, setIsRevealed] = useState(false);
  const [is2FAModalOpen, setIs2FAModalOpen] = useState(false);
  const [isVerified, setIsVerified] = useState(false);

  useEffect(() => {
    setIsVerified(check2FA());
  }, []);

  const handleToggle = () => {
    if (isRevealed) {
      setIsRevealed(false);
    } else {
      if (check2FA()) {
        setIsRevealed(true);
        setIsVerified(true);
      } else {
        setIs2FAModalOpen(true);
      }
    }
  };

  const handle2FASuccess = () => {
    setIsVerified(true);
    setIsRevealed(true);
  };

  // Base transparency for inputs to fit glass theme
  const baseClass = className || "";
  const glassClass = baseClass.includes('bg-') ? "" : "bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm";

  return (
    <div className="relative group">
      {multiline ? (
        isRevealed ? (
          <textarea
            value={value}
            onChange={onChange}
            placeholder={placeholder}
            rows={4}
            className={`${className} ${glassClass}`}
          />
        ) : (
          <div 
            onClick={handleToggle}
            className={`${className} ${glassClass} cursor-pointer flex flex-col gap-1 text-slate-400 select-none overflow-hidden hover:bg-slate-50/50 dark:hover:bg-slate-800/80 transition-colors min-h-[100px] relative`}
          >
             {value ? (
               <div className="w-full h-full opacity-40 font-mono text-xs leading-6 break-all">
                 {/* Simulated Masked Content */}
                 UID=••••••••••••; CID=••••••••••••••••••••; SEID=•••••••••••••••••••••••••••••••;<br/>
                 token=••••••••••••••••••••••••••••••••••••••••••••••••;
               </div>
             ) : (
               <span className="text-sm opacity-50 pt-2">{placeholder}</span>
             )}
             
             <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="bg-slate-100/90 dark:bg-slate-800/90 px-4 py-2 rounded-full border border-slate-200 dark:border-slate-600 backdrop-blur-sm shadow-sm flex items-center gap-2 text-xs font-bold text-slate-500 tracking-wider">
                    <Lock size={12} /> 已隐藏 (点击查看)
                </div>
             </div>
          </div>
        )
      ) : (
        <input
          type={isRevealed ? "text" : "password"}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={!isRevealed && !isVerified}
          className={`${className} ${glassClass} ${!isRevealed ? 'text-slate-500 tracking-widest' : ''}`}
        />
      )}
      
      {!isVerified && !isRevealed && !multiline && (
         <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
            {value && (
              <span className="flex items-center gap-1.5 text-slate-500 text-[10px] font-bold tracking-widest bg-slate-100/90 dark:bg-slate-800/90 px-3 py-1.5 rounded-full border border-slate-200 dark:border-slate-600 backdrop-blur-sm shadow-sm">
                <Lock size={10} /> 2FA PROTECTED
              </span>
            )}
         </div>
      )}

      <button
        type="button"
        onClick={handleToggle}
        className="absolute right-3 top-3 text-slate-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors z-20 bg-transparent p-1 rounded-md hover:bg-slate-100/50 dark:hover:bg-slate-700/50"
        title={isRevealed ? "隐藏内容" : "查看/编辑 (需 2FA 验证)"}
      >
        {isRevealed ? <EyeOff size={18} /> : (isVerified ? <Eye size={18} /> : <Lock size={16} />)}
      </button>

      <TwoFactorAuth 
        isOpen={is2FAModalOpen} 
        onClose={() => setIs2FAModalOpen(false)} 
        onSuccess={handle2FASuccess} 
      />
    </div>
  );
};
