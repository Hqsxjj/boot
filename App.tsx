import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { UserCenterView } from './views/UserCenterView';
import { BotSettingsView } from './views/BotSettingsView';
import { CloudOrganizeView } from './views/CloudOrganizeView';
import { EmbyView } from './views/EmbyView';
import { StrmView } from './views/StrmView';
import { LogsView } from './views/LogsView';
import { LoginView } from './views/LoginView';
import { ViewState } from './types';
import { checkAuth, logout } from './services/auth';
import { loadConfig } from './services/mockConfig';
import { Menu, X, LogOut, Sun, Moon } from 'lucide-react';
import { Logo } from './components/Logo';

// High-quality Sci-Fi/Tech/Cinematic backdrops suitable for a Bot Admin Interface
const FALLBACK_BACKDROPS = [
  'https://image.tmdb.org/t/p/original/ilRyazdMJwN05exqhwK4tMKBYZs.jpg', // Blade Runner 2049 (Orange/Teal)
  'https://image.tmdb.org/t/p/original/kjFonKwBSNYiQ8fVvnYhBL9s9E7.jpg', // Tron: Legacy (Blue/Tech)
  'https://image.tmdb.org/t/p/original/jYEW5xZkZk2WTrdbMGAPFuBqbDc.jpg', // Dune (Minimalist/Sand)
  'https://image.tmdb.org/t/p/original/rAiYTfKGqDCRIIqo664sY9XZIVQ.jpg', // Interstellar (Space)
  'https://image.tmdb.org/t/p/original/5p3aIQUw425L5VdFtO9TysVwN5G.jpg', // The Creator (Modern Sci-Fi)
  'https://image.tmdb.org/t/p/original/8rpDcsfLJypbO6vREc0547FVq5q.jpg', // Avatar (Blue/Nature)
  'https://image.tmdb.org/t/p/original/tmU7GeKVybMWFButWEGl2Mdbj47.jpg', // The Godfather (Dark/Classic)
];

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  const [currentView, setCurrentView] = useState<ViewState>(ViewState.USER_CENTER);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  
  // Background State
  const [backdrops, setBackdrops] = useState<string[]>([]);
  const [currentBackdropIndex, setCurrentBackdropIndex] = useState(0);

  // Theme State
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('theme');
      return saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches);
    }
    return false;
  });

  useEffect(() => {
    setIsAuthenticated(checkAuth());
    setIsChecking(false);
  }, []);

  // Theme Effect
  useEffect(() => {
    const root = window.document.documentElement;
    if (isDark) {
      root.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      root.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDark]);

  // Global Background Fetching (TMDB High Quality)
  useEffect(() => {
    const fetchBackdrops = async () => {
        const config = loadConfig();
        const apiKey = config.tmdb.apiKey;
        
        let loaded = false;
        if (apiKey && apiKey.length > 10) {
            try {
                // Use 'discover' to filter for high quality (High popularity + High vote count)
                // Added with_genres=878 (Science Fiction) to match the Bot/Tech theme better
                const res = await fetch(`https://api.themoviedb.org/3/discover/movie?api_key=${apiKey}&language=zh-CN&sort_by=popularity.desc&include_adult=false&include_video=false&page=1&vote_count.gte=1000&vote_average.gte=7&with_genres=878`);
                
                if (res.ok) {
                    const data = await res.json();
                    if (data.results && data.results.length > 0) {
                         const paths = data.results
                            .filter((m: any) => m.backdrop_path)
                            .slice(0, 20) // Fetch top 20 to have rotation options
                            .map((m: any) => `https://image.tmdb.org/t/p/original${m.backdrop_path}`);
                         
                         if (paths.length > 0) {
                             setBackdrops(paths);
                             loaded = true;
                         }
                    }
                }
            } catch (e) {
                console.warn('Failed to fetch TMDB backdrops', e);
            }
        }
        
        if (!loaded) {
            setBackdrops(FALLBACK_BACKDROPS);
        }
    };

    fetchBackdrops();
  }, []);

  // Daily Background Rotation Logic
  useEffect(() => {
    if (backdrops.length > 0) {
        // Calculate day of the year
        const now = new Date();
        const start = new Date(now.getFullYear(), 0, 0);
        const diff = (now.getTime() - start.getTime()) + ((start.getTimezoneOffset() - now.getTimezoneOffset()) * 60 * 1000);
        const oneDay = 1000 * 60 * 60 * 24;
        const dayOfYear = Math.floor(diff / oneDay);
        
        // Select index based on day of year, ensuring it stays same for 24h
        const index = dayOfYear % backdrops.length;
        setCurrentBackdropIndex(index);
    }
  }, [backdrops]);

  const toggleTheme = () => setIsDark(!isDark);

  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    logout(); 
    setIsAuthenticated(false); 
    setMobileMenuOpen(false);
    setCurrentView(ViewState.USER_CENTER); 
  };

  const renderContent = () => {
    switch (currentView) {
      case ViewState.USER_CENTER: return <UserCenterView />;
      case ViewState.BOT_SETTINGS: return <BotSettingsView />;
      case ViewState.CLOUD_ORGANIZE: return <CloudOrganizeView />;
      case ViewState.EMBY_INTEGRATION: return <EmbyView />;
      case ViewState.STRM_GENERATION: return <StrmView />;
      case ViewState.LOGS: return <LogsView />;
      default: return <UserCenterView />;
    }
  };

  if (isChecking) {
    return <div className="min-h-screen bg-slate-900 flex items-center justify-center text-slate-500">Loading...</div>;
  }

  return (
    <div className="min-h-screen font-sans transition-colors duration-300 relative overflow-x-hidden">
      {/* Global Background Layer */}
      <div className="fixed inset-0 z-0 bg-slate-900">
         {backdrops.length > 0 && (
            <div 
               className="absolute inset-0 bg-cover bg-center bg-no-repeat bg-fixed transition-opacity duration-1000 opacity-100"
               style={{ backgroundImage: `url(${backdrops[currentBackdropIndex]})` }}
            />
         )}
         
         {/* Theme Overlays - HD Clarity */}
         {/* Light Mode: Very subtle white gradient */}
         <div className={`absolute inset-0 transition-all duration-1000 ${isDark ? 'opacity-0' : 'opacity-100 bg-gradient-to-br from-white/80 via-white/40 to-white/10'}`}></div>
         
         {/* Dark Mode: Subtle dark gradient */}
         <div className={`absolute inset-0 transition-all duration-1000 ${isDark ? 'opacity-100 bg-gradient-to-br from-slate-950/80 via-slate-900/60 to-slate-900/20' : 'opacity-0'}`}></div>
      </div>

      <div className="relative z-10 h-full">
        {!isAuthenticated ? (
          <LoginView onLoginSuccess={handleLoginSuccess} />
        ) : (
          <div className="min-h-screen text-slate-900 dark:text-slate-100 flex flex-col md:flex-row">
            
            {/* Mobile Menu Trigger (Bottom Left FAB) */}
            <button 
              onClick={() => setMobileMenuOpen(true)}
              className="md:hidden fixed bottom-6 left-6 z-50 p-3 bg-brand-600/90 backdrop-blur-md text-white rounded-full shadow-lg shadow-brand-600/30 active:scale-95 transition-all border border-white/20"
              title="打开菜单"
            >
              <Menu size={20} />
            </button>

            {/* Mobile Sidebar Drawer */}
            {mobileMenuOpen && (
              <>
                {/* Backdrop */}
                <div 
                  className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] md:hidden animate-in fade-in duration-300"
                  onClick={() => setMobileMenuOpen(false)}
                ></div>
                
                {/* Drawer - Reduced width for better mobile proportion */}
                <div className="fixed inset-y-0 left-0 w-64 bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl z-[70] md:hidden shadow-2xl animate-in slide-in-from-left duration-300 flex flex-col border-r border-white/20 dark:border-slate-700/50">
                   <div className="h-20 flex items-center justify-between px-6 border-b border-slate-200/50 dark:border-slate-700/50">
                      <Logo />
                      <button onClick={() => setMobileMenuOpen(false)} className="p-2 text-slate-500 dark:text-slate-400">
                        <X size={24} />
                      </button>
                   </div>
                   
                   <nav className="flex-1 p-4 space-y-2 overflow-y-auto custom-scrollbar">
                      <div className="text-[10px] font-bold text-slate-400 dark:text-slate-500 uppercase tracking-widest mb-4 px-2">功能菜单</div>
                      {[
                        { id: ViewState.USER_CENTER, label: '用户中心' },
                        { id: ViewState.BOT_SETTINGS, label: '机器人设置' },
                        { id: ViewState.CLOUD_ORGANIZE, label: '网盘整理' },
                        { id: ViewState.EMBY_INTEGRATION, label: 'Emby 联动' },
                        { id: ViewState.STRM_GENERATION, label: 'STRM 生成' },
                        { id: ViewState.LOGS, label: '运行日志' },
                      ].map(item => (
                         <button 
                            key={item.id}
                            onClick={() => { setCurrentView(item.id as ViewState); setMobileMenuOpen(false); }} 
                            className={`block w-full text-left px-4 py-3 rounded-xl font-medium transition-colors ${
                              currentView === item.id 
                                ? 'bg-brand-50 text-brand-600 dark:bg-brand-900/30 dark:text-brand-400' 
                                : 'text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'
                            }`}
                         >
                            {item.label}
                         </button>
                      ))}
                   </nav>

                   <div className="p-4 border-t border-slate-200/50 dark:border-slate-700/50 grid grid-cols-2 gap-3">
                       <button onClick={toggleTheme} className="flex items-center justify-center gap-2 py-3 bg-slate-100 dark:bg-slate-800 rounded-xl text-slate-600 dark:text-slate-300 font-medium text-xs">
                          {isDark ? <Sun size={16}/> : <Moon size={16}/>}
                          {isDark ? '亮色' : '暗色'}
                       </button>
                       <button onClick={handleLogout} className="flex items-center justify-center gap-2 py-3 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded-xl font-medium text-xs">
                          <LogOut size={16}/>
                          退出
                       </button>
                   </div>
                </div>
              </>
            )}

            <Sidebar 
              currentView={currentView} 
              onChangeView={setCurrentView} 
              isDark={isDark}
              toggleTheme={toggleTheme}
              onLogout={handleLogout}
              collapsed={sidebarCollapsed}
              toggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
            />

            {/* Main Content Area */}
            {/* Added extra bottom padding (pb-32) for mobile to allow scrolling past FAB */}
            <main className={`flex-1 min-h-screen transition-all duration-300 w-full ${sidebarCollapsed ? 'md:pl-20' : 'md:pl-64'}`}>
              <div className="w-full max-w-[1600px] mx-auto px-4 sm:px-6 lg:px-8 py-8 pb-32">
                {renderContent()}
              </div>
            </main>
          </div>
        )}
      </div>
    </div>
  );
};

export default App;