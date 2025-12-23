
import React from 'react';
import { ViewState } from '../types';
import { UserCog, CloudCog, Tv, Terminal, LogOut, Sun, Moon, PanelLeftClose, PanelLeftOpen, Sparkles, Palette } from 'lucide-react';
import { Logo } from './Logo';

interface SidebarProps {
  currentView: ViewState;
  onChangeView: (view: ViewState) => void;
  isDark: boolean;
  toggleTheme: () => void;
  onLogout: () => void;
  collapsed: boolean;
  toggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onChangeView,
  isDark,
  toggleTheme,
  onLogout,
  collapsed,
  toggleCollapse
}) => {
  const navItems = [
    { id: ViewState.USER_CENTER, label: '用户中心', icon: UserCog },
    { id: ViewState.CLOUD_ORGANIZE, label: '网盘整理', icon: CloudCog },
    { id: ViewState.RESOURCE_SEARCH, label: '资源搜索', icon: Sparkles },
    { id: ViewState.EMBY_INTEGRATION, label: 'Emby 联动', icon: Tv },
    { id: ViewState.COVER_GENERATOR, label: '封面工坊', icon: Palette },
    { id: ViewState.LOGS, label: '运行日志', icon: Terminal },
  ];

  return (
    <div className={`hidden md:flex flex-col h-screen fixed left-0 top-0 z-30 transition-all duration-300 ease-in-out
      ${collapsed ? 'w-20' : 'w-64'}
      bg-white/70 dark:bg-slate-900/60 backdrop-blur-xl 
      border-r border-white/50 dark:border-slate-700/50 shadow-2xl`}
    >

      {/* Header */}
      <div className={`h-20 flex items-center border-b border-slate-200/50 dark:border-slate-700/50 ${collapsed ? 'justify-center px-0' : 'px-6'}`}>
        <Logo collapsed={collapsed} />
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto custom-scrollbar overflow-x-hidden">
        {!collapsed && <div className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-3 px-3 mt-4 whitespace-nowrap">功能菜单</div>}
        {navItems.map((item) => {
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onChangeView(item.id)}
              title={collapsed ? item.label : undefined}
              className={`w-full flex items-center ${collapsed ? 'justify-center px-0 py-3' : 'gap-3 px-3 py-3'} rounded-xl transition-all duration-200 group relative ${isActive
                ? 'bg-brand-50/80 text-brand-600 dark:bg-brand-900/30 dark:text-brand-400 font-bold shadow-sm backdrop-blur-sm'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100/50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-slate-200'
                }`}
            >
              {isActive && <div className="absolute left-0 top-1 bottom-1 w-1 bg-brand-500 rounded-r-full"></div>}
              <item.icon size={collapsed ? 24 : 18} className={`transition-colors shrink-0 ${isActive ? 'text-brand-600 dark:text-brand-400' : 'text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300'}`} />
              {!collapsed && <span className="text-sm tracking-wide whitespace-nowrap">{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className={`p-4 border-t border-slate-200/50 dark:border-slate-700/50 bg-slate-50/30 dark:bg-slate-900/30 flex flex-col gap-3 ${collapsed ? 'items-center' : ''}`}>

        {/* Toggle Collapse Button (Integrated) */}
        <button
          onClick={toggleCollapse}
          className={`flex items-center gap-2 text-slate-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors w-full ${collapsed ? 'justify-center py-2' : 'px-2 py-1'}`}
          title={collapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          {collapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={18} />}
          {!collapsed && <span className="text-xs font-medium">收起菜单</span>}
        </button>

        {!collapsed && (
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-slate-100/50 dark:bg-black/20 border border-slate-200/50 dark:border-white/5 overflow-hidden backdrop-blur-sm">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse shrink-0"></div>
            <div className="flex flex-col whitespace-nowrap">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-300">端口: 18080</span>
            </div>
          </div>
        )}

        <div className={`grid ${collapsed ? 'grid-cols-1 gap-4' : 'grid-cols-2 gap-2'}`}>
          <button
            onClick={toggleTheme}
            className={`flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white hover:bg-slate-200/50 dark:hover:bg-slate-700/50 rounded-lg transition-colors ${collapsed ? 'w-10 h-10 p-0' : ''}`}
            title="切换主题"
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
            {!collapsed && '主题'}
          </button>

          <button
            onClick={onLogout}
            className={`flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-red-600 dark:hover:text-red-300 hover:bg-red-50/50 dark:hover:bg-red-500/10 rounded-lg transition-colors ${collapsed ? 'w-10 h-10 p-0' : ''}`}
            title="退出登录"
          >
            <LogOut size={18} />
            {!collapsed && '退出'}
          </button>
        </div>
      </div>
    </div>
  );
};
