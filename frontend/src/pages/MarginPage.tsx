import { useState, useEffect } from 'react';
import { api } from '../api';
import type { MarginSummary, MarginTopChange } from '../types';
import { LoadingSkeleton } from '@/components/shared/LoadingSkeleton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/Table';
import { cn } from '@/lib/utils';
import { fmtYi, fmtPct, colorPct } from '@/lib/format';
import { TrendingUp, Building2 } from 'lucide-react';
import MarginChart from '../components/trends/MarginChart';

export default function MarginPage({ onLoaded }: { onLoaded: () => void }) {
  const [summary, setSummary] = useState<MarginSummary | null>(null);
  const [topChanges, setTopChanges] = useState<MarginTopChange[]>([]);
  const [sectorSummary, setSectorSummary] = useState<{ sector_code: string; total_margin: number; stock_count: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.marginSummary(),
      api.marginTopChanges('weekly', 'increase', 20),
      api.marginSectorSummary(),
    ]).then(([s, t, sec]) => {
      setSummary(s);
      setTopChanges(t);
      setSectorSummary(sec);
    }).finally(() => {
      setLoading(false);
      onLoaded();
    });
  }, []);


  if (loading) return <LoadingSkeleton rows={8} />;

  return (
    <div className="space-y-4 animate-in fade-in">
      <h2 className="text-lg font-bold">两融深度分析</h2>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Card>
          <CardContent className="p-3">
            <div className="text-xs text-zinc-500 mb-1">两融标的</div>
            <div className="text-xl font-bold">{summary?.stock_count || 0}<span className="text-xs font-normal text-zinc-400 ml-1">只</span></div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <div className="text-xs text-zinc-500 mb-1">融资余额</div>
            <div className="text-xl font-bold text-red-600">{fmtYi(summary?.total_margin_balance)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <div className="text-xs text-zinc-500 mb-1">当日融资买入</div>
            <div className="text-xl font-bold text-amber-600">{fmtYi(summary?.total_margin_buy)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-3">
            <div className="text-xs text-zinc-500 mb-1">总余额(含融券)</div>
            <div className="text-xl font-bold">{fmtYi(summary?.total_balance)}</div>
          </CardContent>
        </Card>
      </div>

      {/* Trend chart */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>融资余额 & 市场成交量 走势（近120日）</CardTitle>
        </CardHeader>
        <CardContent>
          <MarginChart days={120} />
        </CardContent>
      </Card>

      {/* Two columns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top changes */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-red-500" />
              融资余额 TOP20
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">代码</TableHead>
                    <TableHead className="text-xs">名称</TableHead>
                    <TableHead className="text-xs text-right">融资余额</TableHead>
                    <TableHead className="text-xs text-right">融资买入</TableHead>
                    <TableHead className="text-xs text-right">涨跌</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {topChanges.map(it => (
                    <TableRow key={it.code}>
                      <TableCell className="text-xs font-mono text-zinc-400">{it.code}</TableCell>
                      <TableCell className="text-xs font-medium">{it.name}</TableCell>
                      <TableCell className="text-xs text-right font-mono text-red-600">{fmtYi(it.margin_balance)}</TableCell>
                      <TableCell className="text-xs text-right font-mono">{fmtYi(it.margin_buy)}</TableCell>
                      <TableCell className={cn("text-xs text-right font-mono", colorPct(it.change_pct))}>
                        {it.change_pct != null ? fmtPct(it.change_pct) : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>

        {/* Sector summary */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-violet-500" />
              板块融资汇总 TOP20
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">板块</TableHead>
                    <TableHead className="text-xs text-right">融资余额</TableHead>
                    <TableHead className="text-xs text-right">标的数</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sectorSummary.slice(0, 20).map(it => (
                    <TableRow key={it.sector_code}>
                      <TableCell className="text-xs font-medium truncate max-w-[180px]">{it.sector_code}</TableCell>
                      <TableCell className="text-xs text-right font-mono text-red-600">{fmtYi(it.total_margin)}</TableCell>
                      <TableCell className="text-xs text-right">{it.stock_count}<span className="text-zinc-400 ml-0.5">只</span></TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
