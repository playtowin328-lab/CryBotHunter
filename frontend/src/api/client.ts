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
  pnl: number;
  status: string;
  entered_at: string;
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

export type SystemStatus = {
  paper_trading: boolean;
  exchange: string;
  telegram_enabled: boolean;
  telegram_chat_count: number;
  open_positions: number;
  daily_pnl: number;
};

export type BacktestReport = {
  win_rate: number;
  profit_factor: number;
  sharpe_ratio: number;
  max_drawdown: number;
  average_profit: number;
  average_loss: number;
};

export type ActionMessage = {
  ok: boolean;
  message: string;
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
