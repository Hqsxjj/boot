
import React from 'react';

export const Logo: React.FC<{ collapsed?: boolean }> = ({ collapsed = false }) => {
  return (
    <div className={`flex items-center gap-3 select-none ${collapsed ? 'justify-center' : ''} group`}>
      <div className="relative w-10 h-10 flex items-center justify-center">
        {/* Abstract Cloud/Link Shape */}
        <div className="absolute inset-0 bg-gradient-to-br from-brand-400 to-indigo-600 rounded-xl rotate-6 group-hover:rotate-12 transition-transform duration-500 ease-out shadow-lg shadow-brand-500/20"></div>
        <div className="absolute inset-0.5 bg-slate-900 rounded-[10px] z-0"></div>
        
        <svg 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round" 
          strokeLinejoin="round" 
          className="relative z-10 w-6 h-6 text-brand-400 group-hover:text-white transition-colors duration-300"
        >
          <path d="M17.5 19c0-1.7-1.3-3-3-3h-1.1c-.1-2.9-2.5-5.3-5.4-5.3-1.8 0-3.5 1-4.4 2.5C1.8 13.5 1 15.6 1.8 17.6c.6 1.6 2.1 2.6 3.7 2.4h9c1.7 0 3-1.3 3-3z" />
          <path d="M14 13l3.5-3.5" />
          <path d="M22 14.5L17.5 9.5" />
          <path d="M19 19h1" />
        </svg>
      </div>
      
      {!collapsed && (
        <div className="flex flex-col">
          <h1 className="font-bold text-xl tracking-tight text-white leading-none flex items-center gap-1">
            115<span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-400 to-indigo-400 font-light">Bot</span>
          </h1>
          <span className="text-[10px] text-slate-500 font-medium tracking-widest uppercase">管理面板</span>
        </div>
      )}
    </div>
  );
};
