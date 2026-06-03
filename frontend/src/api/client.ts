import axios from "axios";

export const api = axios.create({
  baseURL: "/api/v1"
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
