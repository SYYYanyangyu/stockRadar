import { useState, useEffect } from 'react';
import { api } from '../api';
import type { QuietBullItem } from '../types';
import { cn } from '@/lib/utils';
import { Pagination } from '@/components/shared/Pagination';

export default function QuietBullsPage({ onLoaded }: { onLoaded: () => void }) {
  const [items, setItems] = useState<QuietBullItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [minScore, setMinScore] = useState(50);
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  useEffect(() => {
    setLoading(true);
    api.quietBulls(page, pageSize, minScore)
      .then(r => { setItems(r.items); setTotal(r.total); })
      .finally(() => { setLoading(false); onLoaded(); });
  }, [page, minScore]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-bold">低调牛股</h2>
        <p className="text-xs text-zinc-400">五维十六子维度：趋势+低调+量价+筹码+形态，远离喧嚣偷偷涨</p>
        <div className="flex items-center gap-2 ml-auto">
          <label className="text-xs text-zinc-500">最低分</label>
          {[30, 50, 60, 70].map(s => (
            <button key={s} onClick={() => setMinScore(s)}
              className={cn("px-2 py-1 rounded text-xs", minScore === s ? "bg-red-100 text-red-700" : "bg-zinc-100 text-zinc-600")}>{s}</button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-10">
          <div className="w-5 h-5 rounded-full border-2 border-red-200 border-t-red-600 animate-spin" />
        </div>
      ) : total === 0 ? (
        <div className="text-center py-10 text-zinc-400">
          <p className="text-lg mb-1">暂无符合条件的低调牛股</p>
          <p className="text-xs">降低最低分数要求或等待更多数据</p>
        </div>
      ) : (
        <>
          <div className="text-xs text-zinc-500">共 {total} 只，按综合评分降序</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {items.map((it, i) => (
              <div key={i} className="rounded-lg border border-zinc-200 p-4 hover:border-zinc-300 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <span className="font-mono text-xs text-zinc-500 mr-2">{it.code}</span>
                    <span className="font-bold text-sm">{it.name || '-'}</span>
                  </div>
                  <span className={cn(
                    "px-2 py-0.5 rounded text-xs font-bold",
                    (it.total_score ?? 0) >= 70 ? "bg-red-600 text-white" :
                    (it.total_score ?? 0) >= 50 ? "bg-orange-100 text-orange-700" :
                    "bg-yellow-100 text-yellow-700"
                  )}>{(it.total_score ?? 0).toFixed(0)}分</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-zinc-500 mb-2">
                  <span>连阳 {it.streak_days ?? '-'}天</span>
                  <span>涨幅 {(it.total_pct ?? 0) > 0 ? '+' : ''}{(it.total_pct ?? 0).toFixed(1)}%</span>
                  <span>最新 {it.price != null ? it.price.toFixed(2) : '-'}</span>
                </div>
                {it.scores && (
                  <div className="space-y-1">
                    {[
                      { label: '趋势', v: it.scores.trend ?? 0, hint: '连阳·涨幅·胜率·多头排列' },
                      { label: '低调', v: it.scores.quiet ?? 0, hint: '避热榜·避涨跌停' },
                      { label: '量价', v: it.scores.volume ?? 0, hint: '量稳·缩量上涨·MA上方' },
                      { label: '筹码', v: it.scores.institution ?? 0, hint: '融资·低振幅·小回撤' },
                      { label: '形态', v: it.scores.pattern ?? 0, hint: '小阳线·窄震·连阳' },
                    ].map(d => (
                      <div key={d.label} className="flex items-center gap-2">
                        <span className="w-6 text-xs text-zinc-400">{d.label}</span>
                        <div className="flex-1 h-1.5 bg-zinc-100 rounded-full overflow-hidden">
                          <div className={cn("h-full rounded-full",
                            d.v >= 15 ? "bg-red-500" : d.v >= 10 ? "bg-orange-400" : "bg-yellow-400")}
                            style={{ width: `${(d.v / 20) * 100}%` }} />
                        </div>
                        <span className="text-xs text-zinc-400 w-4 text-right">{d.v}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
          <Pagination page={page} pageSize={pageSize} total={total} onChange={setPage} />
        </>
      )}
    </div>
  );
}
