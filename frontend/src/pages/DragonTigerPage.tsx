import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api';
import type { DragonTigerItem, DragonTigerSeat, NorthBoundData, DragonTigerGroup, ConceptGroup, StockBrief, TraderDetail } from '../types';
import { PaginatedResponse } from '../types';
import { Pagination } from '@/components/shared/Pagination';
import { EmptyState } from '@/components/shared/EmptyState';
import { LoadingSkeleton } from '@/components/shared/LoadingSkeleton';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/Table';
import { ScrollArea } from '@/components/ui/ScrollArea';
import KLineChart from '@/components/trends/KLineChart';
import { cn } from '@/lib/utils';
import { fmtWan, fmtPct, colorPct } from '@/lib/format';
import { Flame, Building2, Users, X } from 'lucide-react';

const PAGE_SIZE = 20;

export default function DragonTigerPage({ onLoaded }: { onLoaded: () => void }) {
  const [dtPage, setDtPage] = useState(1);
  const [dtData, setDtData] = useState<PaginatedResponse<DragonTigerItem> | null>(null);
  const [north, setNorth] = useState<NorthBoundData>({});
  const [traderGroups, setTraderGroups] = useState<DragonTigerGroup[]>([]);
  const [conceptGroups, setConceptGroups] = useState<ConceptGroup[]>([]);
  const [view, setView] = useState<'list' | 'trader' | 'concept'>('list');
  const [loading, setLoading] = useState(true);

  // Seat detail
  const [expandedCode, setExpandedCode] = useState<string | null>(null);
  const [seats, setSeats] = useState<Record<string, DragonTigerSeat[]>>({});

  // K-line
  const [klineCode, setKlineCode] = useState<string | null>(null);
  const [klineName, setKlineName] = useState('');

  // Trader detail sheet
  const [traderDetail, setTraderDetail] = useState<TraderDetail | null>(null);
  const [traderDetailLoading, setTraderDetailLoading] = useState(false);

  const openTraderDetail = async (traderName: string) => {
    setTraderDetail(null);
    setTraderDetailLoading(true);
    try {
      const d = await api.dragonTigerTraderDetail(traderName);
      setTraderDetail(d);
    } catch { /* ignore */ }
    setTraderDetailLoading(false);
  };

  const loadDt = useCallback(async (page: number) => {
    setLoading(true);
    try {
      const dt = await api.dragonTiger(page, PAGE_SIZE);
      setDtData(dt);
    } catch { /* ignore */ }
    try {
      const n = await api.northBound();
      setNorth(n);
    } catch { /* ignore */ }
    try {
      const tg = await api.dragonTigerByTrader(5);
      setTraderGroups(tg || []);
    } catch { /* ignore */ }
    try {
      const cg = await api.dragonTigerByConcept();
      setConceptGroups(cg || []);
    } catch { /* ignore */ }
    setLoading(false);
    onLoaded();
  }, []);

  useEffect(() => {
    loadDt(dtPage);
  }, [dtPage]);

  const toggleSeats = async (code: string) => {
    if (expandedCode === code) { setExpandedCode(null); return; }
    setExpandedCode(code);
    if (!seats[code]) {
      try {
        const data = await api.dragonTigerSeats(code);
        setSeats(prev => ({ ...prev, [code]: data }));
      } catch { /* ignore */ }
    }
  };

  const netFlow = Number(north.net_flow) || 0;
  const items = dtData?.items || [];

  return (
    <div className="space-y-4 animate-in fade-in">
      {/* North bound banner */}
      <Card className={cn(netFlow >= 0 ? "border-red-200 dark:border-red-900 bg-red-50/30 dark:bg-red-950/20" : "border-green-200 dark:border-green-900 bg-green-50/30 dark:bg-green-950/20")}>
        <CardContent className="p-4 flex items-center justify-between">
          <div>
            <div className="text-xs text-muted-foreground mb-1">北向资金（当日净流入）</div>
            <div className={cn("text-2xl font-bold tracking-tight", netFlow >= 0 ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400")}>
              {netFlow > 0 ? '+' : ''}{fmtYi(netFlow)}
            </div>
          </div>
          <div className={cn("text-3xl", netFlow >= 0 ? "text-red-500" : "text-green-500")}>
            {netFlow >= 0 ? '🔥' : '💧'}
          </div>
        </CardContent>
      </Card>

      {/* View tabs */}
      <Tabs value={view} onValueChange={(v) => setView(v as typeof view)}>
        <TabsList className="w-full sm:w-auto">
          <TabsTrigger value="list" className="text-xs">
            <Flame className="h-3.5 w-3.5 mr-1" /> 龙虎榜
          </TabsTrigger>
          <TabsTrigger value="trader" className="text-xs">
            <Users className="h-3.5 w-3.5 mr-1" /> 游资分组
          </TabsTrigger>
          <TabsTrigger value="concept" className="text-xs">
            <Building2 className="h-3.5 w-3.5 mr-1" /> 概念分组
          </TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="mt-4">
          {loading ? <LoadingSkeleton rows={10} /> : items.length === 0 ? <EmptyState text="今日暂无龙虎榜数据" /> : (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">龙虎榜（共 {dtData?.total} 只）</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <ScrollArea>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>代码</TableHead>
                        <TableHead>名称</TableHead>
                        <TableHead>原因</TableHead>
                        <TableHead>换手%</TableHead>
                        <TableHead>净买(万)</TableHead>
                        <TableHead>席位</TableHead>
                        <TableHead>涨幅%</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {items.map(s => {
                        const seatList = seats[s.code] || [];
                        const buySeats = seatList.filter(t => t.trader_type === 'buy');
                        const sellSeats = seatList.filter(t => t.trader_type === 'sell');
                        const isExpanded = expandedCode === s.code;
                        return (
                          <React.Fragment key={s.code}>
                            <TableRow
                              onClick={() => toggleSeats(s.code)}
                              className={cn("cursor-pointer", isExpanded && "bg-red-50/50 dark:bg-red-950/20")}
                            >
                              <TableCell className="text-xs text-zinc-400">{s.code}</TableCell>
                              <TableCell>
                                <span className="font-medium text-sm">{s.name}</span>
                                {s.up_desc && (
                                  <Badge variant="outline" className="ml-1 text-xs py-0 px-1">{s.up_desc}</Badge>
                                )}
                              </TableCell>
                              <TableCell className="text-xs max-w-[160px] truncate" title={s.reason}>
                                {s.reason || '-'}
                              </TableCell>
                              <TableCell className="text-sm font-semibold">
                                {(s.turnover_ratio ?? 0).toFixed(2)}%
                              </TableCell>
                              <TableCell>
                                <span className={cn("font-bold text-sm", Number(s.net_buy) >= 0 ? "text-red-600" : "text-green-600")}>
                                  {fmtWan(Number(s.net_buy))}
                                </span>
                              </TableCell>
                              <TableCell className="text-xs">
                                买{s.buy_seats ?? 0}/{s.sell_seats ?? 0}卖
                              </TableCell>
                              <TableCell>
                                <span className={cn("font-bold text-sm", colorPct(Number(s.change_pct)))}>
                                  {fmtPct(Number(s.change_pct))}
                                </span>
                              </TableCell>
                            </TableRow>
                            {isExpanded && (
                              <TableRow>
                                <TableCell colSpan={7} className="p-0">
                                  <div className="bg-zinc-50 dark:bg-zinc-900 p-4">
                                    {seatList.length > 0 ? (
                                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        {buySeats.length > 0 && (
                                          <div>
                                            <div className="text-xs font-bold text-red-600 mb-2">买入席位</div>
                                            {buySeats.map((t, j) => (
                                              <div key={j} className="flex justify-between text-xs py-1 border-b border-zinc-100 dark:border-zinc-800 last:border-0">
                                                <span>
                                                  <span className="text-zinc-400 mr-2">#{t.rank}</span>
                                                  {t.trader_name}
                                                  {t.group_name && (
                                                    <Badge variant="secondary" className="ml-1 text-xs py-0">{t.group_name}</Badge>
                                                  )}
                                                </span>
                                                <span className="text-red-600 font-semibold">{fmtWan(t.buy_amount)}</span>
                                              </div>
                                            ))}
                                          </div>
                                        )}
                                        {sellSeats.length > 0 && (
                                          <div>
                                            <div className="text-xs font-bold text-green-600 mb-2">卖出席位</div>
                                            {sellSeats.map((t, j) => (
                                              <div key={j} className="flex justify-between text-xs py-1 border-b border-zinc-100 dark:border-zinc-800 last:border-0">
                                                <span>
                                                  <span className="text-zinc-400 mr-2">#{t.rank}</span>
                                                  {t.trader_name}
                                                  {t.group_name && (
                                                    <Badge variant="secondary" className="ml-1 text-xs py-0">{t.group_name}</Badge>
                                                  )}
                                                </span>
                                                <span className="text-green-600 font-semibold">{fmtWan(t.sell_amount)}</span>
                                              </div>
                                            ))}
                                          </div>
                                        )}
                                      </div>
                                    ) : (
                                      <div className="text-xs text-zinc-400">暂无席位明细</div>
                                    )}
                                    <button
                                      onClick={(e) => { e.stopPropagation(); setKlineCode(s.code); setKlineName(s.name || s.code); }}
                                      className="mt-3 text-xs text-blue-500 hover:text-blue-600 font-medium"
                                    >
                                      📊 查看K线图
                                    </button>
                                  </div>
                                </TableCell>
                              </TableRow>
                            )}
                          </React.Fragment>
                        );
                      })}
                    </TableBody>
                  </Table>
                </ScrollArea>
                <Pagination
                  page={dtPage}
                  pageSize={PAGE_SIZE}
                  total={dtData?.total || 0}
                  onChange={setDtPage}
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="trader" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">游资席位分组（近5天）</CardTitle>
            </CardHeader>
            <CardContent>
              {traderGroups.length === 0 ? <EmptyState text="暂无游资分组数据" /> : (
                <div className="space-y-3">
                  <div className="overflow-x-auto rounded border border-zinc-200">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs whitespace-nowrap">游资</TableHead>
                          <TableHead className="text-xs text-right whitespace-nowrap">操作次数</TableHead>
                          <TableHead className="text-xs text-right whitespace-nowrap">涉及股票</TableHead>
                          <TableHead className="text-xs text-right whitespace-nowrap">买入次数</TableHead>
                          <TableHead className="text-xs text-right whitespace-nowrap">总买入</TableHead>
                          <TableHead className="text-xs text-right whitespace-nowrap">总卖出</TableHead>
                          <TableHead className="text-xs text-right whitespace-nowrap">净额</TableHead>
                          <TableHead className="text-xs text-right whitespace-nowrap">活跃天数</TableHead>
                          <TableHead className="text-xs text-right whitespace-nowrap">买入比例</TableHead>
                          <TableHead className="text-xs text-right whitespace-nowrap">跟庄胜率*</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {traderGroups.map(g => (
                          <TableRow key={g.group_name} className="cursor-pointer hover:bg-zinc-50"
                            onClick={() => openTraderDetail(g.group_name)}>
                            <TableCell className="text-xs font-bold whitespace-nowrap text-blue-600 hover:underline">
                              {g.group_name}
                            </TableCell>
                            <TableCell className="text-xs text-right font-mono">{g.total_trades}</TableCell>
                            <TableCell className="text-xs text-right font-mono">{g.stock_count}</TableCell>
                            <TableCell className="text-xs text-right font-mono text-red-600">{g.buy_times}</TableCell>
                            <TableCell className="text-xs text-right font-mono text-red-600">{fmtWan(g.total_buy)}</TableCell>
                            <TableCell className="text-xs text-right font-mono text-green-600">{fmtWan(g.total_sell)}</TableCell>
                            <TableCell className={cn("text-xs text-right font-mono font-semibold", g.net >= 0 ? "text-red-600" : "text-green-600")}>
                              {fmtWan(g.net)}
                            </TableCell>
                            <TableCell className="text-xs text-right">{g.active_days}<span className="text-zinc-400">天</span></TableCell>
                            <TableCell className="text-xs text-right">
                              <span className={cn(g.buy_ratio >= 0.6 ? "text-red-600" : g.buy_ratio >= 0.4 ? "text-amber-600" : "text-green-600")}>
                                {(g.buy_ratio * 100).toFixed(0)}%
                              </span>
                            </TableCell>
                            <TableCell className="text-xs text-right">
                              <span className={cn(g.win_rate >= 0.7 ? "text-red-600" : g.win_rate >= 0.5 ? "text-amber-600" : "text-zinc-400")}>
                                {g.win_rate > 0 ? `${(g.win_rate * 100).toFixed(0)}%` : '-'}
                              </span>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                  <p className="text-xs text-zinc-400">*跟庄胜率: 近5日买入后下一交易日股价上涨的比例。点击游资名称查看详情。</p>
                  <CoOccurrencePanel />
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="concept" className="mt-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">概念分组（涨停+龙虎榜共振）</CardTitle>
            </CardHeader>
            <CardContent>
              {conceptGroups.length === 0 ? <EmptyState text="暂无概念分组数据" /> : (
                <div className="space-y-3">
                  {conceptGroups.map((g, i) => (
                    <Card key={i} className="hover:shadow-sm transition-shadow">
                      <CardContent className="p-3">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold">{g.concept}</span>
                            <Badge variant="default" className="text-xs">{g.stock_count}只上榜</Badge>
                            {g.max_streak >= 3 && (
                              <Badge variant="destructive" className="text-xs">{g.max_streak}连板</Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-3 text-xs text-zinc-500">
                            <span>均涨幅 <span className={cn("font-semibold", g.avg_change_pct >= 0 ? "text-red-600" : "text-green-600")}>
                              {g.avg_change_pct > 0 ? '+' : ''}{g.avg_change_pct?.toFixed(1)}%</span></span>
                            {g.total_seat_net !== 0 && (
                              <span>游资净 <span className={cn("font-semibold", g.total_seat_net >= 0 ? "text-red-600" : "text-green-600")}>
                                {fmtWan(g.total_seat_net)}</span></span>
                            )}
                          </div>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {(g.stocks || []).map(st => (
                            <div key={st.code}
                              onClick={(e) => { e.stopPropagation(); setKlineCode(st.code); setKlineName(st.name || st.code); }}
                              className="flex items-center gap-3 px-2 py-1.5 rounded bg-zinc-50 hover:bg-violet-50 cursor-pointer transition-colors group"
                            >
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-1.5">
                                  <span className="text-xs font-mono text-zinc-400">{st.code}</span>
                                  <span className="text-xs font-medium truncate">{st.name}</span>
                                  {st.streak > 1 && (
                                    <Badge variant="destructive" className="text-xs py-0 px-1">{st.streak}板</Badge>
                                  )}
                                </div>
                                {st.traders && (
                                  <div className="text-xs text-zinc-400 truncate mt-0.5">{st.traders}</div>
                                )}
                              </div>
                              <div className="text-right shrink-0">
                                <div className={cn("text-xs font-mono font-semibold", st.change_pct >= 0 ? "text-red-600" : "text-green-600")}>
                                  {st.change_pct > 0 ? '+' : ''}{st.change_pct?.toFixed(1)}%
                                </div>
                                {st.dt_net !== 0 && (
                                  <div className={cn("text-xs font-mono", st.dt_net >= 0 ? "text-red-500" : "text-green-500")}>
                                    {st.dt_net > 0 ? '净入' : '净出'}{fmtWan(Math.abs(st.dt_net))}
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* K-line Side Panel */}
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
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4">
              <KLineChart code={klineCode} name={klineName} />
            </div>
          </div>
        </>
      )}

      {/* Trader Detail Sheet */}
      {traderDetail && (
        <>
          <div className="fixed inset-0 bg-black/50 z-40" onClick={() => setTraderDetail(null)} />
          <div className="fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white dark:bg-zinc-900 shadow-lg overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-zinc-200 dark:border-zinc-800 sticky top-0 bg-white dark:bg-zinc-900 z-10">
              <h3 className="text-base font-semibold">{traderDetail.trader_name}</h3>
              <button onClick={() => setTraderDetail(null)} className="p-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800">
                <X className="w-5 h-5" />
              </button>
            </div>
            {traderDetailLoading ? (
              <div className="p-6 flex justify-center">
                <div className="w-5 h-5 rounded-full border-2 border-red-200 border-t-red-600 animate-spin" />
              </div>
            ) : !traderDetail.total_appearances ? (
              <div className="p-6"><EmptyState text="暂无该游资详情" /></div>
            ) : (
              <div className="p-4 space-y-4">
                {/* Stats */}
                <div className="grid grid-cols-3 gap-2">
                  <Card>
                    <CardContent className="p-3 text-center">
                      <div className="text-lg font-bold">{traderDetail.total_appearances}</div>
                      <div className="text-xs text-zinc-500">上榜次数</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-3 text-center">
                      <div className={cn("text-lg font-bold", traderDetail.net >= 0 ? "text-red-600" : "text-green-600")}>
                        {fmtWan(traderDetail.net)}
                      </div>
                      <div className="text-xs text-zinc-500">净买入</div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-3 text-center">
                      <div className="text-lg font-bold">{(traderDetail.win_rate_est * 100).toFixed(0)}%</div>
                      <div className="text-xs text-zinc-500">预估胜率</div>
                    </CardContent>
                  </Card>
                </div>

                {/* Favorite sectors */}
                {traderDetail.favorite_sectors.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-zinc-500 mb-2">偏好的行业方向</div>
                    <div className="flex flex-wrap gap-1">
                      {traderDetail.favorite_sectors.map(s => (
                        <Badge key={s} variant="secondary" className="text-xs">{s}</Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Co-traders */}
                {traderDetail.co_traders.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-zinc-500 mb-2">协同上榜游资</div>
                    <div className="flex flex-wrap gap-1">
                      {traderDetail.co_traders.map(ct => (
                        <button
                          key={ct.name}
                          onClick={() => openTraderDetail(ct.name)}
                          className="text-xs px-2 py-1 rounded bg-violet-50 dark:bg-violet-950 text-violet-600 hover:bg-violet-100 transition-colors"
                        >
                          {ct.name}
                          <span className="text-violet-400 ml-1">{ct.co_count}次</span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* History */}
                <div>
                  <div className="text-xs font-medium text-zinc-500 mb-2">最近交易记录</div>
                  <div className="overflow-x-auto rounded border border-zinc-200">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs">日期</TableHead>
                          <TableHead className="text-xs">代码</TableHead>
                          <TableHead className="text-xs text-right">买入</TableHead>
                          <TableHead className="text-xs text-right">卖出</TableHead>
                          <TableHead className="text-xs text-right">净额</TableHead>
                          <TableHead className="text-xs text-right">涨幅</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {traderDetail.history.map((h, j) => (
                          <TableRow key={j}>
                            <TableCell className="text-xs text-zinc-400">{h.trade_date.slice(5)}</TableCell>
                            <TableCell className="text-xs font-mono">{h.code}</TableCell>
                            <TableCell className="text-xs text-right text-red-600">{fmtWan(h.buy_amount)}</TableCell>
                            <TableCell className="text-xs text-right text-green-600">{fmtWan(h.sell_amount)}</TableCell>
                            <TableCell className={cn("text-xs text-right font-semibold", h.net >= 0 ? "text-red-600" : "text-green-600")}>
                              {fmtWan(h.net)}
                            </TableCell>
                            <TableCell className={cn("text-xs text-right", colorPct(h.stock_change_pct))}>
                              {fmtPct(h.stock_change_pct)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function fmtYi(v: number): string {
  if (!v) return '-';
  return `${(v / 100000000).toFixed(2)}亿`;
}

function CoOccurrencePanel() {
  const [items, setItems] = useState<{ trader_a: string; trader_b: string; co_count: number; total_buy_a: number; total_buy_b: number }[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.dragonTigerCoOccurrence(30).then(data => {
      setItems(data || []);
    }).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex justify-center py-4">
      <div className="w-4 h-4 rounded-full border-2 border-red-200 border-t-red-600 animate-spin" />
    </div>
  );

  if (items.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs">游资协同网络（近30天，≥2次共同上榜）</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {items.slice(0, 15).map((c, i) => (
            <div key={i} className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-zinc-50 dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800">
              <span className="font-medium">{c.trader_a.slice(0, 6)}</span>
              <span className="text-zinc-400">↔</span>
              <span className="font-medium">{c.trader_b.slice(0, 6)}</span>
              <Badge variant="default" className="text-xs ml-1">{c.co_count}次</Badge>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
