import { BarChart, Bar, XAxis, YAxis, ReferenceLine, ResponsiveContainer } from 'recharts';
import type { KLineItem } from '@/types';

interface Props {
  data: KLineItem[];
  baselineAvg?: number;
}

export default function VolumeSparkline({ data, baselineAvg }: Props) {
  const recent = data.slice(-20);
  if (recent.length === 0) return <div className="text-xs text-muted-foreground py-2">无成交量数据</div>;

  const maxVol = Math.max(...recent.map(d => d.volume));
  if (maxVol <= 0) return <div className="text-xs text-muted-foreground py-2">无成交量数据</div>;

  const chartData = recent.map(d => ({
    ...d,
    volYi: +(d.volume / 1e4).toFixed(0),
    fill: (d.change_pct ?? 0) >= 0 ? '#ef4444' : '#22c55e',
    label: d.trade_date ? d.trade_date.slice(5) : '',
  }));

  return (
    <ResponsiveContainer width="100%" height={60}>
      <BarChart data={chartData} margin={{ top: 2, right: 2, bottom: 0, left: 0 }}>
        <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#94a3b8' }} interval="preserveStartEnd" axisLine={false} tickLine={false} />
        <YAxis hide domain={[0, 'dataMax']} />
        {baselineAvg && baselineAvg > 0 && (
          <ReferenceLine
            y={baselineAvg / 1e4}
            stroke="#d4d4d8"
            strokeDasharray="3 3"
            strokeWidth={0.5}
          />
        )}
        <Bar dataKey="volYi" radius={[1, 1, 0, 0]} maxBarSize={8}>
          {chartData.map((entry, index) => (
            <rect key={index} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
