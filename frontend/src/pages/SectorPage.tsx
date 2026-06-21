import React, { useState, useEffect, useRef } from 'react';
import { api } from '../api';
import type { SectorItem, SectorStock } from '../types';
import { PaginatedResponse } from '../types';
import { Pagination } from '@/components/shared/Pagination';
import { LoadingSkeleton } from '@/components/shared/LoadingSkeleton';
import { StatCard } from '@/components/shared/StatCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/Table';
import { ScrollArea } from '@/components/ui/ScrollArea';
import KLineChart from '@/components/trends/KLineChart';
import { cn } from '@/lib/utils';
import { fmtPct, colorPct } from '@/lib/format';

const PAGE_SIZE = 50;

export default function SectorPage({ onLoaded }: { onLoaded: () => void }) {
  const [sectors, setSectors] = useState<PaginatedResponse<SectorItem> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [sectorStocks, setSectorStocks] = useState<Record<string, SectorStock[]>>({});

  const [klineCode, setKlineCode] = useState<string | null>(null);
  const [klineName, setKlineName] = useState('');

  const tableRef = useRef<HTMLDivElement>(null);
  const sectorRowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

  useEffect(() => {
    setLoading(true);
    api.sectorRank(page, PAGE_SIZE)
      .then(setSectors)
      .catch(() => {})
      .finally(() => {
        setLoading(false);
        onLoaded();
      });
  }, [page]);

  const expand = async (code: string, scrollIntoView = false) => {
    if (expandedCode === code) { setExpandedCode(null); return; }
    setExpandedCode(code);
    if (scrollIntoView) {
      setTimeout(() => {
        const row = sectorRowRefs.current[code];
        if (row) {
          row.scrollIntoView({ behavior: 'smooth', block: 'center' });
          row.classList.add('ring-2', 'ring-violet-400');
          setTimeout(() => row.classList.remove('ring-2', 'ring-violet-400'), 2000);
        }
      }, 100);
    }
    if (!sectorStocks[code]) {
      try {
        const result = await api.sectorStocks(code, 1, 50);
        setSectorStocks(prev => ({ ...prev, [code]: result.items || [] }));
      } catch { /* ignore */ }
    }
  };

  const items = sectors?.items || [];
  const rising = items.filter(s => Number(s.change_pct) > 0);
  const falling = items.filter(s => Number(s.change_pct) < 0);

  if (loading && !sectors) {
    return <LoadingSkeleton variant="card" />;
  }

  return (
    <div className="space-y-4 animate-in fade-in">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard
          label="概念板块"
          value={sectors?.total ?? 0}
          color="text-violet-600 dark:text-violet-400"
        />
        <div onClick={() => {
          if (rising.length > 0) expand(rising[0].code, true);
        }} className="cursor-pointer group relative">
          <StatCard
            label="上涨板块"
            value={rising.length}
            color="text-red-600 dark:text-red-400"
            sub={sectors ? `${(rising.length / sectors.total * 100).toFixed(0)}%` : ''}
          />
          <span className="absolute bottom-1 right-2 text-xs text-zinc-400 opacity-0 group-hover:opacity-100 transition-opacity">点击查看详情 →</span>
        </div>
        <div onClick={() => {
          if (falling.length > 0) expand(falling[0].code, true);
        }} className="cursor-pointer group relative">
          <StatCard
            label="下跌板块"
            value={falling.length}
            color="text-green-600 dark:text-green-400"
            sub={sectors ? `${(falling.length / sectors.total * 100).toFixed(0)}%` : ''}
          />
          <span className="absolute bottom-1 right-2 text-xs text-zinc-400 opacity-0 group-hover:opacity-100 transition-opacity">点击查看详情 →</span>
        </div>
        <div onClick={() => {
          if (items.length > 0) expand(items[0].code, true);
        }} className="cursor-pointer group relative">
          <StatCard
            label="涨幅最高"
            value={items[0]?.name?.slice(0, 4) ?? '-'}
            color="text-amber-600 dark:text-amber-400"
            small
            sub={items[0] ? fmtPct(items[0].change_pct) : ''}
          />
          <span className="absolute bottom-1 right-2 text-xs text-zinc-400 opacity-0 group-hover:opacity-100 transition-opacity">点击查看详情 →</span>
        </div>
      </div>

      {/* TOP Cards */}
      {items.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
          {items.slice(0, 10).map((s, i) => (
            <Card
              key={i}
              onClick={() => expand(s.code, true)}
              className={cn(
                "hover:shadow-md transition-shadow cursor-pointer",
                Number(s.change_pct) >= 0 ? "border-red-100 dark:border-red-900" : "border-blue-100 dark:border-blue-900"
              )}
            >
              <CardContent className="p-3">
                <div className="flex items-start justify-between mb-1">
                  <span className="text-xs font-bold truncate max-w-[55%]">{s.name}</span>
                  <span className={cn(
                    "text-xs font-bold px-1.5 py-0.5 rounded",
                    Number(s.change_pct) >= 0
                      ? "bg-red-50 dark:bg-red-950 text-red-600"
                      : "bg-blue-50 dark:bg-blue-950 text-blue-600"
                  )}>
                    {fmtPct(s.change_pct)}
                  </span>
                </div>
                <div className="text-xs text-zinc-500 dark:text-zinc-400">
                  <div>领涨: <span className="font-medium text-zinc-700 dark:text-zinc-300">{s.top_stock}</span></div>
                  <div>
                    <span className="text-red-500">涨 {s.up_count}</span>{' '}
                    <span className="text-green-500">跌 {s.down_count}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Full table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">全部板块（共 {sectors?.total} 个）</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>板块</TableHead>
                  <TableHead>涨幅%</TableHead>
                  <TableHead>领涨股</TableHead>
                  <TableHead>领涨涨幅</TableHead>
                  <TableHead>涨/跌</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map(s => (
                  <React.Fragment key={s.code}>
                    <TableRow
                      ref={(el) => { sectorRowRefs.current[s.code] = el; }}
                      onClick={() => expand(s.code)}
                      className={cn(
                        "cursor-pointer",
                        expandedCode === s.code && "bg-violet-50/50 dark:bg-violet-950/20"
                      )}
                    >
                      <TableCell>
                        <span className="font-medium text-sm">{s.name}</span>
                        <span className="text-xs text-zinc-400 ml-1.5">{s.code}</span>
                      </TableCell>
                      <TableCell>
                        <span className={cn("font-bold text-sm", colorPct(Number(s.change_pct)))}>
                          {fmtPct(Number(s.change_pct))}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="text-violet-600 dark:text-violet-400 font-medium">{s.top_stock}</span>
                      </TableCell>
                      <TableCell>
                        <span className={cn("font-semibold text-sm", colorPct(Number(s.top_change_pct)))}>
                          {fmtPct(Number(s.top_change_pct))}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="text-red-500">{s.up_count}</span>
                        <span className="text-zinc-400"> / </span>
                        <span className="text-green-500">{s.down_count}</span>
                      </TableCell>
                    </TableRow>
                    {expandedCode === s.code && sectorStocks[s.code] && (
                      <TableRow>
                        <TableCell colSpan={5} className="p-0">
                          <div className="bg-zinc-50 dark:bg-zinc-900 p-4">
                            <div className="text-xs font-semibold mb-2 text-zinc-500">成分股（点击查看K线）：</div>
                            <div className="flex gap-2 flex-wrap">
                              {sectorStocks[s.code].map((st, j) => (
                                <button
                                  key={j}
                                  onClick={(e) => { e.stopPropagation(); setKlineCode(st.code); setKlineName(st.name || st.code); }}
                                  className="bg-white dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700 rounded-lg px-3 py-1.5 text-xs hover:border-violet-400 dark:hover:border-violet-500 hover:shadow-sm transition-all"
                                >
                                  <span className="font-medium">{st.name}</span>
                                  <span className="text-zinc-400 text-xs ml-1">{st.code}</span>
                                  <span className={cn("ml-2 font-semibold", colorPct(st.change_pct))}>
                                    {fmtPct(st.change_pct)}
                                  </span>
                                </button>
                              ))}
                            </div>
                          </div>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          </ScrollArea>
          {sectors && (
            <Pagination page={page} pageSize={PAGE_SIZE} total={sectors.total} onChange={setPage} />
          )}
        </CardContent>
      </Card>

      {/* K-line sheet */}
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
