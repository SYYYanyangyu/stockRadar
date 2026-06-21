import { useState, useEffect, useMemo } from 'react';
import { api } from '../api';
import type { ZtAnalysisResponse, MarginSummary, UsCorrelationResponse } from '../types';
import { StatCard } from '@/components/shared/StatCard';
import { LoadingSkeleton } from '@/components/shared/LoadingSkeleton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import KLineChart from '@/components/trends/KLineChart';
import MarginChart from '@/components/trends/MarginChart';
import UsCorrelationModule from '@/components/home/UsCorrelationModule';
import BacktestModule from '@/components/home/BacktestModule';
import PredictionModule from '@/components/home/PredictionModule';
import { cn } from '@/lib/utils';
import { Flame, Banknote, ShieldCheck, Bomb, Clock, Layers, Globe } from 'lucide-react';

const GRADE_COLORS: Record<string, string> = {
  '强势封板': 'bg-emerald-100 dark:bg-emerald-900 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700',
  '一般封板': 'bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700',
  '烂板': 'bg-red-100 dark:bg-red-900 text-red-700 dark:text-red-300 border-red-300 dark:border-red-700',
  '弱': 'bg-zinc-100 dark:bg-zinc-800 text-zinc-500 border-zinc-200 dark:border-zinc-700',
};

export default function HomePage({ onLoaded }: { onLoaded: () => void }) {
  const [ztAnalysis, setZtAnalysis] = useState<ZtAnalysisResponse | null>(null);
  const [marginSummary, setMarginSummary] = useState<MarginSummary | null>(null);
  const [usCorr, setUsCorr] = useState<UsCorrelationResponse | null>(null);
  const [klineCode, setKlineCode] = useState<string | null>(null);
  const [klineName, setKlineName] = useState('');
  const [expandedTiers, setExpandedTiers] = useState<Record<number, boolean>>({});
  const [detailSheet, setDetailSheet] = useState<{ title: string; stocks: { code: string; name: string; detail?: string }[] } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.ztAnalysis(),
      api.marginSummary().catch(() => null),
      api.usCorrelation().catch(() => null),
    ]).then(([zt, margin, usc]) => {
      setZtAnalysis(zt);
      setMarginSummary(margin);
      setUsCorr(usc);
    }).catch(() => {}).finally(() => {
      setLoading(false);
      onLoaded();
    });
  }, []);

  const items = ztAnalysis?.items || [];
  const industries = ztAnalysis?.industries || [];
  const brokenBoards = ztAnalysis?.broken_boards || [];
  const maxStreak = ztAnalysis?.max_streak || 0;

  // 涨停情绪评分 (0-100)
  const sentiment = useMemo(() => {
    if (!items.length) return null;
    const total = items.length;
    const strongCount = items.filter(s => s.seal_quality.grade === '强势封板').length;
    const brokenCount = brokenBoards.length;
    const streak3plus = items.filter(s => (s.streak || 0) >= 3).length;
    const avgBreak = items.reduce((s, i) => s + (i.break_count || 0), 0) / total;
    // 强势封板率、炸板率、连板高度综合评分
    let score = 50;
    score += (strongCount / total) * 25; // 强势封板越多越好
    score -= (brokenCount / total) * 20;  // 炸板多不好
    score += streak3plus * 2;              // 连板高度加分
    score -= Math.max(0, avgBreak - 2) * 5; // 平均炸板高扣分
    score = Math.max(0, Math.min(100, Math.round(score)));
    const level = score >= 70 ? '强势' : score >= 50 ? '一般' : score >= 30 ? '偏弱' : '冰点';
    const levelColor = score >= 70 ? 'text-emerald-600' : score >= 50 ? 'text-amber-600' : score >= 30 ? 'text-orange-600' : 'text-red-600';
    return { score, level, levelColor, strongPct: ((strongCount / total) * 100).toFixed(0), brokenPct: ((brokenCount / total) * 100).toFixed(0) };
  }, [items, brokenBoards]);

  // 按连板数分组
  const streakGroups = useMemo(() => {
    const groups: Record<number, typeof items> = {};
    for (const s of items) {
      const st = s.streak || 1;
      (groups[st] ||= []).push(s);
    }
    return groups;
  }, [items]);

  // 封板成功率 = 零炸板数/总数
  const zeroBreakCount = items.filter(s => (s.break_count || 0) === 0).length;

  if (loading) {
    return <LoadingSkeleton variant="stats" />;
  }

  return (
    <div className="space-y-4 animate-in fade-in">
      {/* ===== 情绪仪表盘 ===== */}
      {sentiment && (
        <Card className="bg-gradient-to-r from-zinc-50 to-zinc-100 dark:from-zinc-900 dark:to-zinc-800 border-zinc-200 dark:border-zinc-700">
          <CardContent className="p-4">
            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-3">
                <div className={cn(
                  "w-14 h-14 rounded-full flex items-center justify-center text-2xl font-black ring-4",
                  sentiment.score >= 70 ? "bg-emerald-100 dark:bg-emerald-900 text-emerald-600 ring-emerald-300 dark:ring-emerald-700" :
                  sentiment.score >= 50 ? "bg-amber-100 dark:bg-amber-900 text-amber-600 ring-amber-300 dark:ring-amber-700" :
                  sentiment.score >= 30 ? "bg-orange-100 dark:bg-orange-900 text-orange-600 ring-orange-300 dark:ring-orange-700" :
                  "bg-red-100 dark:bg-red-900 text-red-600 ring-red-300 dark:ring-red-700"
                )}>
                  {sentiment.score}
                </div>
                <div>
                  <div className={cn("text-lg font-bold", sentiment.levelColor)}>
                    {sentiment.level}
                    <span className="text-xs font-normal text-zinc-400 ml-1">涨停情绪</span>
                  </div>
                  <div className="text-xs text-zinc-400 mt-0.5 space-x-2">
                    <span>强势{sentiment.strongPct}%</span>
                    <span>·</span>
                    <span>炸板率{sentiment.brokenPct}%</span>
                    <span>·</span>
                    <span>最高{maxStreak}连板</span>
                  </div>
                </div>
              </div>
              <div className="flex-1" />
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-x-5 gap-y-2 text-center">
                <button onClick={() => setDetailSheet({ title: '零炸板 · 确定性最高', stocks: items.filter(s => (s.break_count || 0) === 0).map(s => ({ code: s.code, name: s.name || '', detail: `${s.seal_quality.time_label} · ${s.streak || 0}板` })) })} className="group">
                  <div className="text-lg font-black text-emerald-600 group-hover:scale-110 transition-transform">{zeroBreakCount}</div>
                  <div className="text-xs text-zinc-400 group-hover:text-zinc-600">零炸板</div>
                </button>
                <button onClick={() => setDetailSheet({ title: '秒板 · 09:35前封板', stocks: items.filter(s => s.seal_quality.time_label === '秒板').map(s => ({ code: s.code, name: s.name || '', detail: `${s.seal_quality.break_label} · ${s.streak || 0}板` })) })} className="group">
                  <div className="text-lg font-black text-blue-600 group-hover:scale-110 transition-transform">{items.filter(s => s.seal_quality.time_label === '秒板').length}</div>
                  <div className="text-xs text-zinc-400 group-hover:text-zinc-600">秒板</div>
                </button>
                <button onClick={() => setDetailSheet({ title: '首板 · 低位首板', stocks: (streakGroups[1] || []).map(s => ({ code: s.code, name: s.name || '', detail: `${s.seal_quality.time_label} · ${s.seal_quality.grade}` })) })} className="group">
                  <div className="text-lg font-black text-amber-600 group-hover:scale-110 transition-transform">{streakGroups[1]?.length || 0}</div>
                  <div className="text-xs text-zinc-400 group-hover:text-zinc-600">首板</div>
                </button>
                <button onClick={() => setDetailSheet({ title: '3连板+ · 高位标', stocks: items.filter(s => (s.streak || 0) >= 3).map(s => ({ code: s.code, name: s.name || '', detail: `${s.streak || 0}板 · ${s.seal_quality.grade}` })) })} className="group">
                  <div className="text-lg font-black text-violet-600 group-hover:scale-110 transition-transform">{streakGroups[3]?.length || 0}</div>
                  <div className="text-xs text-zinc-400 group-hover:text-zinc-600">3连板+</div>
                </button>
                <button onClick={() => setDetailSheet({ title: '总炸板次 · ${brokenBoards.reduce((s,b)=>s+b.break_count,0)}次', stocks: brokenBoards.map(b => ({ code: b.code, name: b.name || '', detail: `炸${b.break_count}次 · ${b.streak || 0}板` })) })} className="group">
                  <div className="text-lg font-black text-red-600 group-hover:scale-110 transition-transform">{brokenBoards.reduce((s, b) => s + b.break_count, 0)}</div>
                  <div className="text-xs text-zinc-400 group-hover:text-zinc-600">总炸板次</div>
                </button>
                <button onClick={() => setDetailSheet({ title: '涨停成交 · 总成交额', stocks: items.sort((a,b) => (b.amount||0)-(a.amount||0)).map(s => ({ code: s.code, name: s.name || '', detail: `${(s.amount/1e8).toFixed(1)}亿 · ${s.seal_quality.grade}` })) })} className="group">
                  <div className="text-lg font-black text-rose-600 group-hover:scale-110 transition-transform">{(items.reduce((sum, s) => sum + (s.amount || 0), 0) / 1e8).toFixed(0)}亿</div>
                  <div className="text-xs text-zinc-400 group-hover:text-zinc-600">涨停成交</div>
                </button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ===== 核心指标卡 ===== */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div onClick={() => setDetailSheet({ title: '涨停家数 · 全部涨停股', stocks: items.map(s => ({ code: s.code, name: s.name || '', detail: `${s.streak || 0}连板 · ${s.seal_quality.grade}` })) })} className="cursor-pointer group">
          <StatCard
            label="涨停家数"
            value={ztAnalysis?.total ?? 0}
            color="text-red-600 dark:text-red-400"
            sub={`首板${streakGroups[1]?.length || 0} · 连板${items.length - (streakGroups[1]?.length || 0)}`}
          />
        </div>
        <div onClick={() => setDetailSheet({ title: '强势封板 · 秒板+零炸', stocks: items.filter(s => s.seal_quality.grade === '强势封板').map(s => ({ code: s.code, name: s.name || '', detail: `${s.seal_quality.time_label} · ${s.seal_quality.break_label}` })) })} className="cursor-pointer group">
          <StatCard
            label="强势封板"
            value={items.filter(s => s.seal_quality.grade === '强势封板').length}
            color="text-emerald-600 dark:text-emerald-400"
            icon={<ShieldCheck className="h-3.5 w-3.5" />}
            sub={items.length > 0 ? `${((items.filter(s => s.seal_quality.grade === '强势封板').length / items.length) * 100).toFixed(0)}% 秒板+零炸` : ''}
          />
        </div>
        <div onClick={() => setDetailSheet({ title: '炸板预警 · 全部炸板≥3次', stocks: brokenBoards.map(b => ({ code: b.code, name: b.name || '', detail: `炸${b.break_count}次 · ${b.streak || 0}板` })) })} className="cursor-pointer group">
          <StatCard
            label="炸板预警"
            value={brokenBoards.length}
            color="text-orange-600 dark:text-orange-400"
            icon={<Bomb className="h-3.5 w-3.5" />}
            sub={`≥3次 共${brokenBoards.reduce((s, b) => s + b.break_count, 0)}次`}
          />
        </div>
        <div className="cursor-pointer group">
          <StatCard
            label="美股联动"
            value={usCorr ? `${usCorr.concepts?.length || usCorr.stocks.length}个` : '分析中'}
            color="text-blue-600 dark:text-blue-400"
            icon={<Globe className="h-3.5 w-3.5" />}
            sub={usCorr?.date ? `概念产业链联动 · ${usCorr.date}` : "概念产业链联动"}
          />
        </div>
        <div className="cursor-pointer group">
          <StatCard
            label="融资余额"
            value={marginSummary ? (marginSummary.total_margin_balance / 1e8).toFixed(0) + '亿' : '-'}
            color="text-blue-600 dark:text-blue-400"
            icon={<Banknote className="h-3.5 w-3.5" />}
            sub={marginSummary ? `${marginSummary.stock_count}只标的` : ''}
          />
        </div>
      </div>

      {/* ===== 时间分布 + 行业热力 ===== */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {/* 封板时间分布 - 更视觉化 */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Clock className="h-3.5 w-3.5 text-blue-500" />
              封板时间分布
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3">
            <div className="space-y-2.5">
              {(ztAnalysis?.time_dist || []).map(t => {
                const maxCount = Math.max(...(ztAnalysis?.time_dist.map(x => x.count) || [1]));
                const pct = maxCount > 0 ? (t.count / maxCount) * 100 : 0;
                const total = ztAnalysis?.total || 1;
                const ratio = total > 0 ? ((t.count / total) * 100).toFixed(0) : '0';
                const isFast = t.label.includes('秒板');
                const isEarly = t.label.includes('早封') && !t.label.includes('早盘');
                const isAfternoon = t.label.includes('午后');
                const barColor = isFast ? 'bg-emerald-500' : isEarly ? 'bg-blue-500' : isAfternoon ? 'bg-zinc-400' : 'bg-amber-500';
                const timeStocks = items.filter(s => {
                  const ft = s.first_seal_time || '';
                  if (t.label.includes('秒板')) return ft <= '093500';
                  if (t.label.includes('早封') && !t.label.includes('早盘')) return ft > '093500' && ft <= '094500';
                  if (t.label.includes('早盘封')) return ft > '094500' && ft <= '100000';
                  if (t.label.includes('午前封')) return ft > '100000' && ft <= '103000';
                  return ft > '103000' || !ft;
                });
                return (
                  <button
                    key={t.label}
                    onClick={() => setDetailSheet({ title: `${t.label.split('(')[0]} · ${t.count}只`, stocks: timeStocks.map(s => ({ code: s.code, name: s.name || '', detail: `${s.seal_quality.time_label} · ${s.seal_quality.grade} · ${s.streak || 0}板` })) })}
                    className="relative w-full text-left hover:bg-zinc-50 dark:hover:bg-zinc-800/50 rounded px-1 py-0.5 -mx-1 transition-colors group/time"
                  >
                    <div className="flex items-center gap-2 text-xs mb-0.5">
                      <span className="w-28 text-zinc-600 dark:text-zinc-400 shrink-0">{t.label.replace('(',' ').replace(')','')}</span>
                      <span className="ml-auto font-bold text-zinc-700 dark:text-zinc-300">{t.count}</span>
                      <span className="text-xs text-zinc-400 w-8 text-right">{ratio}%</span>
                      <span className="text-xs text-zinc-300 opacity-0 group-hover/time:opacity-100 transition-opacity">查看 →</span>
                    </div>
                    <div className="h-1.5 bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                      <div className={cn("h-full rounded-full transition-all group-hover/time:brightness-75", barColor)} style={{ width: `${pct}%` }} />
                    </div>
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* 行业热力 TOP8 */}
        <Card className="sm:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Layers className="h-3.5 w-3.5 text-red-500" />
              涨停行业热力图 TOP8
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {industries.slice(0, 8).map((ind, i) => {
                const colors = [
                  'bg-red-100 dark:bg-red-950/40 border-red-200 dark:border-red-800',
                  'bg-orange-100 dark:bg-orange-950/40 border-orange-200 dark:border-orange-800',
                  'bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-800',
                  'bg-yellow-50 dark:bg-yellow-950/30 border-yellow-200 dark:border-yellow-800',
                  'bg-rose-50 dark:bg-rose-950/30 border-rose-200 dark:border-rose-800',
                  'bg-pink-50 dark:bg-pink-950/30 border-pink-200 dark:border-pink-800',
                  'bg-fuchsia-50 dark:bg-fuchsia-950/20 border-fuchsia-200 dark:border-fuchsia-800',
                  'bg-violet-50 dark:bg-violet-950/20 border-violet-200 dark:border-violet-800',
                ];
                return (
                  <div key={ind.name} className={cn("rounded-lg p-2.5 border", colors[i] || colors[0])}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="text-xs font-bold text-zinc-800 dark:text-zinc-200 truncate max-w-[70%]" title={ind.name}>
                        {ind.name}
                      </div>
                      <span className="text-xs text-zinc-400">#{i + 1}</span>
                    </div>
                    <div className="flex items-baseline gap-1 mb-1">
                      <span className="text-xl font-black text-red-600">{ind.count}</span>
                      <span className="text-xs text-zinc-400">只涨停</span>
                    </div>
                    {ind.max_streak > 1 && (
                      <div className="text-xs text-amber-600 font-medium mb-1.5">
                         最高{ind.max_streak}连板
                      </div>
                    )}
                    <div className="flex flex-wrap gap-0.5">
                      {ind.stocks.slice(0, 4).map(st => (
                        <button
                          key={st.code}
                          onClick={() => { setKlineCode(st.code); setKlineName(st.name || st.code); }}
                          className="text-xs px-1 py-0.5 rounded bg-white/60 dark:bg-white/10 hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-600 transition-colors"
                        >
                          {st.name}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ===== 融资余额 + 成交量走势图 ===== */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <Banknote className="h-4 w-4 text-blue-500" />
            融资余额 & 市场成交量走势
            <span className="text-xs font-normal text-zinc-400">近90日</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4">
          <MarginChart days={90} />
        </CardContent>
      </Card>

      {/* ===== 连板梯队 + 封板质量 ===== */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2">
            <Flame className="h-4 w-4 text-red-500" />
            连板梯队 · 封板质量
            <span className="text-xs font-normal text-zinc-400">秒板+早封=强势 · 零炸板=确定性高</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className={cn(
            "grid gap-3",
            maxStreak >= 4 ? "grid-cols-2 sm:grid-cols-4" :
            maxStreak >= 3 ? "grid-cols-2 sm:grid-cols-3" : "grid-cols-2"
          )}>
            {[
              { label: '首板', n: 1, color: 'bg-zinc-50 dark:bg-zinc-900', border: 'border-zinc-200 dark:border-zinc-800', text: 'text-zinc-700 dark:text-zinc-300', icon: '①' },
              { label: '2板', n: 2, color: 'bg-amber-50 dark:bg-amber-950', border: 'border-amber-200 dark:border-amber-800', text: 'text-amber-700 dark:text-amber-300', icon: '②' },
              { label: '3板', n: 3, color: 'bg-red-50 dark:bg-red-950', border: 'border-red-200 dark:border-red-800', text: 'text-red-700 dark:text-red-300', icon: '③' },
              { label: '4板+', n: 4, color: 'bg-purple-50 dark:bg-purple-950', border: 'border-purple-200 dark:border-purple-800', text: 'text-purple-700 dark:text-purple-300', icon: '④' },
            ].map(tier => {
              const tierStocks = tier.n >= 4
                ? items.filter(s => (s.streak || 0) >= 4)
                : (streakGroups[tier.n] || []);
              const displayed = expandedTiers[tier.n] ? tierStocks : tierStocks.slice(0, 8);
              // 统计该梯队封板质量
              const strongInTier = tierStocks.filter(s => s.seal_quality.grade === '强势封板').length;

              return (
                <div key={tier.label} className={cn("rounded-lg p-3 border", tier.color, tier.border)}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className={cn("text-sm font-bold", tier.text)}>{tier.label}</span>
                    <Badge className="text-xs" variant="secondary">{tierStocks.length}只</Badge>
                    {tier.n >= 2 && tier.n < 4 && (
                      <span className="text-xs text-zinc-400">
                        晋级{(streakGroups[tier.n - 1]?.length || 0) > 0
                          ? ((tierStocks.length / (streakGroups[tier.n - 1]?.length || 1)) * 100).toFixed(0) + '%' : '-'}
                      </span>
                    )}
                    {strongInTier > 0 && (
                      <span className="text-xs text-emerald-600 ml-auto">强势{strongInTier}</span>
                    )}
                  </div>
                  {displayed.length > 0 ? (
                    <div className="space-y-1.5">
                      {displayed.map(s => (
                        <button
                          key={s.code}
                          onClick={() => { setKlineCode(s.code); setKlineName(s.name || s.code); }}
                          className="w-full text-left group flex items-center gap-2 text-xs py-1.5 px-2 rounded hover:bg-white/70 dark:hover:bg-white/5 transition-colors"
                        >
                          {/* 封板质量标签 */}
                          <span className={cn(
                            "text-xs px-1.5 py-0.5 rounded font-medium shrink-0 min-w-[42px] text-center border",
                            GRADE_COLORS[s.seal_quality.grade] || 'bg-zinc-100 text-zinc-500 border-zinc-200'
                          )}>
                            {s.seal_quality.time_label}
                          </span>
                          <span className="font-medium truncate flex-1">{s.name}</span>
                          <span className="text-zinc-400 text-xs shrink-0 hidden sm:inline">{s.code}</span>
                          {/* 封成比 */}
                          {s.seal_ratio != null && (
                            <span className={cn(
                              "text-xs shrink-0 px-1 rounded",
                              s.seal_ratio >= 0.5 ? "text-emerald-600 bg-emerald-50 dark:bg-emerald-950" :
                              s.seal_ratio >= 0.2 ? "text-amber-600 bg-amber-50 dark:bg-amber-950" :
                              "text-zinc-400"
                            )}>封成{s.seal_ratio}</span>
                          )}
                          <span className={cn(
                            "text-xs shrink-0",
                            (s.break_count || 0) === 0 ? "text-emerald-600 font-medium" :
                            (s.break_count || 0) <= 2 ? "text-amber-600" : "text-red-500"
                          )}>
                            {s.seal_quality.break_label}
                          </span>
                        </button>
                      ))}
                      {tierStocks.length > displayed.length && (
                        <button
                          onClick={() => setExpandedTiers(prev => ({ ...prev, [tier.n]: !prev[tier.n] }))}
                          className="text-xs text-blue-500 hover:text-blue-600 font-medium pl-2"
                        >
                          展开全部 {tierStocks.length} 只 →
                        </button>
                      )}
                      {expandedTiers[tier.n] && tierStocks.length > 8 && (
                        <button
                          onClick={() => setExpandedTiers(prev => ({ ...prev, [tier.n]: false }))}
                          className="text-xs text-zinc-400 hover:text-zinc-500 pl-2"
                        >
                          收起
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-zinc-400 py-2 text-center">暂无</div>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* ===== 炸板预警 ===== */}
      {brokenBoards.length > 0 && (
        <Card className="border-orange-200 dark:border-orange-800 bg-orange-50/30 dark:bg-orange-950/10">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Bomb className="h-3.5 w-3.5 text-orange-500" />
              炸板预警
              <span className="text-xs font-normal text-zinc-400">（≥3次炸板 · 封板失败风险高 · 共{brokenBoards.length}只）</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-6 gap-2">
              {brokenBoards.slice(0, expandedTiers[-1] ? brokenBoards.length : 18).map((b, i) => {
                const stock = items.find(s => s.code === b.code);
                const severity = b.break_count >= 10 ? 'bg-red-100 dark:bg-red-950 border-red-300 dark:border-red-700' :
                  b.break_count >= 5 ? 'bg-orange-100 dark:bg-orange-950 border-orange-300 dark:border-orange-700' :
                  'bg-yellow-50 dark:bg-yellow-950 border-yellow-200 dark:border-yellow-700';
                return (
                  <button
                    key={b.code}
                    onClick={() => { setKlineCode(b.code); setKlineName(b.name || b.code); }}
                    className={cn("flex items-center gap-2 px-2.5 py-2 rounded-lg border text-xs hover:shadow-sm transition-shadow text-left", severity)}
                  >
                    <span className="text-xs font-black text-zinc-500 w-4">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{b.name}</div>
                      <div className="text-xs text-zinc-400">炸{b.break_count}次{stock ? ` · ${stock.seal_quality.time_label}` : ''}{b.streak > 1 ? ` · ${b.streak}板` : ''}</div>
                    </div>
                  </button>
                );
              })}
              {brokenBoards.length > 18 && !expandedTiers[-1] && (
                <button
                  onClick={() => setExpandedTiers(prev => ({ ...prev, [-1]: true }))}
                  className="text-xs text-blue-500 hover:text-blue-600 font-medium self-center"
                >
                  展开全部 {brokenBoards.length} 只 →
                </button>
              )}
              {expandedTiers[-1] && brokenBoards.length > 18 && (
                <button
                  onClick={() => setExpandedTiers(prev => ({ ...prev, [-1]: false }))}
                  className="text-xs text-zinc-400 hover:text-zinc-500 self-center"
                >
                  收起
                </button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* ===== 美股→A股联动模块 ===== */}
      <UsCorrelationModule />

      {/* ===== 明日预测模块 ===== */}
      <PredictionModule />

      {/* ===== 回测验证模块 ===== */}
      <BacktestModule />

      {/* ===== Detail Sheet (stat card drill-down) ===== */}
      {detailSheet && (
        <>
          <div className="fixed inset-0 bg-black/50 z-40" onClick={() => setDetailSheet(null)} />
          <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md bg-white dark:bg-zinc-900 shadow-lg overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-zinc-200 dark:border-zinc-800 sticky top-0 bg-white dark:bg-zinc-900 z-10">
              <h3 className="text-sm font-semibold">
                {detailSheet.title}
                <span className="text-xs text-zinc-400 ml-2">共{detailSheet.stocks.length}只</span>
              </h3>
              <button onClick={() => setDetailSheet(null)} className="p-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="p-3">
              <div className="space-y-1">
                {detailSheet.stocks.map((st, i) => (
                  <button
                    key={st.code}
                    onClick={() => { setKlineCode(st.code); setKlineName(st.name); }}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors text-left"
                  >
                    <span className="text-xs text-zinc-400 w-4 text-right">{i + 1}</span>
                    <span className="text-sm font-medium truncate flex-1">{st.name}</span>
                    <span className="text-xs text-zinc-400 shrink-0">{st.code}</span>
                    {st.detail && (
                      <span className="text-xs text-zinc-500 shrink-0">{st.detail}</span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* ===== K-line Side Panel ===== */}
      {klineCode && (
        <>
          <div className="fixed inset-0 bg-black/50 z-40" onClick={() => setKlineCode(null)} />
          <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white dark:bg-zinc-900 shadow-lg overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-zinc-200 dark:border-zinc-800 sticky top-0 bg-white dark:bg-zinc-900 z-10">
              <h3 className="text-base font-semibold">
                {klineName}
                <span className="text-xs text-zinc-400 ml-2">{klineCode}</span>
              </h3>
              <button onClick={() => setKlineCode(null)} className="p-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <div className="p-4">
              <KLineChart code={klineCode} name={klineName} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}
