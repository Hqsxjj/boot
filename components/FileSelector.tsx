import React, { useState, useEffect } from 'react';
import { Folder, File, ChevronRight, Check, X, HardDrive, ArrowLeft, Loader2 } from 'lucide-react';
import { api } from '../services/api';

interface FileSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (cid: string, name: string) => void;
  title?: string;
  cloudType?: '115' | '123';  // 云盘类型
}

interface FileNode {
  id: string; // cid
  name: string;
  is_dir: boolean;
  time?: string;
}

export const FileSelector: React.FC<FileSelectorProps> = ({
  isOpen,
  onClose,
  onSelect,
  title = "选择文件夹",
  cloudType = '115'  // 默认 115 网盘
}) => {
  // 历史记录栈，用于面包屑导航和返回上一级
  const [history, setHistory] = useState<Array<{ id: string, name: string }>>([{ id: '0', name: '根目录' }]);

  // 当前文件列表
  const [files, setFiles] = useState<FileNode[]>([]);

  // 选中的项
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedName, setSelectedName] = useState<string>('');

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 获取当前目录 ID
  // const currentFolderId = history[history.length - 1].id; // Unused

  // 根据云盘类型获取初始目录 ID
  const getInitialDirId = () => {
    switch (cloudType) {
      case '123':
        return '/';
      default:
        return '0';
    }
  };

  // 根据云盘类型加载文件列表
  const loadFiles = async (dirId: string) => {
    setIsLoading(true);
    setError(null);
    try {
      let items: FileNode[] = [];

      switch (cloudType) {
        case '115': {
          // 115 网盘 API
          const data = await api.get115Files(dirId);
          if (data && data.files) {
            items = data.files.map((f: any) => ({
              id: f.id || f.cid || f.file_id,
              name: f.name || f.n,
              is_dir: f.is_dir || f.file_type === 0,
              time: f.time || f.t || ''
            }));
          }
          break;
        }
        case '123': {
          // 123 云盘 API - 返回 {id, name, children (is_dir), date}
          const data = await api.list123Directories(dirId);
          if (data && Array.isArray(data)) {
            items = data.map((f: any) => ({
              id: f.id,
              name: f.name,
              is_dir: f.children === true || f.is_dir === true,  // 兼容两种格式
              time: f.date || f.time || ''
            }));
          }
          break;
        }
      }

      setFiles(items);
    } catch (e) {
      console.error("加载目录失败", e);
      setError(`加载失败: ${cloudType === '115' ? '请先登录 115 账号' : cloudType === '123' ? '请先配置 123 云盘凭证' : '服务未连接'}`);
      setFiles([]);
    } finally {
      setIsLoading(false);
    }
  };

  // 初始化加载
  useEffect(() => {
    if (isOpen) {
      const initialId = getInitialDirId();
      setHistory([{ id: initialId, name: '根目录' }]);
      setSelectedId(null);
      setError(null);
      loadFiles(initialId);
    }
  }, [isOpen, cloudType]);

  // 进入下级目录
  const handleNavigate = (folder: { id: string, name: string }) => {
    const newHistory = [...history, folder];
    setHistory(newHistory);
    loadFiles(folder.id);
    // 进入新目录时，清除选中状态
    setSelectedId(null);
  };

  // 返回上级目录
  const handleUp = () => {
    if (history.length > 1) {
      const newHistory = history.slice(0, -1);
      const prevFolderId = newHistory[newHistory.length - 1].id;

      setHistory(newHistory);
      loadFiles(prevFolderId);
      setSelectedId(null);
    }
  };

  const handleConfirm = () => {
    // 如果有选中的子文件夹，使用选中的
    if (selectedId) {
      onSelect(selectedId, selectedName);
    } else {
      // 如果没有选中任何子文件夹，则选择“当前所在的目录”
      const current = history[history.length - 1];
      onSelect(current.id, current.name);
    }
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden border border-slate-200 dark:border-slate-700 flex flex-col h-[500px]">
        {/* Header */}
        <div className="p-4 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center bg-slate-50 dark:bg-slate-900/50">
          <div className="flex items-center gap-2">
            <HardDrive size={18} className="text-brand-600" />
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
            className="p-1.5 bg-white dark:bg-slate-700 rounded-md text-slate-600 dark:text-slate-300 disabled:opacity-30 disabled:cursor-not-allowed hover:bg-slate-200 dark:hover:bg-slate-600 transition-colors shadow-sm"
          >
            <ArrowLeft size={16} />
          </button>
          <div className="flex-1 overflow-x-auto scrollbar-hide flex items-center whitespace-nowrap px-1">
            {history.map((p, idx) => (
              <div key={p.id} className="flex items-center">
                <span className={`font-medium text-xs ${idx === history.length - 1 ? 'text-brand-600 dark:text-brand-400 font-bold' : 'text-slate-500'}`}>{p.name}</span>
                {idx < history.length - 1 && <ChevronRight size={12} className="mx-1 text-slate-300" />}
              </div>
            ))}
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto p-2 relative custom-scrollbar bg-slate-50/30 dark:bg-slate-900/20">
          {isLoading ? (
            <div className="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-slate-800/50 z-10">
              <div className="flex flex-col items-center gap-2 text-brand-600">
                <Loader2 className="animate-spin" size={32} />
                <span className="text-xs font-medium">加载目录中...</span>
              </div>
            </div>
          ) : (
            <>
              {files.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-400">
                  <Folder size={48} className="mb-2 opacity-20" />
                  <span className="text-sm">空文件夹</span>
                </div>
              ) : (
                files.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => { setSelectedId(item.id); setSelectedName(item.name); }}
                    onDoubleClick={() => { if (item.is_dir) handleNavigate(item); }}
                    className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors mb-1 group border ${selectedId === item.id ? 'bg-brand-50 dark:bg-brand-900/20 border-brand-200 dark:border-brand-800' : 'bg-white dark:bg-slate-800 border-transparent hover:border-slate-200 dark:hover:border-slate-600 hover:shadow-sm'}`}
                  >
                    <div className="flex items-center gap-3 overflow-hidden">
                      <div className={`p-2 rounded-lg transition-colors shrink-0 ${selectedId === item.id ? 'bg-brand-100 text-brand-600' : 'bg-slate-100 dark:bg-slate-700 text-slate-500 group-hover:bg-slate-200 dark:group-hover:bg-slate-600'}`}>
                        {item.is_dir ? (
                          <Folder size={20} className={selectedId === item.id ? 'fill-brand-600/20' : 'fill-slate-400/20'} />
                        ) : (
                          <File size={20} className={selectedId === item.id ? 'fill-brand-600/20' : 'fill-slate-400/20'} />
                        )}
                      </div>
                      <div className="min-w-0">
                        <div className={`text-sm font-medium truncate ${selectedId === item.id ? 'text-brand-700 dark:text-brand-300' : 'text-slate-700 dark:text-slate-200'}`}>{item.name}</div>
                        {item.time && <div className="text-[10px] text-slate-400">{item.time}</div>}
                      </div>
                    </div>
                    {item.is_dir && <ChevronRight size={16} className="text-slate-300 shrink-0" />}
                  </div>
                ))
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 dark:border-slate-700 flex justify-between items-center bg-white dark:bg-slate-800">
          <div className="text-xs text-slate-500 max-w-[200px] truncate flex flex-col">
            <span className="opacity-70">已选:</span>
            <span className="font-bold text-brand-600 dark:text-brand-400">
              {selectedId ? selectedName : history[history.length - 1].name}
            </span>
          </div>
          <div className="flex gap-3">
            <button onClick={onClose} className="px-4 py-2 text-slate-500 hover:text-slate-700 text-sm font-medium">取消</button>
            <button
              onClick={handleConfirm}
              className="px-6 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm font-bold flex items-center gap-2 shadow-lg shadow-brand-500/20 transition-all active:scale-95"
            >
              <Check size={16} /> 确认选择
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};