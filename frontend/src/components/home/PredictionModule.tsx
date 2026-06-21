import { useState, useEffect } from 'react';
import { api } from '@/api';
import type { PredictionResponse } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus, Zap, ShieldAlert } from 'lucide-react';

const DIRECTION_MAP = {
  bull: { icon: TrendingUp, color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-950/30', border: 'border-red-200 dark:border-red-700', label: '看多' },
  bear: { icon: TrendingDown, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-950/30', border: 'border-green-200 dark:border-green-700', label: '看空' },
  neutral: { icon: Minus, color: 'text-zinc-400', bg: 'bg-zinc-50 dark:bg-zinc-900', border: 'border-zinc-200 dark:border-zinc-700', label: '中性' },
};

export default function PredictionModule() {
  const [data, setData] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.prediction()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <Skeleton className="h-[200px] w-full" />;
  }

  if (!data) {
    return null;
  }

  const hasExtreme = data.predictions.some(p => p.extreme_alert);
  const bullCount = data.predictions.filter(p => p.direction === 'bull').length;
  const bearCount = data.predictions.filter(p => p.direction === 'bear').length;

  return (
    <Card className={cn(
      'border-2',
      hasExtreme ? 'border-red-300 dark:border-red-700' : 'border-blue-200 dark:border-blue-700',
    )}>
      <CardHeader className="pb-1 sm:pb-2">
        <CardTitle className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
          <Zap className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-amber-500" />
          <span className="text-sm sm:text-base">明日A股概念预测</span>
          <span className="text-[10px] sm:text-xs font-normal text-muted-foreground">
            {data.us_market_date}
          </span>
          {hasExtreme && (
            <span className="text-[10px] sm:text-xs bg-red-100 dark:bg-red-900 text-red-600 dark:text-red-400 px-1.5 py-0.5 rounded-full font-bold animate-pulse">
              极端信号
            </span>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* ── Indicators Bar — desktop 5-col grid, mobile 3-col ── */}
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-3 mb-4">
          {data.indices.map(idx => {
            const isUp = (idx.change_pct ?? 0) >= 0;
            return (
              <div key={idx.abbr} className="text-center">
                <div className="text-[10px] sm:text-xs text-muted-foreground truncate">{idx.name}</div>
                <div className={cn('text-sm sm:text-lg font-black font-mono', isUp ? 'text-red-600' : 'text-green-600')}>
                  {idx.change_pct != null ? `${isUp ? '+' : ''}${idx.change_pct.toFixed(2)}%` : '-'}
                </div>
                <div className="text-[10px] sm:text-xs text-muted-foreground font-mono hidden sm:block">
                  {idx.close?.toLocaleString() ?? '-'}
                </div>
              </div>
            );
          })}
          {(data.cross_indicators || []).slice(0, 2).map(ci => {
            const isUp = (ci.change_pct ?? 0) >= 0;
            const isGold = ci.abbr === 'GOLD';
            return (
              <div key={ci.abbr} className="text-center">
                <div className="text-[10px] sm:text-xs text-muted-foreground truncate">{ci.name}</div>
                <div className={cn('text-sm sm:text-lg font-black font-mono', isUp ? 'text-red-600' : 'text-green-600')}>
                  {ci.change_pct != null ? `${isUp ? '+' : ''}${ci.change_pct.toFixed(2)}%` : '-'}
                </div>
                <div className="text-[10px] sm:text-xs text-muted-foreground font-mono hidden sm:block">
                  {isGold ? (ci.value != null ? `¥${ci.value.toFixed(0)}/g` : '-') :
                   ci.value != null ? ci.value.toFixed(0) : '-'}
                </div>
              </div>
            );
          })}
        </div>

        {/* ── Market Bias Summary ── */}
        <div className="flex items-center justify-between mb-3 pb-3 border-b border-border">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">市场倾向:</span>
            {bullCount > bearCount ? (
              <span className="text-sm font-bold text-red-600">偏多 ({bullCount}概念看涨)</span>
            ) : bearCount > bullCount ? (
              <span className="text-sm font-bold text-green-600">偏空 ({bearCount}概念看跌)</span>
            ) : (
              <span className="text-sm font-bold text-zinc-500">中性</span>
            )}
          </div>
          <span className="text-xs text-muted-foreground">{data.disclaimer}</span>
        </div>

        {/* ── Prediction Cards — 2-col desktop, 1-col mobile, show fewer on mobile ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {data.predictions.slice(0, data.predictions.length).map((p, i) => {
            const isMobileHidden = i >= 4;
            const dir = DIRECTION_MAP[p.direction];
            const Icon = dir.icon;
            const bestIdx = p.best_signal;

            return (
              <div
                key={p.concept}
                className={cn(
                  'rounded-lg border p-2 sm:p-3',
                  isMobileHidden && 'hidden sm:block',
                  p.extreme_alert ? 'border-red-300 dark:border-red-700 bg-red-50/30 dark:bg-red-950/10' : dir.border,
                )}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-1 sm:mb-1.5">
                  <div className="flex items-center gap-1 sm:gap-1.5">
                    <span className="text-base sm:text-lg">{p.icon}</span>
                    <span className="text-[11px] sm:text-xs font-bold">{p.concept}</span>
                  </div>
                  <div className={cn('flex items-center gap-0.5 text-[11px] sm:text-xs font-bold', dir.color)}>
                    <Icon className="h-2.5 w-2.5 sm:h-3 sm:w-3" />
                    {p.avg_expected >= 0 ? '+' : ''}{p.avg_expected.toFixed(2)}%
                  </div>
                </div>

                {/* Best index signal */}
                <div className="text-[10px] sm:text-xs text-muted-foreground mb-1 sm:mb-1.5">
                  {bestIdx.index_abbr} {bestIdx.us_chg >= 0 ? '+' : ''}{bestIdx.us_chg}%
                  {' → '}A股预期 {bestIdx.expected_a_chg >= 0 ? '+' : ''}{bestIdx.expected_a_chg}%
                </div>

                {/* Confidence bar */}
                <div className="flex items-center gap-1.5 sm:gap-2">
                  <span className="text-[10px] sm:text-xs text-muted-foreground w-8 sm:w-10 shrink-0">置信</span>
                  <div className="flex-1 h-1 sm:h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className={cn(
                        'h-full rounded-full transition-all',
                        bestIdx.confidence >= 80 ? 'bg-emerald-500' :
                        bestIdx.confidence >= 60 ? 'bg-blue-500' :
                        bestIdx.confidence >= 40 ? 'bg-amber-500' : 'bg-zinc-300',
                      )}
                      style={{ width: `${bestIdx.confidence}%` }}
                    />
                  </div>
                  <span className="text-[10px] sm:text-xs font-mono font-bold w-7 sm:w-8 text-right">{bestIdx.confidence}%</span>
                </div>

                {/* Multi-index consensus */}
                <div className="flex items-start gap-1 mt-1.5">
                  <span className="text-xs text-muted-foreground shrink-0 mt-0.5">共识</span>
                  <div className="flex flex-wrap gap-0.5 min-w-0 flex-1">
                    {p.signals.map(s => (
                      <span
                        key={s.index_abbr}
                        className={cn(
                          'text-[10px] sm:text-xs px-1 py-0.5 rounded font-mono whitespace-nowrap',
                          s.us_chg >= 0 ? 'bg-red-100 dark:bg-red-900/50 text-red-600' : 'bg-green-100 dark:bg-green-900/50 text-green-600',
                        )}
                      >
                        {s.index_abbr}:{s.us_chg >= 0 ? '+' : ''}{s.us_chg}%
                      </span>
                    ))}
                    {(p.cross_signals || []).map(s => (
                      <span
                        key={s.index_abbr}
                        className={cn(
                          'text-[10px] sm:text-xs px-1 py-0.5 rounded font-mono whitespace-nowrap border border-dashed',
                          s.us_chg >= 0 ? 'bg-amber-100 dark:bg-amber-900/50 text-amber-700 border-amber-300' : 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 border-blue-300',
                        )}
                      >
                        {s.index_abbr}:{s.us_chg >= 0 ? '+' : ''}{s.us_chg}%
                      </span>
                    ))}
                  </div>
                  <span className="text-xs font-bold shrink-0 ml-auto">{p.consensus}%</span>
                </div>

                {/* Extreme alert badge */}
                {p.extreme_alert && p.extreme_alert !== '' && (
                  <div className="flex items-center gap-1 mt-1.5 text-xs text-red-600 dark:text-red-400 font-bold">
                    <ShieldAlert className="h-3 w-3" />
                    极端{p.extreme_alert.includes('bull') ? '上涨' : '下跌'}信号 · 历史胜率{p.best_signal.up_winrate}%
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
