
import React from 'react';
import { Copy } from 'lucide-react';

interface CommandCardProps {
  command: string;
  description: string;
  example?: string;
}

export const CommandCard: React.FC<CommandCardProps> = ({ command, description, example }) => {
  const copyToClipboard = () => {
    navigator.clipboard.writeText(command);
  };

  return (
    <div className="bg-slate-50/50 dark:bg-slate-800/50 rounded-lg border border-slate-200/50 dark:border-slate-700/50 p-4 transition-colors hover:bg-slate-100/50 dark:hover:bg-slate-800/80 backdrop-blur-sm group">
      <div className="flex justify-between items-start mb-2">
        <code className="bg-white/80 dark:bg-slate-900/80 text-brand-600 dark:text-brand-400 px-2 py-1 rounded text-sm font-mono font-bold shadow-sm">
          {command}
        </code>
        <button 
          onClick={copyToClipboard}
          className="text-slate-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors opacity-0 group-hover:opacity-100"
          title="复制命令"
        >
          <Copy size={16} />
        </button>
      </div>
      <p className="text-slate-600 dark:text-slate-300 text-sm mb-2">{description}</p>
      {example && (
        <div className="text-xs text-slate-500 dark:text-slate-400 bg-white/40 dark:bg-black/20 p-2 rounded border border-slate-200/50 dark:border-slate-700/50 font-mono mt-2 truncate">
          <span className="text-slate-400 select-none">$ </span>{example}
        </div>
      )}
    </div>
  );
};
