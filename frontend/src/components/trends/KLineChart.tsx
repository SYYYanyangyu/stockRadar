import { useState, useEffect } from 'react';
import { api } from '@/api';
import type { KLineItem } from '@/types';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/shared/EmptyState';
import { fmtWan } from '@/lib/format';
import { cn } from '@/lib/utils';
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell,
} from 'recharts';

interface KLineChartProps {
  code: string;
  name: string;
  days?: number;
}

// 计算均线
function calcMA(data: KLineItem[], days: number): (number | null)[] {
  const result: (number | null)[] = [];
  for (let i = 0; i < data.length; i++) {
    if (i < days - 1) { result.push(null); continue; }
    let sum = 0;
    for (let j = i - days + 1; j <= i; j++) sum += data[j].close;
    result.push(+(sum / days).toFixed(2));
  }
  return result;
}

export default function KLineChart({ code, name, days = 60 }: KLineChartProps) {
  const [data, setData] = useState<KLineItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.stockKline(code, days)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [code, days]);

  if (loading) return <Skeleton className="h-[400px] w-full" />;
  if (!data.length) return <EmptyState text="暂无K线数据" icon="📊" />;

  const ma5 = calcMA(data, 5);
  const ma10 = calcMA(data, 10);
  const ma20 = calcMA(data, 20);

  const chartData = data.map((d, i) => ({
    ...d,
    ma5: ma5[i],
    ma10: ma10[i],
    ma20: ma20[i],
    isUp: d.close >= d.open,
    body: [d.open, d.close].sort((a, b) => a - b),
    wickLow: d.low,
    wickHigh: d.high,
  }));

  const last = data[data.length - 1];
  const changePct = last ? (last.change_pct ?? 0) : 0;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-sm font-bold">{name} <span className="text-xs text-zinc-400 ml-1">{code}</span></div>
          <div className="text-xs text-zinc-500 mt-0.5">
            MA5 <span className="text-amber-500 font-medium">{last ? last.close?.toFixed(2) : '-'}</span>
            {' '}近{days}日
          </div>
        </div>
        <div className={cn(
          "text-lg font-bold",
          changePct >= 0 ? "text-red-600" : "text-green-600"
        )}>
          {last?.close?.toFixed(2)}
          <span className="text-xs ml-1">
            ({changePct >= 0 ? '+' : ''}{changePct?.toFixed(2)}%)
          </span>
        </div>
      </div>

      {/* Candlestick chart */}
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            dataKey="trade_date"
            tick={{ fontSize: 10, fill: '#94a3b8' }}
            tickFormatter={(v: string) => v?.slice(5) || ''}
            interval={Math.floor(data.length / 6)}
          />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fontSize: 10, fill: '#94a3b8' }}
            width={55}
            tickFormatter={(v: number) => v.toFixed(1)}
          />
          <Tooltip
            contentStyle={{
              background: '#fff',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              fontSize: '12px',
              fontFamily: 'monospace',
            }}
            formatter={(value: unknown, name: unknown) => [Number(value).toFixed(2), String(name)]}
            labelFormatter={(label: unknown) => `日期: ${label}`}
          />
          {/* Close price line */}
          <Line type="monotone" dataKey="close" stroke="#3b82f6" dot={false} strokeWidth={1} name="收盘" />
          {/* MA lines */}
          <Line type="monotone" dataKey="ma5" stroke="#f59e0b" dot={false} strokeWidth={1} name="MA5" connectNulls />
          <Line type="monotone" dataKey="ma10" stroke="#8b5cf6" dot={false} strokeWidth={1} name="MA10" connectNulls />
          <Line type="monotone" dataKey="ma20" stroke="#06b6d4" dot={false} strokeWidth={1} name="MA20" connectNulls />
        </ComposedChart>
      </ResponsiveContainer>

      {/* Volume bars */}
      <div className="mt-3">
        <div className="text-xs text-zinc-400 mb-1">成交量</div>
        <ResponsiveContainer width="100%" height={80}>
          <ComposedChart data={chartData}>
            <Bar dataKey="volume" name="成交量">
              {chartData.map((d, i) => (
                <Cell key={i} fill={d.isUp ? '#ef4444' : '#22c55e'} fillOpacity={0.3} />
              ))}
            </Bar>
            <Tooltip
              contentStyle={{ fontSize: '11px', fontFamily: 'monospace' }}
              formatter={(value: unknown) => [fmtWan(Number(value)), '成交量']}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-2 text-xs text-zinc-400">
        <span><span className="inline-block w-3 h-0.5 bg-amber-500 align-middle mr-1" />MA5</span>
        <span><span className="inline-block w-3 h-0.5 bg-violet-500 align-middle mr-1" />MA10</span>
        <span><span className="inline-block w-3 h-0.5 bg-cyan-500 align-middle mr-1" />MA20</span>
        <span><span className="inline-block w-3 h-0.5 bg-blue-500 align-middle mr-1" />收盘</span>
      </div>
    </div>
  );
}
