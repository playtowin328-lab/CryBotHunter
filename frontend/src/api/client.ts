import axios from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v1"
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export type Position = {
  id: number;
  symbol: string;
  side: string;
  entry_price: number;
  current_price: number;
  volume: number;
  stop: number;
  take: number;
  trailing_stop_percent: number;
  highest_price: number;
  lowest_price: number;
  pnl: number;
  status: string;
  exit_reason?: string | null;
  entered_at: string;
  closed_at?: string | null;
};

export type Order = {
  id: number;
  exchange_order_id?: string | null;
  symbol: string;
  side: string;
  order_type: string;
  status: string;
  requested_amount: number;
  filled_amount: number;
  requested_price?: number | null;
  average_price?: number | null;
  fee: number;
  slippage: number;
  created_at: string;
};

export type Dashboard = {
  balance: number;
  pnl_day: number;
  pnl_week: number;
  win_rate: number;
  trades_count: number;
  active_positions: Position[];
};

export type TradingDecision = {
  symbol: string;
  signal: "BUY" | "SELL" | "WAIT";
  score: number;
  action: "OPENED" | "SKIPPED";
  reason: string;
};

export type TradingRun = {
  scanned: number;
  opened: number;
  skipped: number;
  decisions: TradingDecision[];
};

export type TradingTick = {
  checked: number;
  closed: number;
  updated: Array<{
    id: number;
    symbol: string;
    side: string;
    previous_price: number;
    current_price: number;
    pnl: number;
    status: string;
    exit_reason?: string | null;
    stop: number;
    take: number;
  }>;
};

export type SystemStatus = {
  paper_trading: boolean;
  exchange: string;
  telegram_enabled: boolean;
  telegram_chat_count: number;
  open_positions: number;
  daily_pnl: number;
};

export type PerformanceGuard = {
  allowed: boolean;
  reason: string;
  trades_checked: number;
  win_rate: number;
  loss_streak: number;
  total_profit: number;
};

export type BacktestReport = {
  win_rate: number;
  profit_factor: number;
  sharpe_ratio: number;
  max_drawdown: number;
  average_profit: number;
  average_loss: number;
  trades_count: number;
  total_profit: number;
};

export type HistoryIngest = {
  symbol: string;
  timeframe: string;
  inserted: number;
};

export type StrategyOptimization = {
  id?: number | null;
  symbol: string;
  timeframe: string;
  parameters: Record<string, number>;
  score: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown: number;
  total_profit: number;
  trades_count: number;
  created_at?: string | null;
};

export type ActionMessage = {
  ok: boolean;
  message: string;
};

export type AgentDecision = {
  agent_name: string;
  symbol: string;
  action: "BUY" | "SELL" | "WAIT" | "ALLOW" | "REDUCE_SIZE" | "BLOCK";
  confidence: number;
  rationale: string;
  context: Record<string, unknown>;
};

export type AgentAnalysis = {
  symbol: string;
  market: AgentDecision;
  llm?: AgentDecision | null;
  risk: AgentDecision;
  final_action: "BUY" | "SELL" | "WAIT" | "BLOCK";
  final_confidence: number;
  approved: boolean;
};

export type MarketCoin = {
  symbol: string;
  price: number;
  volume_24h: number;
  price_change_percent: number;
  rsi: number;
  ema50: number;
  ema200: number;
  rating: number;
};

export type LogEntry = {
  id: number;
  level: string;
  message: string;
  created_at: string;
};
