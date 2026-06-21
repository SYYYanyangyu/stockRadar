import { useState, useEffect, Fragment } from 'react';
import { api } from '../api';
import type { VolumeAnomalyItem, KLineItem } from '../types';
import { cn } from '@/lib/utils';
import VolumeSparkline from '../components/trends/VolumeSparkline';
import { Pagination } from '@/components/shared/Pagination';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/Table';

export default function VolumeAnomalyPage({ onLoaded }: { onLoaded: () => void }) {
  const [items, setItems] = useState<VolumeAnomalyItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [days, setDays] = useState(5);
  const [baseDays, setBaseDays] = useState(50);
  const [minRatio, setMinRatio] = useState(2.0);
  const [excludeZt, setExcludeZt] = useState(true);
  const [loading, setLoading] = useState(true);
  const [dataDate, setDataDate] = useState('');
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [klineData, setKlineData] = useState<KLineItem[]>([]);
  const [klineLoading, setKlineLoading] = useState(false);
  const pageSize = 20;

  const fetchData = () => {
    setLoading(true);
    api.volumeAnomaly({ days, base_days: baseDays, min_ratio: minRatio, exclude_zt: excludeZt, page, page_size: pageSize })
      .then(r => { setItems(r.items); setTotal(r.total); setDataDate(r.data_date || ''); })
      .finally(() => { setLoading(false); onLoaded(); });
  };

  useEffect(fetchData, [days, baseDays, minRatio, excludeZt, page]);

  const handleRowClick = async (code: string) => {
    if (expandedCode === code) {
      setExpandedCode(null);
      return;
    }
    setExpandedCode(code);
    setKlineLoading(true);
    try {
      const data = await api.stockKline(code, 30);
      setKlineData(data);
    } finally {
      setKlineLoading(false);
    }
  };

  const formatDate = (d: string) => {
    if (!d) return '-';
    const parts = d.split('-');
    return `${parts[1]}-${parts[2]}`;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-bold">成交量异动</h2>
        <div className="flex items-center gap-2 ml-auto">
          <label className="text-xs text-zinc-500">窗口</label>
          {[5, 10, 15].map(d => (
            <button key={d} onClick={() => { setDays(d); setPage(1); }}
              className={cn("px-2 py-1 rounded text-xs", days === d ? "bg-red-100 text-red-700" : "bg-zinc-100 text-zinc-600")}>{d}日</button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-zinc-500">基线</label>
          {[50, 120].map(d => (
            <button key={d} onClick={() => { setBaseDays(d); setPage(1); }}
              className={cn("px-2 py-1 rounded text-xs", baseDays === d ? "bg-red-100 text-red-700" : "bg-zinc-100 text-zinc-600")}>{d}日</button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-zinc-500">量比≥</label>
          {[1.5, 2.0, 3.0, 5.0].map(r => (
            <button key={r} onClick={() => { setMinRatio(r); setPage(1); }}
              className={cn("px-2 py-1 rounded text-xs", minRatio === r ? "bg-red-100 text-red-700" : "bg-zinc-100 text-zinc-600")}>{r}x</button>
          ))}
        </div>
        <button onClick={() => { setExcludeZt(!excludeZt); setPage(1); }}
          className={cn("px-2 py-1 rounded text-xs", excludeZt ? "bg-red-100 text-red-700" : "bg-zinc-100 text-zinc-600")}>
          {excludeZt ? '排除涨停' : '含涨停'}
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-10">
          <div className="w-5 h-5 rounded-full border-2 border-red-200 border-t-red-600 animate-spin" />
        </div>
      ) : total === 0 ? (
        <div className="text-center py-10 text-zinc-400">
          <p className="text-lg mb-1">暂无满足条件的异动股票</p>
          <p className="text-xs">尝试放宽量比阈值或增加时间窗口</p>
        </div>
      ) : (
        <>
          <div className="flex items-center gap-3 text-xs text-zinc-500 flex-wrap">
            <span>共 {total} 只，量比 ≥ {minRatio}x，按量比降序</span>
            {dataDate && (
              <span className="text-zinc-400">数据截至 {dataDate}</span>
            )}
            {days >= 10 && (
              <span className="text-amber-500">（{days}日窗口数据可能不完整）</span>
            )}
          </div>
          <div className="overflow-x-auto rounded-lg border border-zinc-200">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>代码</TableHead>
                  <TableHead>名称</TableHead>
                  <TableHead className="text-right">量比</TableHead>
                  <TableHead className="text-right">涨跌幅</TableHead>
                  <TableHead className="text-right">最新价</TableHead>
                  <TableHead className="text-right">{days}日均量</TableHead>
                  <TableHead className="text-right">{baseDays}日均量</TableHead>
                  <TableHead className="text-right">成交额</TableHead>
                  <TableHead className="text-right">日期</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((it, i) => (
                  <Fragment key={it.code}>
                    <TableRow onClick={() => handleRowClick(it.code)}
                      className={cn(
                        "cursor-pointer",
                        expandedCode === it.code && "bg-red-50/50"
                      )}>
                      <TableCell className="font-mono text-xs">{it.code}</TableCell>
                      <TableCell className="font-medium text-xs">{it.name || '-'}</TableCell>
                      <TableCell className="text-right">
                        <span className={cn(
                          "inline-block px-2 py-0.5 rounded text-xs font-bold",
                          it.volume_ratio >= 5 ? "bg-red-600 text-white" :
                          it.volume_ratio >= 3 ? "bg-orange-100 text-orange-700" :
                          "bg-yellow-100 text-yellow-700"
                        )}>{it.volume_ratio.toFixed(1)}x</span>
                      </TableCell>
                      <TableCell className={cn("text-right text-xs font-mono",
                        (it.change_pct ?? 0) > 0 ? "text-red-600" : (it.change_pct ?? 0) < 0 ? "text-green-600" : "text-zinc-400")}>
                        {it.change_pct != null ? `${it.change_pct > 0 ? '+' : ''}${it.change_pct.toFixed(2)}%` : '-'}
                      </TableCell>
                      <TableCell className="text-right text-xs font-mono">{it.price != null ? it.price.toFixed(2) : '-'}</TableCell>
                      <TableCell className="text-right text-xs font-mono">{it.avg_vol_short > 0 ? (it.avg_vol_short / 10000).toFixed(0) + '万' : '-'}</TableCell>
                      <TableCell className="text-right text-xs font-mono">{it.avg_vol_base > 0 ? (it.avg_vol_base / 10000).toFixed(0) + '万' : '-'}</TableCell>
                      <TableCell className="text-right text-xs font-mono">{it.amount > 0 ? (it.amount / 1e8).toFixed(2) + '亿' : '-'}</TableCell>
                      <TableCell className="text-right text-xs font-mono text-zinc-400">{formatDate(it.latest_trade_date || '')}</TableCell>
                    </TableRow>
                    {expandedCode === it.code && (
                      <TableRow key={`${i}-expand`}>
                        <TableCell colSpan={9} className="bg-zinc-50/70 py-3">
                          {klineLoading ? (
                            <div className="flex justify-center py-4">
                              <div className="w-4 h-4 rounded-full border-2 border-red-200 border-t-red-600 animate-spin" />
                            </div>
                          ) : klineData.length > 0 ? (
                            <div className="space-y-2">
                              <VolumeSparkline data={klineData} baselineAvg={it.avg_vol_base} />
                              <div className="flex gap-4 text-xs text-zinc-500">
                                <span>近5日均量: {(it.avg_vol_short / 10000).toFixed(0)}万</span>
                                <span>基线均量: {(it.avg_vol_base / 10000).toFixed(0)}万</span>
                                <span>今日量: {it.latest_volume > 0 ? (it.latest_volume / 10000).toFixed(0) + '万' : '-'}</span>
                              </div>
                            </div>
                          ) : (
                            <p className="text-xs text-zinc-400 text-center py-2">暂无K线数据</p>
                          )}
                        </TableCell>
                      </TableRow>
                    )}
                  </Fragment>
                ))}
              </TableBody>
            </Table>
          </div>
          <Pagination page={page} pageSize={pageSize} total={total} onChange={setPage} />
        </>
      )}
    </div>
  );
}