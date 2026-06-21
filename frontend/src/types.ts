export interface ZtStock {
  code: string;
  name: string;
  change_pct: number;
  price: number;
  amount: number;
  circ_mv: number;
  seal_amount: number;
  streak: number;
  first_seal_time: string;
  last_seal_time: string;
  break_count: number;
  industry: string;
}

export interface ZtPoolResponse {
  items: ZtStock[];
  total: number;
  page: number;
  page_size: number;
  date?: string;
  maxStreak: number;
  streakDist: Record<number, number>;
}

export interface Gainer {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  change_amt: number;
  volume: number;
  amount: number;
  high: number;
  low: number;
  open: number;
  pre_close: number;
  turnover: number;
}

export interface HotStock {
  rank: number;
  code: string;
  name: string;
  price: number;
  change_pct: number;
}

export interface TrendSignal {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  score: number;
  signals: { type: string; label: string; weight: number; desc: string }[];
  ma5: number | null;
  ma10: number | null;
  ma20: number | null;
  ma60: number | null;
}

export interface DragonTigerItem {
  code: string;
  name: string;
  date: string;
  reason: string;
  price: number;
  change_pct: number;
  net_buy: number;
  buy_amount: number;
  sell_amount: number;
  total_amount: number;
  net_pct: number;
  turnover: number;
  circ_mv: number;
  buy_seats: number;
  sell_seats: number;
  turnover_ratio: number;
  amplitude: number;
  up_desc: string;
  join_num: number;
  concepts?: string;
}

export interface DragonTigerSeat {
  trade_date: string;
  code: string;
  rank: number;
  trader_name: string;
  trader_type: string;
  group_name: string;
  buy_amount: number;
  sell_amount: number;
  reason_type: string;
}

export interface StockBrief {
  code: string;
  name: string;
}

export interface ConceptStock {
  code: string;
  name: string;
  change_pct: number;
  streak: number;
  reason: string;
  dt_net: number;
  seat_net: number;
  traders: string;
}

export interface DragonTigerGroup {
  group_name: string;
  stock_count: number;
  total_trades: number;
  active_days: number;
  total_buy: number;
  total_sell: number;
  net: number;
  buy_times: number;
  sell_times: number;
  buy_ratio: number;
  win_rate: number;
  codes: string[];
  stocks: StockBrief[];
}

export interface ConceptGroup {
  concept: string;
  stock_count: number;
  codes: string[];
  stocks: ConceptStock[];
  avg_change_pct: number;
  total_seat_net: number;
  max_streak: number;
  leader: ConceptStock | null;
}

export interface FundFlowItem {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  main_net: number;
  main_pct: number;
  super_large_net: number;
  large_net: number;
  mid_net: number;
  small_net: number;
}

export interface NorthBoundData {
  date?: string;
  net_flow?: number;
  balance?: number;
}

export interface SectorItem {
  rank: number;
  name: string;
  code: string;
  price: number;
  change_pct: number;
  total_mv: number;
  turnover: number;
  up_count: number;
  down_count: number;
  top_stock: string;
  top_change_pct: number;
}

export interface SectorStock {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  amount: number;
  turnover: number;
}

export interface KLineItem {
  trade_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
  change_pct: number;
}

export interface MarginSummary {
  stock_count: number;
  total_margin_buy: number;
  total_margin_balance: number;
  total_balance: number;
}


export interface SealQuality {
  time_label: string;
  time_score: number;
  break_label: string;
  break_score: number;
  total_score: number;
  grade: string;
}

export interface ZtAnalysisStock extends ZtStock {
  seal_quality: SealQuality;
  seal_ratio: number | null;
}

export interface IndustryHeat {
  name: string;
  count: number;
  stocks: { code: string; name: string; streak: number }[];
  max_streak: number;
}

export interface TimeBucket {
  label: string;
  count: number;
}

export interface BrokenBoard {
  code: string;
  name: string;
  break_count: number;
  streak: number;
}

export interface ZtAnalysisResponse {
  trade_date: string;
  total: number;
  items: ZtAnalysisStock[];
  industries: IndustryHeat[];
  time_dist: TimeBucket[];
  grade_dist: Record<string, number>;
  broken_boards: BrokenBoard[];
  max_streak: number;
}

export interface MarginHistoryItem {
  trade_date: string;
  margin_balance: number;
  margin_buy: number;
  total_volume: number;
  total_amount: number;
}

// ─── 成交量异动 ───
export interface VolumeAnomalyItem {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  latest_volume: number;
  amount: number;
  avg_vol_short: number;
  avg_vol_base: number;
  volume_ratio: number;
  latest_trade_date?: string;
}

export interface VolumeAnomalyResponse extends PaginatedResponse<VolumeAnomalyItem> {
  data_date?: string;
}

// ─── 两融深度 ───
export interface MarginTrendItem {
  trade_date: string;
  margin_balance: number;
  margin_buy: number;
  short_balance: number;
  stock_price: number;
  change_pct: number;
}

export interface MarginTopChange {
  code: string;
  name: string;
  margin_balance: number;
  margin_buy: number;
  total_balance: number;
  balance_change: number;
  change_pct: number | null;
}

// ─── 低调牛股 ───
export interface QuietBullScores {
  trend: number;
  quiet: number;
  volume: number;
  institution: number;
  pattern: number;
}

export interface QuietBullItem {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  total_score: number;
  scores: QuietBullScores;
  streak_days: number;
  total_pct: number;
}

// ─── 龙虎榜游资 ───
export interface TraderHistoryItem {
  trade_date: string;
  code: string;
  name: string;
  buy_amount: number;
  sell_amount: number;
  net: number;
  stock_change_pct: number;
  post_3d_change: number | null;
}

export interface TraderDetail {
  trader_name: string;
  total_appearances: number;
  total_buy: number;
  total_sell: number;
  net: number;
  avg_net_per_trade: number;
  win_rate_est: number;
  favorite_sectors: string[];
  co_traders: { name: string; co_count: number }[];
  history: TraderHistoryItem[];
}

export interface CoOccurrence {
  trader_a: string;
  trader_b: string;
  co_count: number;
  total_buy_a: number;
  total_buy_b: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ─── 美股→A股联动 ───
export interface UsIndexSnapshot {
  symbol: string;
  name: string;
  close: number | null;
  change_pct: number | null;
  recent_5d: number[];
}

export interface UsCorrelatedStock {
  code: string;
  name: string;
  us_index: string;
  corr_10d: number | null;
  corr_15d: number | null;
  corr_20d: number | null;
  beta: number | null;
  overnight_gap: number | null;
  a_stock_change: number | null;
  us_change: number | null;
}

export interface UsCorrelationResponse {
  indices: UsIndexSnapshot[];
  concepts: UsConceptCard[];
  stocks: UsCorrelatedStock[];
  date: string | null;
  mode: 'concept' | 'stock';
}

// 美股联动 — 概念模式 (v2)
export interface UsConceptCard {
  name: string;
  icon: string;
  us_index: string;
  stock_count: number;
  total_constituents: number;
  avg_corr: number | null;
  std_corr: number | null;
  consistency: number | null;
  composite_score: number | null;
  avg_beta: number | null;
  top_stocks: UsConceptTopStock[];
}

export interface UsConceptTopStock {
  code: string;
  name: string;
  corr: number | null;
  beta: number | null;
  gap: number | null;
  a_chg: number | null;
  amount: number | null;
}

export interface UsCorrelationResponse {
  indices: UsIndexSnapshot[];
  stocks: UsCorrelatedStock[];
  date: string | null;
}

// ─── 回测验证 ───
export interface BacktestConceptResult {
  concept: string;
  index_symbol: string;
  index_name: string;
  samples: number;
  up_avg: number;
  down_avg: number;
  diff_bps: number;
  up_winrate: number;
  down_winrate: number;
  p_value: number;
  significance: 'strong' | 'moderate' | 'weak' | 'none';
  info_ratio: number;
  extreme_up_n: number;
  extreme_up_avg: number | null;
  extreme_down_n: number;
  extreme_down_avg: number | null;
}

export interface BacktestIndexSummary {
  index_symbol: string;
  index_name: string;
  concepts_tested: number;
  avg_diff_bps: number;
  significant_concepts: number;
  best_concept: string;
}

export interface BacktestTimeWindow {
  window_start: string;
  window_end: string;
  n: number;
  diff_bps: number;
  p_value: number;
  up_avg: number;
  down_avg: number;
}

export interface BacktestExtremeBin {
  label: string;
  n: number;
  avg_a_chg: number | null;
  winrate: number | null;
}

export interface BacktestExtremeConcept {
  concept: string;
  bins: BacktestExtremeBin[];
}

export interface BacktestResponse {
  summary: {
    total_tests: number;
    strong_signals: number;
    moderate_signals: number;
    best_signal: BacktestConceptResult;
    data_period: string;
    total_aligned_days: number;
  };
  by_concept: BacktestConceptResult[];
  by_index: BacktestIndexSummary[];
  extreme_analysis: BacktestExtremeConcept[];
  time_stability: BacktestTimeWindow[];
  generated_at: string;
}

// ─── 明日预测 ───
export interface PredictionSignal {
  index_symbol: string;
  index_name: string;
  index_abbr: string;
  us_chg: number;
  expected_a_chg: number;
  confidence: number;
  diff_bps: number;
  p_value: number;
  significance: string;
  up_winrate: number;
  samples: number;
}

export interface PredictionItem {
  concept: string;
  icon: string;
  total_stocks: number;
  signals: PredictionSignal[];
  consensus: number;
  avg_expected: number;
  direction: 'bull' | 'bear' | 'neutral';
  extreme_alert: string;
  best_signal: PredictionSignal;
}

export interface PredictionIndex {
  trade_date: string | null;
  close: number | null;
  change_pct: number | null;
  name: string;
  abbr: string;
}

export interface PredictionResponse {
  generated_at: string;
  us_market_date: string;
  a_market_date: string;
  indices: PredictionIndex[];
  predictions: PredictionItem[];
  disclaimer: string;
}
