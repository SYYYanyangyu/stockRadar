import { useState } from 'react';
import HomePage from './pages/HomePage';
import DragonTigerPage from './pages/DragonTigerPage';
import SectorPage from './pages/SectorPage';
import VolumeAnomalyPage from './pages/VolumeAnomalyPage';
import QuietBullsPage from './pages/QuietBullsPage';
import MarginPage from './pages/MarginPage';
import { cn } from '@/lib/utils';
import { Flame, LayoutDashboard, PieChart, BarChart3, TrendingUp, Banknote, Moon, Sun } from 'lucide-react';
import { useDarkMode } from '@/hooks/useDarkMode';

type Tab = 'home' | 'dragon' | 'sector' | 'vol' | 'bulls' | 'margin';

const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'home', label: '首页', icon: <LayoutDashboard className="h-4 w-4" /> },
  { key: 'dragon', label: '龙虎榜', icon: <Flame className="h-4 w-4" /> },
  { key: 'sector', label: '板块', icon: <PieChart className="h-4 w-4" /> },
  { key: 'vol', label: '量比异动', icon: <BarChart3 className="h-4 w-4" /> },
  { key: 'bulls', label: '低调牛股', icon: <TrendingUp className="h-4 w-4" /> },
  { key: 'margin', label: '两融', icon: <Banknote className="h-4 w-4" /> },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('home');
  const [loading, setLoading] = useState(false);
  const { isDark, toggle } = useDarkMode();

  const switchTab = (t: Tab) => { setLoading(true); setTab(t); };
  const onLoaded = () => setLoading(false);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950">
      {/* Header — desktop */}
      <header className="sticky top-0 z-10 bg-white dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
        <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-13">
          <h1 className="text-lg font-bold tracking-tight">
            Corr<span className="text-red-600 dark:text-red-400">Board</span>
            <span className="text-xs text-zinc-400 dark:text-zinc-500 font-normal ml-2">联动板</span>
          </h1>
          <div className="flex items-center gap-2">
            <button
              onClick={toggle}
              className="p-1.5 rounded-md text-zinc-500 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
              title={isDark ? '切换亮色模式' : '切换暗色模式'}
            >
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </button>
            <nav className="hidden sm:flex gap-0.5">
              {tabs.map(t => (
                <button key={t.key} onClick={() => switchTab(t.key)}
                  className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                    tab === t.key
                      ? "bg-red-50 dark:bg-red-950 text-red-600 dark:text-red-400"
                      : "text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
                  )}>
                  {t.icon}
                  {t.label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-6xl mx-auto px-4 py-4 pb-20 sm:pb-4">
        {loading && (
          <div className="flex justify-center py-6">
            <div className="w-5 h-5 rounded-full border-2 border-red-200 border-t-red-600 animate-spin" />
          </div>
        )}
        <div className={cn("transition-opacity duration-150", loading ? "opacity-40" : "opacity-100")}>
          {tab === 'home' && <HomePage onLoaded={onLoaded} />}
          {tab === 'dragon' && <DragonTigerPage onLoaded={onLoaded} />}
          {tab === 'sector' && <SectorPage onLoaded={onLoaded} />}
          {tab === 'vol' && <VolumeAnomalyPage onLoaded={onLoaded} />}
          {tab === 'bulls' && <QuietBullsPage onLoaded={onLoaded} />}
          {tab === 'margin' && <MarginPage onLoaded={onLoaded} />}
        </div>
      </main>

      {/* Bottom nav — mobile */}
      <nav className="sm:hidden fixed bottom-0 inset-x-0 z-10 bg-white dark:bg-zinc-900 border-t border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center justify-around h-14">
          {tabs.map(t => (
            <button key={t.key} onClick={() => switchTab(t.key)}
              className={cn(
                "flex flex-col items-center gap-0.5 py-1 px-4 text-xs font-medium transition-colors",
                tab === t.key
                  ? "text-red-600 dark:text-red-400"
                  : "text-zinc-400 dark:text-zinc-500"
              )}>
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>
      </nav>
    </div>
  );
}
