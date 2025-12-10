
import React, { useState, useEffect } from 'react';
import { Folder, ChevronRight, Check, X, HardDrive, ArrowLeft } from 'lucide-react';

interface FileSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (cid: string, name: string) => void;
  title?: string;
}

// Mock File System with hierarchy to simulate p115client browsing
const MOCK_FILE_SYSTEM: Record<string, Array<{id: string, name: string, children: boolean, date: string}>> = {
  '0': [
    { id: '101', name: '电影 (Movies)', children: true, date: '2023-10-25' },
    { id: '102', name: '电视剧 (TV Shows)', children: true, date: '2023-10-26' },
    { id: '103', name: '动漫 (Anime)', children: true, date: '2023-10-28' },
    { id: '104', name: '下载中转', children: false, date: '2023-10-29' },
    { id: '105', name: 'Telegram 机器人下载', children: false, date: '2023-10-29' },
  ],
  '101': [
    { id: '1011', name: '动作片', children: false, date: '2023-09-10' },
    { id: '1012', name: '科幻片', children: false, date: '2023-09-15' },
    { id: '1013', name: '华语电影', children: false, date: '2023-09-20' },
  ],
  '102': [
    { id: '1021', name: '美剧', children: false, date: '2023-08-01' },
    { id: '1022', name: '国产剧', children: false, date: '2023-08-05' },
    { id: '1023', name: '日韩剧', children: false, date: '2023-08-12' },
  ],
  '103': [
    { id: '1031', name: '新番连载', children: false, date: '2023-10-01' },
    { id: '1032', name: '完结经典', children: false, date: '2023-10-02' },
  ]
};

export const FileSelector: React.FC<FileSelectorProps> = ({ isOpen, onClose, onSelect, title = "选择文件夹" }) => {
  const [history, setHistory] = useState<Array<{id: string, name: string}>>([{id: '0', name: '根目录'}]);
  const [currentFiles, setCurrentFiles] = useState(MOCK_FILE_SYSTEM['0']);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedName, setSelectedName] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);

  // Get current folder ID
  const currentFolderId = history[history.length - 1].id;

  useEffect(() => {
    if (isOpen) {
      // Reset state when opening
      setHistory([{id: '0', name: '根目录'}]);
      setCurrentFiles(MOCK_FILE_SYSTEM['0']);
      setSelectedId(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleNavigate = (folder: {id: string, name: string}) => {
    setIsLoading(true);
    // Simulate network delay for p115client fetch
    setTimeout(() => {
      setHistory([...history, folder]);
      setCurrentFiles(MOCK_FILE_SYSTEM[folder.id] || []); // Fallback to empty if not defined
      setIsLoading(false);
    }, 300);
  };

  const handleUp = () => {
    if (history.length > 1) {
      const newHistory = history.slice(0, -1);
      const prevFolderId = newHistory[newHistory.length - 1].id;
      
      setIsLoading(true);
      setHistory(newHistory);
      setTimeout(() => {
        setCurrentFiles(MOCK_FILE_SYSTEM[prevFolderId] || []);
        setIsLoading(false);
      }, 150);
    }
  };

  const handleConfirm = () => {
    if (selectedId) {
      onSelect(selectedId, selectedName);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden border border-slate-200 dark:border-slate-700 flex flex-col h-[500px]">
        {/* Header */}
        <div className="p-4 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
          <div className="flex items-center gap-2">
             <HardDrive size={18} className="text-brand-500"/>
             <h3 className="font-bold text-slate-700 dark:text-slate-200">{title}</h3>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-full transition-colors">
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {/* Breadcrumb / Navigation */}
        <div className="p-3 bg-slate-100 dark:bg-slate-900/30 flex items-center gap-2 text-sm border-b border-slate-200 dark:border-slate-700">
           <button 
             onClick={handleUp} 
             disabled={history.length <= 1}
             className="p-1.5 bg-white dark:bg-slate-700 rounded-md text-slate-600 dark:text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors"
           >
             <ArrowLeft size={16} />
           </button>
           <div className="flex-1 overflow-x-auto scrollbar-hide flex items-center whitespace-nowrap">
             {history.map((p, idx) => (
               <div key={p.id} className="flex items-center">
                  <span className={`font-medium ${idx === history.length - 1 ? 'text-brand-600 dark:text-brand-400' : 'text-slate-500'}`}>{p.name}</span>
                  {idx < history.length - 1 && <ChevronRight size={14} className="mx-1 text-slate-300" />}
               </div>
             ))}
           </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-2 relative custom-scrollbar">
           {isLoading ? (
             <div className="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-slate-800/50 z-10">
               <div className="w-8 h-8 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin"></div>
             </div>
           ) : (
             <>
               {currentFiles.length === 0 ? (
                 <div className="h-full flex flex-col items-center justify-center text-slate-400">
                    <Folder size={48} className="mb-2 opacity-20" />
                    <span className="text-sm">空文件夹</span>
                 </div>
               ) : (
                 currentFiles.map((folder) => (
                   <div 
                      key={folder.id}
                      onClick={() => { setSelectedId(folder.id); setSelectedName(folder.name); }}
                      onDoubleClick={() => folder.children && handleNavigate(folder)}
                      className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors mb-1 group ${selectedId === folder.id ? 'bg-brand-50 dark:bg-brand-900/20 border border-brand-200 dark:border-brand-800' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50 border border-transparent'}`}
                   >
                      <div className="flex items-center gap-3">
                         <div className={`p-2 rounded-lg transition-colors ${selectedId === folder.id ? 'bg-brand-100 text-brand-600' : 'bg-slate-100 dark:bg-slate-700 text-slate-500 group-hover:bg-slate-200 dark:group-hover:bg-slate-600'}`}>
                            <Folder size={20} />
                         </div>
                         <div>
                            <div className={`text-sm font-medium ${selectedId === folder.id ? 'text-brand-700 dark:text-brand-300' : 'text-slate-700 dark:text-slate-200'}`}>{folder.name}</div>
                            <div className="text-[10px] text-slate-400">{folder.date}</div>
                         </div>
                      </div>
                      {folder.children && <ChevronRight size={16} className="text-slate-300" />}
                   </div>
                 ))
               )}
             </>
           )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 dark:border-slate-700 flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
           <div className="text-xs text-slate-400 max-w-[150px] truncate">
              {selectedId ? `已选: ${selectedName} (CID: ${selectedId})` : '请选择目录'}
           </div>
           <div className="flex gap-3">
             <button onClick={onClose} className="px-4 py-2 text-slate-500 hover:text-slate-700 text-sm font-medium">取消</button>
             <button 
               onClick={handleConfirm}
               disabled={!selectedId}
               className="px-6 py-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-lg shadow-brand-500/20 transition-all active:scale-95"
             >
               <Check size={16} /> 确认
             </button>
           </div>
        </div>
      </div>
    </div>
  );
};
