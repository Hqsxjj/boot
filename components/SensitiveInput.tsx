import React, { useState } from 'react';
import { Eye, EyeOff, Lock } from 'lucide-react';

interface SensitiveInputProps {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  placeholder?: string;
  className?: string;
  multiline?: boolean;
}

export const SensitiveInput: React.FC<SensitiveInputProps> = ({
  value,
  onChange,
  placeholder,
  className = "",
  multiline = false
}) => {
  const [isRevealed, setIsRevealed] = useState(false);

  const handleToggle = () => {
    setIsRevealed(!isRevealed);
  };

  // 基础样式处理，适配暗色模式
  const baseInputClass = `${className} transition-all duration-200 focus:ring-2 focus:ring-brand-500/50 outline-none`;

  return (
    <div className="relative group">
      {multiline ? (
        // 多行文本框 (Textarea) - 适用于 Cookie
        <div className="relative">
          <textarea
            value={value}
            onChange={onChange}
            placeholder={placeholder}
            rows={4}
            className={`${baseInputClass} ${!isRevealed ? 'text-slate-400 tracking-widest blur-[2px] select-none cursor-default' : 'font-mono text-xs'}`}
            readOnly={!isRevealed} // 隐藏时禁止编辑防止误触
          />
          {/* 遮罩层，当未揭示且有内容时显示 */}
          {!isRevealed && value && (
            <div
              onClick={handleToggle}
              className="absolute inset-0 z-10 flex items-center justify-center cursor-pointer hover:bg-slate-50/10 transition-colors rounded-lg"
            >
              <div className="bg-slate-100/90 dark:bg-slate-800/90 px-4 py-2 rounded-full border border-slate-200 dark:border-slate-600 backdrop-blur-sm shadow-sm flex items-center gap-2 text-xs font-bold text-slate-500 tracking-wider">
                <Lock size={12} /> 内容已隐藏 (点击查看)
              </div>
            </div>
          )}
        </div>
      ) : (
        // 单行输入框 (Input) - 适用于 Password / Key
        <input
          type={isRevealed && value !== '__MASKED__' ? "text" : "password"}
          value={isRevealed && value === '__MASKED__' ? '(内容已隐藏，输入新值以修改)' : value}
          onChange={onChange}
          placeholder={placeholder}
          className={`${baseInputClass} ${!isRevealed && value ? 'tracking-widest' : ''} ${value === '__MASKED__' && isRevealed ? 'text-slate-400 italic text-xs' : ''}`}
          readOnly={isRevealed && value === '__MASKED__'}
        />
      )}

      {/* 切换按钮 */}
      <button
        type="button"
        onClick={handleToggle}
        className="absolute right-3 top-3 text-slate-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors z-20 p-1 rounded-md hover:bg-slate-200/50 dark:hover:bg-slate-700/50"
        title={isRevealed ? "隐藏内容" : "显示内容"}
      >
        {isRevealed ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
};
