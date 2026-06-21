import { useState, useEffect } from 'react';
import { api } from '@/api';
import type { UsCorrelationResponse, UsConceptCard } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/Sheet';
import { cn } from '@/lib/utils';
import KLineChart from '@/components/trends/KLineChart';
import { LineChart, Line, ResponsiveContainer } from 'recharts';
import { TrendingUp } from 'lucide-react';

const INDEX_NAMES: Record<string, string> = {
  '.IXIC': '纳斯达克',
  '.INX': '标普500',
  '.DJI': '道琼斯',
};

const INDEX_ICON: Record<string, string> = {
  '.IXIC': '📱',
  '.INX': '📊',
  '.DJI': '🏭',
};

function ScoreBar({ score, label }: { score: number | null; label: string }) {
  const pct = Math.max(0, Math.min(1, (score ?? 0)));
  const color = pct >= 0.5 ? 'bg-blue-500' : pct >= 0.3 ? 'bg-amber-500' : 'bg-zinc-300';
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-muted-foreground w-12">{label}</span>
      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${pct * 100}%` }} />
      </div>
      <span className="text-xs font-mono font-bold w-14 text-right">{score != null ? score.toFixed(3) : '-'}</span>
    </div>
  );
}

export default function UsCorrelationModule() {
  const [data, setData] = useState<UsCorrelationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeIndex, setActiveIndex] = useState('all');
  const [corrPeriod, setCorrPeriod] = useState<'10d' | '15d' | '20d'>('10d');
  const [expandedConcept, setExpandedConcept] = useState<string | null>(null);
  const [klineCode, setKlineCode] = useState<string | null>(null);
  const [klineName, setKlineName] = useState('');

  useEffect(() => {
    setLoading(true);
    api.usCorrelation('all', 50, 'concept', corrPeriod)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [corrPeriod]);

  const concepts = data?.concepts?.filter(c =>
    activeIndex === 'all' ? true : c.us_index === activeIndex
  ) ?? [];

  if (loading) {
    return <Skeleton className="h-[400px] w-full" />;
  }

  if (!data) {
    return <EmptyState text="暂无概念联动数据" />;
  }

  return (
    <>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-blue-500" />
            美股→A股 概念联动
            <span className="text-xs font-normal text-muted-foreground ml-1">产业链相关性排名</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* ── Index Tabs ── */}
          <div className="flex gap-2 mb-4">
            {['all', '.IXIC', '.INX', '.DJI'].map(idx => (
              <button
                key={idx}
                onClick={() => setActiveIndex(idx)}
                className={cn(
                  'px-3 py-1.5 text-xs rounded-md font-medium transition-colors',
                  activeIndex === idx
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground hover:text-foreground',
                )}
              >
                {idx === 'all' ? '全部指数' : `${INDEX_ICON[idx] || ''} ${INDEX_NAMES[idx] || idx}`}
              </button>
            ))}
          </div>

          {/* ── Index Mini Cards ── */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            {data.indices.map(idx => {
              const sparkData = idx.recent_5d.map((v, i) => ({ i, v }));
              const isUp = (idx.change_pct ?? 0) >= 0;
              return (
                <div
                  key={idx.symbol}
                  className={cn(
                    'rounded-lg border p-3 cursor-pointer transition-colors',
                    activeIndex === idx.symbol ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/30',
                  )}
                  onClick={() => setActiveIndex(activeIndex === idx.symbol ? 'all' : idx.symbol)}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium">{INDEX_NAMES[idx.symbol] || idx.symbol}</span>
                    <span className={cn('text-xs font-bold', isUp ? 'text-red-600' : 'text-green-600')}>
                      {isUp ? '+' : ''}{idx.change_pct?.toFixed(2) ?? '-'}%
                    </span>
                  </div>
                  <div className="text-lg font-bold">{idx.close?.toLocaleString() ?? '-'}</div>
                  {sparkData.length >= 2 && (
                    <div className="h-8 mt-1">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={sparkData}>
                          <Line type="monotone" dataKey="v" stroke={isUp ? '#ef4444' : '#22c55e'} strokeWidth={1.5} dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* ── Period Toggle ── */}
          <div className="flex items-center gap-1 mb-4">
            <span className="text-xs text-muted-foreground mr-2">相关系数周期:</span>
            {['10d', '15d', '20d'].map(p => (
              <button
                key={p}
                onClick={() => setCorrPeriod(p as typeof corrPeriod)}
                className={cn(
                  'px-2 py-1 text-xs rounded font-mono transition-colors',
                  corrPeriod === p ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground',
                )}
              >
                {p.replace('d', '日')}
              </button>
            ))}
          </div>

          {/* ── Concept Card Grid ── */}
          {concepts.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground text-xs">
              暂无概念联动数据，请等待每日收盘后计算
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {concepts.map(concept => (
                <ConceptCard
                  key={`${concept.us_index}-${concept.name}`}
                  concept={concept}
                  isExpanded={expandedConcept === `${concept.us_index}-${concept.name}`}
                  onToggle={() => setExpandedConcept(
                    expandedConcept === `${concept.us_index}-${concept.name}`
                      ? null
                      : `${concept.us_index}-${concept.name}`
                  )}
                  onStockClick={(code, name) => { setKlineCode(code); setKlineName(name); }}
                  corrPeriod={corrPeriod}
                />
              ))}
            </div>
          )}

          {/* ── Legend ── */}
          <div className="flex gap-4 mt-4 text-xs text-muted-foreground">
            <span><span className="inline-block w-3 h-3 rounded bg-blue-500/20 align-middle mr-1" />强联动(≥0.5)</span>
            <span><span className="inline-block w-3 h-3 rounded bg-amber-500/20 align-middle mr-1" />中等(≥0.3)</span>
            <span>一致性高 = 概念内个股联动方向统一</span>
          </div>
        </CardContent>
      </Card>

      {/* ── K-line Side Panel ── */}
      <Sheet open={!!klineCode} onOpenChange={(open) => { if (!open) setKlineCode(null); }}>
        <SheetContent side="right" className="w-[520px] max-w-[90vw] p-0">
          <SheetHeader><SheetTitle>K线图 · {klineName}</SheetTitle></SheetHeader>
          <div className="px-4 pb-4">
            {klineCode && <KLineChart code={klineCode} name={klineName} days={60} />}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}

function ConceptCard({
  concept, isExpanded, onToggle, onStockClick, corrPeriod,
}: {
  concept: UsConceptCard;
  isExpanded: boolean;
  onToggle: () => void;
  onStockClick: (code: string, name: string) => void;
  corrPeriod: string;
}) {
  const score = concept.composite_score ?? 0;
  const scoreColor = score >= 0.5 ? 'text-blue-600' : score >= 0.3 ? 'text-amber-600' : 'text-zinc-500';
  const idxAbbrev = INDEX_NAMES[concept.us_index]?.slice(0, 2) || concept.us_index;

  return (
    <div className={cn('rounded-lg border transition-colors', isExpanded ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/30')}>
      <div className="p-4 cursor-pointer" onClick={onToggle}>
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-lg">{concept.icon}</span>
            <span className="font-bold text-sm">{concept.name}</span>
            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{idxAbbrev}</span>
          </div>
          <span className={cn('text-xl font-bold font-mono', scoreColor)}>
            {score.toFixed(2)}
          </span>
        </div>

        {/* Score bar */}
        <ScoreBar score={score} label="联动评分" />

        {/* Meta row */}
        <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
          <span>{concept.stock_count}/{concept.total_constituents} 只有效数据</span>
          <span>均值 r={concept.avg_corr?.toFixed(3) ?? '-'}</span>
          <span>β={concept.avg_beta?.toFixed(2) ?? '-'}</span>
          <span>一致性 {concept.consistency != null ? (concept.consistency * 100).toFixed(0) + '%' : '-'}</span>
        </div>

        {/* Top 3 chip */}
        {concept.top_stocks.length > 0 && (
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {concept.top_stocks.slice(0, 3).map(s => (
              <span key={s.code} className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                {s.name}
                <span className="text-muted-foreground ml-1">β={s.beta?.toFixed(1)} r={s.corr?.toFixed(2)}</span>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Expanded: full constituent table */}
      {isExpanded && concept.top_stocks.length > 0 && (
        <div className="border-t border-border px-4 pb-3">
          <table className="w-full text-xs mt-2">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="text-left py-1.5 font-medium">股票</th>
                <th className="text-right py-1.5 font-medium">成交额</th>
                <th className="text-right py-1.5 font-medium">传导β</th>
                <th className="text-right py-1.5 font-medium">隔夜预期差</th>
                <th className="text-right py-1.5 font-medium">A股涨跌</th>
              </tr>
            </thead>
            <tbody>
              {concept.top_stocks.map(s => (
                <tr
                  key={s.code}
                  className="border-b border-border/30 hover:bg-muted/50 cursor-pointer transition-colors"
                  onClick={(e) => { e.stopPropagation(); onStockClick(s.code, s.name); }}
                >
                  <td className="py-1.5">
                    <span className="font-medium">{s.name}</span>
                    <span className="text-muted-foreground ml-1 font-mono">{s.code}</span>
                  </td>
                  <td className="py-1.5 text-right text-muted-foreground text-xs">
                    {s.amount != null ? `${s.amount}亿` : '-'}
                  </td>
                  <td className={cn('py-1.5 text-right font-mono font-bold', (s.beta ?? 0) >= 1.5 ? 'text-blue-600' : (s.beta ?? 0) >= 0.8 ? 'text-amber-600' : '')}>
                    {s.beta?.toFixed(2) ?? '-'}
                  </td>
                  <td className={cn('py-1.5 text-right font-mono',
                    (s.gap ?? 0) > 0 ? 'text-red-600' : (s.gap ?? 0) < 0 ? 'text-green-600' : '',
                  )}>
                    {s.gap != null ? `${s.gap > 0 ? '+' : ''}${s.gap.toFixed(2)}%` : '-'}
                  </td>
                  <td className={cn('py-1.5 text-right font-mono',
                    (s.a_chg ?? 0) > 0 ? 'text-red-600' : (s.a_chg ?? 0) < 0 ? 'text-green-600' : '',
                  )}>
                    {s.a_chg != null ? `${s.a_chg >= 0 ? '+' : ''}${s.a_chg.toFixed(2)}%` : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
