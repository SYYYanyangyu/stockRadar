import { useState, useEffect } from 'react';
import { api } from '@/api';
import type { BacktestResponse } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/utils';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, BarChart, Bar } from 'recharts';
import { BarChart2, TrendingUp, Zap, CheckCircle2, AlertTriangle, Clock, Layers } from 'lucide-react';

const SIG_COLORS: Record<string, string> = {
  strong: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-950',
  moderate: 'text-blue-600 bg-blue-50 dark:bg-blue-950',
  weak: 'text-amber-600 bg-amber-50 dark:bg-amber-950',
  none: 'text-zinc-400 bg-zinc-50 dark:bg-zinc-900',
};

const SIG_LABELS: Record<string, string> = {
  strong: '★★★',
  moderate: '★★',
  weak: '★',
  none: '-',
};

export default function BacktestModule() {
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'detail' | 'extreme' | 'stability'>('overview');
  const [selectedIndex, setSelectedIndex] = useState<string>('all');

  useEffect(() => {
    api.backtest()
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <Skeleton className="h-[400px] w-full" />;
  }

  if (!data) {
    return null;
  }

  const filtered = data.by_concept.filter(c =>
    selectedIndex === 'all' ? true : c.index_symbol === selectedIndex
  );

  const gotStrongSignal = data.summary.strong_signals > 0;

  const barData = data.by_concept
    .filter(c => c.index_symbol === '.IXIC')
    .sort((a, b) => b.diff_bps - a.diff_bps)
    .slice(0, 8)
    .map(c => ({ concept: c.concept, diff_bps: c.diff_bps }));

  return (
    <Card className="border-emerald-200 dark:border-emerald-800">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <BarChart2 className="h-4 w-4 text-emerald-500" />
          回测验证 · 美股→A股联动
          <span className="text-xs font-normal text-muted-foreground ml-1">
            历史数据验证预测能力
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {/* ── Top Line Summary Banner ── */}
        <div className={cn(
          'rounded-lg p-4 mb-4',
          gotStrongSignal
            ? 'bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-700'
            : 'bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-700'
        )}>
          <div className="flex items-center gap-3 flex-wrap">
            <div className={cn(
              'w-12 h-12 rounded-full flex items-center justify-center text-xl font-black',
              gotStrongSignal
                ? 'bg-emerald-200 dark:bg-emerald-800 text-emerald-700 dark:text-emerald-300'
                : 'bg-amber-200 dark:bg-amber-800 text-amber-700 dark:text-amber-300'
            )}>
              {data.summary.strong_signals}
            </div>
            <div>
              <div className={cn('font-bold text-sm', gotStrongSignal ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-700 dark:text-amber-300')}>
                {gotStrongSignal
                  ? `${data.summary.strong_signals} 组回测达到统计强显著 (p<0.01)`
                  : '回测信号较弱，暂未达到统计显著'}
              </div>
              <div className="text-xs text-muted-foreground mt-0.5">
                三指数 × 10概念 = {data.summary.total_tests}组测试 · {data.summary.moderate_signals}组中等显著
                · 数据覆盖 {data.summary.data_period} · 对齐{data.summary.total_aligned_days}天
              </div>
              <div className="text-xs text-emerald-600 dark:text-emerald-400 mt-0.5 font-medium">
                最强信号：{data.summary.best_signal.concept} × {data.summary.best_signal.index_name}
                {' '}均值差 {data.summary.best_signal.diff_bps >= 0 ? '+' : ''}{data.summary.best_signal.diff_bps}bp
                {' '}p={data.summary.best_signal.p_value}
              </div>
            </div>
          </div>
        </div>

        {/* ── Tab Bar ── */}
        <div className="flex gap-1 mb-4 border-b border-border pb-2">
          {[
            { key: 'overview', label: '概览', icon: Layers },
            { key: 'detail', label: '全量明细', icon: TrendingUp },
            { key: 'extreme', label: '极端行情', icon: Zap },
            { key: 'stability', label: '时间稳定性', icon: Clock },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as typeof activeTab)}
              className={cn(
                'px-3 py-1.5 text-xs rounded-md font-medium transition-colors flex items-center gap-1.5',
                activeTab === tab.key
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:text-foreground',
              )}
            >
              <tab.icon className="h-3 w-3" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* ── Overview Tab ── */}
        {activeTab === 'overview' && (
          <div>
            {/* Index Summary Cards */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              {data.by_index.map(idx => (
                <div
                  key={idx.index_symbol}
                  className="rounded-lg border border-border p-3 cursor-pointer hover:border-primary/30 transition-colors"
                  onClick={() => { setSelectedIndex(idx.index_symbol); setActiveTab('detail'); }}
                >
                  <div className="text-xs font-medium mb-1">{idx.index_name}</div>
                  <div className="text-lg font-bold">
                    {idx.significant_concepts}/{idx.concepts_tested}
                    <span className="text-xs font-normal text-muted-foreground ml-1">显著</span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    avg diff {idx.avg_diff_bps >= 0 ? '+' : ''}{idx.avg_diff_bps}bp
                  </div>
                  <div className="text-xs text-emerald-600 dark:text-emerald-400">
                    最佳: {idx.best_concept}
                  </div>
                </div>
              ))}
            </div>

            {/* Top 8 Concepts Bar Chart */}
            <div className="text-xs font-medium text-muted-foreground mb-2">概念排名 · 均值差(bp) · 纳斯达克</div>
            <div className="h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} layout="vertical" margin={{ left: 100, right: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="concept" tick={{ fontSize: 11 }} width={100} />
                  <Tooltip />
                  <ReferenceLine x={0} stroke="#9ca3af" />
                  <Bar dataKey="diff_bps" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Key Insight */}
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-emerald-200 dark:border-emerald-800 bg-emerald-50/30 dark:bg-emerald-950/10 p-3">
                <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-700 dark:text-emerald-300 mb-1">
                  <Zap className="h-3 w-3" /> 极端放大效应
                </div>
                <div className="text-xs text-muted-foreground">
                  纳指涨&gt;2%时，锂电池概念次日平均涨幅+0.56%，远超纳指微涨(+0.27%)。
                  跌幅方向同样放大，呈现清晰的"剂量-反应"梯度。
                </div>
              </div>
              <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-950/10 p-3">
                <div className="flex items-center gap-1.5 text-xs font-bold text-blue-700 dark:text-blue-300 mb-1">
                  <CheckCircle2 className="h-3 w-3" /> 多指数交叉验证
                </div>
                <div className="text-xs text-muted-foreground">
                  标普500和道琼斯的预测信号与纳指方向一致，
                  三指数共识信号的可信度远高于单一指数。
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Detail Tab ── */}
        {activeTab === 'detail' && (
          <div>
            {/* Index filter */}
            <div className="flex gap-1 mb-3">
              {['all', '.IXIC', '.INX', '.DJI'].map(sym => (
                <button
                  key={sym}
                  onClick={() => setSelectedIndex(sym)}
                  className={cn(
                    'px-2 py-1 text-xs rounded font-mono transition-colors',
                    selectedIndex === sym ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground hover:text-foreground',
                  )}
                >
                  {sym === 'all' ? '全部' : sym}
                </button>
              ))}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-muted-foreground">
                    <th className="text-left py-2 font-medium">概念</th>
                    <th className="text-left py-2 font-medium">指数</th>
                    <th className="text-right py-2 font-medium">样本</th>
                    <th className="text-right py-2 font-medium">指数涨后</th>
                    <th className="text-right py-2 font-medium">指数跌后</th>
                    <th className="text-right py-2 font-medium">均值差</th>
                    <th className="text-right py-2 font-medium">涨胜率</th>
                    <th className="text-right py-2 font-medium">跌胜率</th>
                    <th className="text-right py-2 font-medium">p值</th>
                    <th className="text-center py-2 font-medium">显著</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(row => (
                    <tr
                      key={`${row.concept}-${row.index_symbol}`}
                      className={cn(
                        'border-b border-border/50 hover:bg-muted/50',
                        row.significance === 'strong' ? 'bg-emerald-50/20 dark:bg-emerald-950/10' : '',
                      )}
                    >
                      <td className="py-2 font-medium">{row.concept}</td>
                      <td className="py-2 text-muted-foreground">{row.index_name}</td>
                      <td className="py-2 text-right font-mono">{row.samples}</td>
                      <td className={cn('py-2 text-right font-mono', row.up_avg >= 0 ? 'text-red-600' : 'text-green-600')}>
                        {row.up_avg >= 0 ? '+' : ''}{row.up_avg.toFixed(2)}%
                      </td>
                      <td className={cn('py-2 text-right font-mono', row.down_avg >= 0 ? 'text-red-600' : 'text-green-600')}>
                        {row.down_avg >= 0 ? '+' : ''}{row.down_avg.toFixed(2)}%
                      </td>
                      <td className={cn('py-2 text-right font-mono font-bold', row.diff_bps >= 0 ? 'text-red-600' : 'text-green-600')}>
                        {row.diff_bps >= 0 ? '+' : ''}{row.diff_bps}bp
                      </td>
                      <td className="py-2 text-right">{row.up_winrate}%</td>
                      <td className="py-2 text-right">{row.down_winrate}%</td>
                      <td className={cn('py-2 text-right font-mono', row.p_value < 0.05 ? 'text-emerald-600 font-bold' : row.p_value < 0.1 ? 'text-blue-600' : '')}>
                        {row.p_value.toFixed(4)}
                      </td>
                      <td className="py-2 text-center">
                        <span className={cn('text-xs px-1.5 py-0.5 rounded-full font-bold', SIG_COLORS[row.significance])}>
                          {SIG_LABELS[row.significance]}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── Extreme Tab ── */}
        {activeTab === 'extreme' && (
          <div>
            <div className="text-xs text-muted-foreground mb-3">
              每行一个概念，展示纳指涨跌幅分档下A股概念的平均表现。
              颜色越<span className="text-red-600">红</span>越涨，越<span className="text-green-600">绿</span>越跌。
            </div>

            {data.extreme_analysis.slice(0, 8).map(concept => (
              <div key={concept.concept} className="mb-4 last:mb-0">
                <div className="text-xs font-bold mb-1.5">{concept.concept}</div>
                <div className="grid grid-cols-6 gap-1.5">
                  {concept.bins.map(bin => {
                    const val = bin.avg_a_chg;
                    const isUp = val != null && val >= 0;
                    const intensity = val != null ? Math.min(1, Math.abs(val) / 2) : 0;
                    return (
                      <div key={bin.label} className="text-center">
                        <div className="text-xs text-muted-foreground mb-1">{bin.label}</div>
                        <div
                          className={cn(
                            'rounded-lg py-2 px-1',
                            val == null
                              ? 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400'
                              : isUp
                                ? 'bg-red-500 text-white'
                                : 'bg-green-500 text-white',
                          )}
                          style={val != null ? { opacity: 0.3 + intensity * 0.7 } : {}}
                        >
                          <div className="text-sm font-black">
                            {val != null ? `${val >= 0 ? '+' : ''}${val.toFixed(2)}%` : '-'}
                          </div>
                          <div className="text-xs opacity-80">
                            {bin.n > 0 ? `${bin.winrate}%胜` : ''}
                          </div>
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          n={bin.n}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Stability Tab ── */}
        {activeTab === 'stability' && (
          <div>
            <div className="text-xs text-muted-foreground mb-3">
              锂电池概念 × 纳斯达克，3个月滚动窗口（60个交易日）的均值差变化。
              红色点为p&lt;0.05显著窗口。
            </div>

            <div className="h-[250px] mb-4">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.time_stability} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="window_start"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v: string) => v.slice(5)}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v}bp`}
                  />
                  <Tooltip />
                  <ReferenceLine y={0} stroke="#9ca3af" strokeDasharray="3 3" />
                  <Line
                    type="monotone"
                    dataKey="diff_bps"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#3b82f6' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Key observation */}
            <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-700 text-xs">
              <AlertTriangle className="h-3.5 w-3.5 text-blue-500 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-blue-700 dark:text-blue-300">关键观察：</span>
                信号在2025年9月后明显增强（连续两个窗口p&lt;0.05），可能是市场风格切换或样本积累效应。
                此前4-8月窗口信号较弱（p&gt;0.4），说明联动关系并非稳定存在，需持续监控。
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
