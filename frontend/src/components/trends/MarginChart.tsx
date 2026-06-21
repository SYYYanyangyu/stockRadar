import { useState, useEffect } from 'react';
import { api } from '@/api';
import type { MarginHistoryItem } from '@/types';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { cn } from '@/lib/utils';
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell, Area,
} from 'recharts';

export default function MarginChart({ days = 90 }: { days?: number }) {
  const [data, setData] = useState<MarginHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.marginHistory(days)
      .then(d => setData(d.reverse()))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [days]);

  if (loading) return <Skeleton className="h-[280px] w-full" />;
  if (!data.length) return <EmptyState text="暂无融资历史数据" />;

  // Format to 亿 for display
  const toYi = (v: number) => v / 1e8;
  const toYiStr = (v: number) => (v / 1e8).toFixed(0) + '亿';

  const chartData = data.map(d => ({
    ...d,
    marginYi: +((d.margin_balance || 0) / 1e8).toFixed(0),
    amountYi: +((d.total_amount || 0) / 1e8).toFixed(0),
    volYi: +((d.total_volume || 0) / 1e8).toFixed(1),
    buyYi: +((d.margin_buy || 0) / 1e8).toFixed(0),
  }));

  const latest = chartData[chartData.length - 1];
  const first = chartData[0];

  return (
    <div>
      {/* Header with current stats */}
      <div className="flex items-center gap-4 mb-2 flex-wrap">
        <div>
          <span className="text-xs text-zinc-400">融资余额</span>
          <span className="text-sm font-bold text-blue-600 ml-1.5">
            {latest ? toYiStr(latest.margin_balance) : '-'}
          </span>
        </div>
        <div>
          <span className="text-xs text-zinc-400">当日买入</span>
          <span className="text-sm font-bold text-red-600 ml-1.5">
            {latest ? toYiStr(latest.margin_buy) : '-'}
          </span>
        </div>
        <div>
          <span className="text-xs text-zinc-400">市场成交</span>
          <span className="text-sm font-bold text-zinc-700 dark:text-zinc-300 ml-1.5">
            {latest ? toYiStr(latest.total_amount) : '-'}
          </span>
        </div>
        {first && latest && first.margin_balance > 0 && (
          <div className="ml-auto">
            <span className={cn(
              "text-xs font-bold",
              latest.margin_balance >= first.margin_balance ? "text-red-600" : "text-green-600"
            )}>
              {((latest.margin_balance / first.margin_balance - 1) * 100).toFixed(1)}%
            </span>
            <span className="text-xs text-zinc-400 ml-1">近{days}日</span>
          </div>
        )}
      </div>

      {/* Main chart: 融资余额 (line) + 成交额 (area) */}
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            dataKey="trade_date"
            tick={{ fontSize: 9, fill: '#94a3b8' }}
            tickFormatter={(v: string) => v?.slice(5) || ''}
            interval={Math.floor(data.length / 8)}
          />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 9, fill: '#94a3b8' }}
            width={55}
            tickFormatter={(v: number) => v.toFixed(0) + '亿'}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 9, fill: '#94a3b8' }}
            width={55}
            tickFormatter={(v: number) => v.toFixed(0) + '亿'}
          />
          <Tooltip
            contentStyle={{
              background: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              fontSize: '11px',
              fontFamily: 'monospace',
            }}
            formatter={(value: unknown, name: unknown) => {
              const n = Number(value);
              const labels: Record<string, string> = {
                marginYi: '融资余额',
                amountYi: '成交额',
                buyYi: '融资买入',
              };
              return [n.toFixed(0) + '亿', labels[String(name)] || String(name)];
            }}
            labelFormatter={(label: unknown) => `日期: ${label}`}
          />
          {/* 成交额面积 */}
          <Area
            yAxisId="right"
            type="monotone"
            dataKey="amountYi"
            fill="#f3f4f6"
            stroke="#d1d5db"
            fillOpacity={0.4}
            name="成交额"
          />
          {/* 融资余额线 */}
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="marginYi"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            name="融资余额"
          />
          {/* 融资买入柱 */}
          <Bar yAxisId="left" dataKey="buyYi" name="融资买入" opacity={0.5}>
            {chartData.map((d, i) => (
              <Cell key={i} fill="#ef4444" />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="flex gap-4 mt-1 text-xs text-zinc-400">
        <span><span className="inline-block w-3 h-0.5 bg-blue-500 align-middle mr-1" />融资余额</span>
        <span><span className="inline-block w-3 h-2 bg-red-400 align-middle mr-1 rounded-sm" />融资买入</span>
        <span><span className="inline-block w-3 h-2 bg-zinc-300 align-middle mr-1 rounded-sm" />市场成交额</span>
      </div>
    </div>
  );
}
