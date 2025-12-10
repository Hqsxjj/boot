import React from 'react';
import { AlertCircle } from 'lucide-react';

interface TooltipProps {
  content: string;
}

export const Tooltip: React.FC<TooltipProps> = ({ content }) => {
  return (
    <div className="group relative inline-flex items-center ml-2 align-middle">
      <AlertCircle 
        size={15} 
        className="text-brand-500 cursor-help opacity-70 hover:opacity-100 transition-opacity" 
      />
      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block w-48 p-2 bg-slate-800 text-white text-xs rounded shadow-lg z-20 pointer-events-none transition-all">
        {content}
        {/* Arrow */}
        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800"></div>
      </div>
    </div>
  );
};