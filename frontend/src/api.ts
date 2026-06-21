import type { ZtPoolResponse, Gainer, HotStock, TrendSignal, DragonTigerItem, DragonTigerSeat, FundFlowItem, NorthBoundData, SectorItem, SectorStock, KLineItem, DragonTigerGroup, ConceptGroup, PaginatedResponse, MarginSummary, ZtAnalysisResponse, MarginHistoryItem, VolumeAnomalyItem, VolumeAnomalyResponse, MarginTrendItem, MarginTopChange, QuietBullItem, TraderDetail, CoOccurrence, UsCorrelationResponse } from './types';

const BASE = '/api';

const get = async <T>(url: string): Promise<T> => {
  const r = await fetch(BASE + url);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
};

export const post = async <T>(url: string, body?: unknown): Promise<T> => {
  const r = await fetch(BASE + url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
};

function qs(page: number, pageSize: number): string {
  return `page=${page}&page_size=${pageSize}`;
}

export const api = {
  // 涨停
  ztToday: (page = 1, pageSize = 100, date?: string) =>
    get<ZtPoolResponse>(`/hot-stocks/zt-today?${qs(page, pageSize)}${date ? `&date=${date}` : ''}`),
  ztAnalysis: (date?: string) =>
    get<ZtAnalysisResponse>(`/hot-stocks/zt-analysis${date ? `?date=${date}` : ''}`),
  gainersRank: (page = 1, pageSize = 20) =>
    get<PaginatedResponse<Gainer>>(`/hot-stocks/rank?${qs(page, pageSize)}`),
  hotRank: (page = 1, pageSize = 20) =>
    get<PaginatedResponse<HotStock>>(`/hot-stocks/hot?${qs(page, pageSize)}`),

  // 趋势战法
  trendToday: (page = 1, pageSize = 20) =>
    get<PaginatedResponse<TrendSignal>>(`/trend-signals/today?${qs(page, pageSize)}`),
  trendSymbol: (symbol: string) => get<TrendSignal>(`/trend-signals/${symbol}`),

  // 龙虎榜/资金
  dragonTiger: (page = 1, pageSize = 20, date?: string) =>
    get<PaginatedResponse<DragonTigerItem>>(`/dragon-tiger/today?${qs(page, pageSize)}${date ? `&date=${date}` : ''}`),
  dragonTigerSeats: (code: string) => get<DragonTigerSeat[]>(`/dragon-tiger/seats/${code}`),
  dragonTigerByTrader: (days = 5) => get<DragonTigerGroup[]>(`/dragon-tiger/grouped-by-trader?days=${days}`),
  dragonTigerByConcept: () => get<ConceptGroup[]>('/dragon-tiger/grouped-by-concept'),
  fundFlow: (page = 1, pageSize = 20) =>
    get<PaginatedResponse<FundFlowItem>>(`/dragon-tiger/fund-flow?${qs(page, pageSize)}`),
  northBound: () => get<NorthBoundData>('/dragon-tiger/north-bound'),

  // 板块
  sectorRank: (page = 1, pageSize = 50) =>
    get<PaginatedResponse<SectorItem>>(`/sectors/rank?${qs(page, pageSize)}`),
  sectorStocks: (code: string, page = 1, pageSize = 30) =>
    get<PaginatedResponse<SectorStock>>(`/sectors/${code}/stocks?${qs(page, pageSize)}`),

  // K线
  stockKline: (code: string, days = 60) => get<KLineItem[]>(`/stock-kline/${code}?days=${days}`),

  // 两融
  marginSummary: () => get<MarginSummary>('/margin/summary'),
  marginHistory: (days = 120) => get<MarginHistoryItem[]>(`/margin/history?days=${days}`),
  marginTrend: (code: string, days = 60) => get<MarginTrendItem[]>(`/margin/trend/${code}?days=${days}`),
  marginTopChanges: (period = 'weekly', direction = 'increase', limit = 10) =>
    get<MarginTopChange[]>(`/margin/top-changes?period=${period}&direction=${direction}&limit=${limit}`),
  marginSectorSummary: () => get<{ sector_code: string; total_margin: number; stock_count: number }[]>('/margin/sector-summary'),

  // 成交量异动
  volumeAnomaly: (params: { days?: number; base_days?: number; min_ratio?: number; exclude_zt?: boolean; page?: number; page_size?: number }) => {
    const { days = 5, base_days = 50, min_ratio = 2.0, exclude_zt = true, page = 1, page_size = 20 } = params;
    return get<VolumeAnomalyResponse>(
      `/volume-anomaly?page=${page}&page_size=${page_size}&days=${days}&base_days=${base_days}&min_ratio=${min_ratio}&exclude_zt=${exclude_zt}`
    );
  },

  // 低调牛股
  quietBulls: (page = 1, pageSize = 20, minScore = 50) =>
    get<PaginatedResponse<QuietBullItem>>(`/quiet-bulls?page=${page}&page_size=${pageSize}&min_score=${minScore}`),

  // 龙虎榜游资
  dragonTigerTraderDetail: (name: string) =>
    get<TraderDetail>(`/dragon-tiger/trader/${encodeURIComponent(name)}`),
  dragonTigerCoOccurrence: (days = 30) =>
    get<CoOccurrence[]>(`/dragon-tiger/co-occurrence?days=${days}`),

  // 美股→A股联动（默认概念模式）
  usCorrelation: (usIndex = 'all', top = 20, mode: 'concept' | 'stock' = 'concept', period = '10d') =>
    get<UsCorrelationResponse>(`/us-correlation?us_index=${usIndex}&top=${top}&mode=${mode}&period=${period}`),
};
