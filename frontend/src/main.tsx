import React from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  Bot,
  CheckCircle2,
  KeyRound,
  LogOut,
  Play,
  RefreshCw,
  Save,
  Settings,
  ShieldCheck,
  Terminal,
  XCircle
} from "lucide-react";
import { ActionMessage, AgentAnalysis, AgentDecision, api, BacktestReport, Dashboard, HistoryIngest, LogEntry, MarketCoin, Order, PerformanceGuard, StrategyOptimization, SystemStatus, TradingRun, TradingTick } from "./api/client";
import "./styles.css";

type View = "dashboard" | "market" | "agents" | "logs" | "settings";

function App() {
  const [view, setView] = React.useState<View>("dashboard");
  const [tokenReady, setTokenReady] = React.useState(Boolean(localStorage.getItem("token")));
  const [email, setEmail] = React.useState("demo@example.com");
  const [password, setPassword] = React.useState("password123");
  const [error, setError] = React.useState("");

  async function login(mode: "login" | "register") {
    try {
      setError("");
      const { data } = await api.post(`/auth/${mode}`, { email, password });
      localStorage.setItem("token", data.access_token);
      setTokenReady(true);
    } catch (err) {
      setError(readError(err));
    }
  }

  function logout() {
    localStorage.removeItem("token");
    setTokenReady(false);
  }

  if (!tokenReady) {
    return (
      <main className="auth-shell">
        <section className="auth-panel">
          <div>
            <div className="brand-mark"><Bot size={22} /> CryBotHunter</div>
            <h1>Crypto AI Trader</h1>
            <p>Secure trading control panel with paper mode, risk checks and Telegram operations.</p>
          </div>
          {error && <Alert tone="danger" text={error} />}
          <label className="field">
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="field">
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <div className="action-row">
            <button className="btn primary flex-1" onClick={() => login("login")}><KeyRound size={16} /> Login</button>
            <button className="btn flex-1" onClick={() => login("register")}>Register</button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <nav className="topbar">
        <div className="topbar-inner">
          <div className="brand-mark"><Bot size={20} /> CryBotHunter</div>
          <div className="nav-group">
            <NavButton active={view === "dashboard"} onClick={() => setView("dashboard")} icon={<Activity size={16} />} label="Dashboard" />
            <NavButton active={view === "market"} onClick={() => setView("market")} icon={<BarChart3 size={16} />} label="Market" />
            <NavButton active={view === "agents"} onClick={() => setView("agents")} icon={<Bot size={16} />} label="Agents" />
            <NavButton active={view === "logs"} onClick={() => setView("logs")} icon={<Terminal size={16} />} label="Logs" />
            <NavButton active={view === "settings"} onClick={() => setView("settings")} icon={<Settings size={16} />} label="Settings" />
            <button className="icon-btn" onClick={logout} title="Logout"><LogOut size={16} /></button>
          </div>
        </div>
      </nav>
      <div className="page">
        {view === "dashboard" && <DashboardView />}
        {view === "market" && <MarketView />}
        {view === "agents" && <AgentsView />}
        {view === "logs" && <LogsView />}
        {view === "settings" && <SettingsView />}
      </div>
    </main>
  );
}

function AgentsView() {
  const [analysis, setAnalysis] = React.useState<AgentAnalysis | null>(null);
  const [decisions, setDecisions] = React.useState<AgentDecision[]>([]);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      setError("");
      setDecisions((await api.get("/agents/decisions")).data);
    } catch (err) {
      setError(readError(err));
    }
  }, []);

  React.useEffect(() => void load(), [load]);

  async function analyze() {
    try {
      setLoading(true);
      setError("");
      const symbol = encodeURIComponent("BTC/USDT");
      const { data } = await api.post<AgentAnalysis>(`/agents/analyze?symbol=${symbol}`);
      setAnalysis(data);
      await load();
    } catch (err) {
      setError(readError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-5">
      <Header title="AI Agents" subtitle="Structured market and risk decisions with full audit trail">
        <button className="btn primary" onClick={analyze} disabled={loading}><Bot size={16} /> {loading ? "Analyzing" : "Analyze BTC"}</button>
      </Header>
      {error && <Alert tone="danger" text={error} />}
      {analysis && (
        <div className="status-strip">
          <StatusItem label="Final Action" value={analysis.final_action} good={analysis.approved} />
          <StatusItem label="Confidence" value={`${fmt(analysis.final_confidence * 100)}%`} />
          <StatusItem label="Consensus" value={`${fmt(analysis.consensus_score * 100)}%`} good={analysis.consensus_score >= 0.66} />
          <StatusItem label="Market Agent" value={analysis.market.action} good={analysis.market.action !== "WAIT"} />
          <StatusItem label="AI Advisor" value={analysis.llm?.action ?? "Off"} good={!analysis.llm || analysis.llm.action !== "WAIT"} />
        </div>
      )}
      {analysis && (
        <>
          <div className="two-col">
            <AgentCard decision={analysis.market} />
            {analysis.llm && <AgentCard decision={analysis.llm} />}
            <AgentCard decision={analysis.risk} />
          </div>
          <div className="table-wrap">
            <div className="table-title">Trade Committee</div>
            <table>
              <thead><tr><th>Agent</th><th>Vote</th><th>Confidence</th><th>Reason</th></tr></thead>
              <tbody>
                {analysis.committee.map((item) => (
                  <tr key={item.agent_name}>
                    <td>{item.agent_name}</td>
                    <td><ActionPill action={item.action} /></td>
                    <td>{fmt(item.confidence * 100)}%</td>
                    <td>{item.rationale}</td>
                  </tr>
                ))}
                {!analysis.committee.length && <EmptyRow cols={4} text="No committee votes yet" />}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div className="table-wrap">
        <div className="table-title">Recent Agent Decisions</div>
        <table>
          <thead><tr><th>Agent</th><th>Symbol</th><th>Action</th><th>Confidence</th><th>Rationale</th></tr></thead>
          <tbody>
            {decisions.map((item, index) => (
              <tr key={`${item.agent_name}-${item.symbol}-${index}`}>
                <td>{item.agent_name}</td>
                <td>{item.symbol}</td>
                <td><ActionPill action={item.action} /></td>
                <td>{fmt(item.confidence * 100)}%</td>
                <td>{item.rationale}</td>
              </tr>
            ))}
            {!decisions.length && <EmptyRow cols={5} text="No agent decisions yet" />}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AgentCard({ decision }: { decision: AgentDecision }) {
  return (
    <div className="panel-block">
      <div className="table-title">{decision.agent_name}</div>
      <div className="agent-card-body">
        <ActionPill action={decision.action} />
        <Metric label="Confidence" value={`${fmt(decision.confidence * 100)}%`} />
        <p className="muted">{decision.rationale}</p>
      </div>
    </div>
  );
}

function ActionPill({ action }: { action: AgentDecision["action"] }) {
  const tone = action === "BUY" || action === "ALLOW" ? "buy" : action === "SELL" || action === "BLOCK" ? "sell" : "";
  return <span className={`pill ${tone}`}>{action}</span>;
}

function NavButton(props: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button className={`nav ${props.active ? "active" : ""}`} onClick={props.onClick} title={props.label}>
      {props.icon}
      <span>{props.label}</span>
    </button>
  );
}

function DashboardView() {
  const [data, setData] = React.useState<Dashboard | null>(null);
  const [orders, setOrders] = React.useState<Order[]>([]);
  const [optimizations, setOptimizations] = React.useState<StrategyOptimization[]>([]);
  const [status, setStatus] = React.useState<SystemStatus | null>(null);
  const [guard, setGuard] = React.useState<PerformanceGuard | null>(null);
  const [backtest, setBacktest] = React.useState<BacktestReport | null>(null);
  const [historyResult, setHistoryResult] = React.useState<HistoryIngest | null>(null);
  const [run, setRun] = React.useState<TradingRun | null>(null);
  const [tick, setTick] = React.useState<TradingTick | null>(null);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      setError("");
      const [dashboardRes, statusRes, guardRes, backtestRes, ordersRes, optimizationsRes] = await Promise.all([
        api.get("/dashboard"),
        api.get("/trading/status"),
        api.get("/trading/guard"),
        api.get("/trading/backtest/sample"),
        api.get("/orders"),
        api.get("/strategy-lab/results")
      ]);
      setData(dashboardRes.data);
      setStatus(statusRes.data);
      setGuard(guardRes.data);
      setBacktest(backtestRes.data);
      setOrders(ordersRes.data);
      setOptimizations(optimizationsRes.data);
    } catch (err) {
      setError(readError(err));
    }
  }, []);

  React.useEffect(() => void load(), [load]);

  async function runTrading() {
    try {
      setLoading(true);
      setError("");
      const { data: result } = await api.post<TradingRun>("/trading/run-once");
      setRun(result);
      await load();
    } catch (err) {
      setError(readError(err));
    } finally {
      setLoading(false);
    }
  }

  async function managePositions() {
    try {
      setLoading(true);
      setError("");
      const { data: result } = await api.post<TradingTick>("/trading/tick");
      setTick(result);
      await load();
    } catch (err) {
      setError(readError(err));
    } finally {
      setLoading(false);
    }
  }

  async function loadHistoryAndBacktest() {
    try {
      setLoading(true);
      setError("");
      const symbol = encodeURIComponent("BTC/USDT");
      const { data: history } = await api.post<HistoryIngest>(`/market/history/ingest?symbol=${symbol}&timeframe=1h&limit=500`);
      setHistoryResult(history);
      const { data: report } = await api.post<BacktestReport>(`/trading/backtest?symbol=${symbol}&timeframe=1h&limit=500`);
      setBacktest(report);
    } catch (err) {
      setError(readError(err));
    } finally {
      setLoading(false);
    }
  }

  async function optimizeStrategy() {
    try {
      setLoading(true);
      setError("");
      const symbol = encodeURIComponent("BTC/USDT");
      const { data } = await api.post<StrategyOptimization[]>(`/strategy-lab/optimize?symbol=${symbol}&timeframe=1h&limit=500`);
      setOptimizations(data);
    } catch (err) {
      setError(readError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-5">
      <Header title="Dashboard" subtitle="Portfolio, risk state and bot execution summary">
        <button className="btn" onClick={load}><RefreshCw size={16} /> Refresh</button>
        <button className="btn" onClick={loadHistoryAndBacktest} disabled={loading}><BarChart3 size={16} /> Backtest BTC</button>
        <button className="btn" onClick={optimizeStrategy} disabled={loading}><Settings size={16} /> Optimize</button>
        <button className="btn" onClick={managePositions} disabled={loading}><Activity size={16} /> Manage positions</button>
        <button className="btn primary" onClick={runTrading} disabled={loading}><Play size={16} /> {loading ? "Running" : "Run scan"}</button>
      </Header>
      {error && <Alert tone="danger" text={error} />}
      <div className="status-strip">
        <StatusItem label="Mode" value={status?.paper_trading ? "Paper trading" : "Live trading"} good={status?.paper_trading ?? true} />
        <StatusItem label="Exchange" value={status?.exchange ?? "-"} />
        <StatusItem label="Telegram" value={status?.telegram_enabled ? `${status.telegram_chat_count} chat` : "Disabled"} good={Boolean(status?.telegram_enabled)} />
        <StatusItem label="Open positions" value={String(status?.open_positions ?? 0)} />
        <StatusItem
          label="Exposure"
          value={`${fmt(status?.gross_exposure_percent)}%`}
          good={(status?.gross_exposure_percent ?? 0) <= (status?.max_gross_exposure_percent ?? 300)}
        />
        <StatusItem label="Committee" value={status?.ai_committee_enabled ? `${fmt((status.ai_committee_min_consensus ?? 0) * 100)}%` : "Off"} good={status?.ai_committee_enabled ?? true} />
        <StatusItem label="Guard" value={guard?.allowed ? "Allowed" : "Blocked"} good={guard?.allowed ?? true} />
      </div>
      <div className="metric-grid">
        <Metric label="Balance" value={`$${fmt(data?.balance)}`} />
        <Metric label="PnL day" value={`$${fmt(data?.pnl_day)}`} tone={(data?.pnl_day ?? 0) >= 0 ? "good" : "bad"} />
        <Metric label="PnL week" value={`$${fmt(data?.pnl_week)}`} />
        <Metric label="Win Rate" value={`${fmt(data?.win_rate)}%`} />
        <Metric label="Trades" value={String(data?.trades_count ?? 0)} />
      </div>
      {run && (
        <div className="panel-block">
          <div className="table-title">Last Run: scanned {run.scanned}, opened {run.opened}, skipped {run.skipped}</div>
          <DecisionList run={run} />
        </div>
      )}
      {tick && (
        <Alert
          tone={tick.closed > 0 ? "good" : "good"}
          text={`Position manager checked ${tick.checked} position(s), closed ${tick.closed}, updated ${tick.updated.length}.`}
        />
      )}
      <div className="two-col">
        <PositionsTable data={data} onChanged={load} />
        <div className="panel-block">
          <div className="table-title">Backtest</div>
          {historyResult && <p className="muted">Loaded {historyResult.inserted} new {historyResult.timeframe} candles for {historyResult.symbol}.</p>}
          <div className="mini-grid">
            <Metric label="Win Rate" value={`${fmt(backtest?.win_rate)}%`} />
            <Metric label="Profit Factor" value={fmt(backtest?.profit_factor)} />
            <Metric label="Trades" value={String(backtest?.trades_count ?? 0)} />
            <Metric label="Total Profit" value={`$${fmt(backtest?.total_profit)}`} tone={(backtest?.total_profit ?? 0) >= 0 ? "good" : "bad"} />
            <Metric label="Max Drawdown" value={`$${fmt(backtest?.max_drawdown)}`} tone="bad" />
            <Metric label="Avg Profit" value={`$${fmt(backtest?.average_profit)}`} tone="good" />
          </div>
        </div>
      </div>
      <OrdersTable orders={orders} onChanged={load} />
      <OptimizationTable items={optimizations} />
    </section>
  );
}

function OptimizationTable({ items }: { items: StrategyOptimization[] }) {
  return (
    <div className="table-wrap">
      <div className="table-title">Strategy Lab Top Configs</div>
      <table>
        <thead>
          <tr><th>Symbol</th><th>Score</th><th>Stop</th><th>Take</th><th>Trail</th><th>Win Rate</th><th>Profit Factor</th><th>Total</th></tr>
        </thead>
        <tbody>
          {items.map((item, index) => (
            <tr key={`${item.symbol}-${item.score}-${index}`}>
              <td className="font-semibold">{item.symbol}</td>
              <td>{fmt(item.score)}</td>
              <td>{fmt(item.parameters.stop_loss_percent)}%</td>
              <td>{fmt(item.parameters.take_profit_percent)}%</td>
              <td>{fmt(item.parameters.trailing_stop_percent)}%</td>
              <td>{fmt(item.win_rate)}%</td>
              <td>{fmt(item.profit_factor)}</td>
              <td className={item.total_profit >= 0 ? "text-accent" : "text-danger"}>${fmt(item.total_profit)}</td>
            </tr>
          ))}
          {!items.length && <EmptyRow cols={8} text="Run Optimize to generate strategy configs" />}
        </tbody>
      </table>
    </div>
  );
}

function OrdersTable({ orders, onChanged }: { orders: Order[]; onChanged: () => Promise<void> }) {
  async function reconcile() {
    await api.post("/orders/reconcile");
    await onChanged();
  }
  return (
    <div className="table-wrap">
      <div className="table-title table-title-row">
        <span>Execution Audit Trail</span>
        <button className="btn compact" onClick={reconcile}>Reconcile</button>
      </div>
      <table>
        <thead>
          <tr><th>Time</th><th>Symbol</th><th>Side</th><th>Status</th><th>Filled</th><th>Avg Price</th><th>Fee</th><th>Slippage</th></tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.id}>
              <td>{new Date(order.created_at).toLocaleString()}</td>
              <td className="font-semibold">{order.symbol}</td>
              <td><span className={`pill ${order.side === "buy" ? "buy" : "sell"}`}>{order.side}</span></td>
              <td>{order.status}</td>
              <td>{fmt(order.filled_amount)}</td>
              <td>${fmt(order.average_price ?? 0)}</td>
              <td>${fmt(order.fee)}</td>
              <td>${fmt(order.slippage)}</td>
            </tr>
          ))}
          {!orders.length && <EmptyRow cols={8} text="No orders yet" />}
        </tbody>
      </table>
    </div>
  );
}

function PositionsTable(props: { data: Dashboard | null; onChanged: () => Promise<void> }) {
  const positions = props.data?.active_positions ?? [];
  return (
    <div className="table-wrap">
      <div className="table-title">Active Positions</div>
      <table>
        <thead>
          <tr><th>Coin</th><th>Side</th><th>Entry</th><th>Stop</th><th>Take</th><th>PnL</th><th></th></tr>
        </thead>
        <tbody>
          {positions.map((position) => (
            <tr key={position.id}>
              <td className="font-semibold">{position.symbol}</td>
              <td><span className={`pill ${position.side === "LONG" ? "buy" : "sell"}`}>{position.side}</span></td>
              <td>${fmt(position.entry_price)}</td>
              <td>${fmt(position.stop)}</td>
              <td>${fmt(position.take)}</td>
              <td className={position.pnl >= 0 ? "text-accent" : "text-danger"}>${fmt(position.pnl)}</td>
              <td><button className="btn compact" onClick={async () => { await api.post(`/positions/${position.id}/close`); await props.onChanged(); }}>Close</button></td>
            </tr>
          ))}
          {!positions.length && <EmptyRow cols={7} text="No active positions yet" />}
        </tbody>
      </table>
    </div>
  );
}

function DecisionList({ run }: { run: TradingRun }) {
  return (
    <div className="decision-list">
      {run.decisions.map((item) => (
        <div className="decision" key={item.symbol}>
          <span className={`pill ${item.signal === "BUY" ? "buy" : item.signal === "SELL" ? "sell" : ""}`}>{item.signal}</span>
          <strong>{item.symbol}</strong>
          <span>score {item.score}</span>
          <span className={item.action === "OPENED" ? "text-accent" : "text-slate-500"}>{item.action}</span>
          <span className="truncate">{item.reason}</span>
        </div>
      ))}
    </div>
  );
}

function MarketView() {
  const [coins, setCoins] = React.useState<MarketCoin[]>([]);
  const [error, setError] = React.useState("");
  const load = React.useCallback(async () => {
    try {
      setError("");
      setCoins((await api.get("/market/scan")).data);
    } catch (err) {
      setError(readError(err));
    }
  }, []);
  React.useEffect(() => void load(), [load]);
  return (
    <section className="space-y-5">
      <Header title="Market Scanner" subtitle="Rating, trend and indicator snapshot">
        <button className="btn" onClick={load}><RefreshCw size={16} /> Refresh</button>
      </Header>
      {error && <Alert tone="danger" text={error} />}
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Coin</th><th>Price</th><th>24h Volume</th><th>Change</th><th>RSI</th><th>Trend</th><th>Rating</th></tr>
          </thead>
          <tbody>
            {coins.map((coin) => (
              <tr key={coin.symbol}>
                <td className="font-semibold">{coin.symbol}</td>
                <td>${fmt(coin.price)}</td>
                <td>${fmt(coin.volume_24h)}</td>
                <td className={coin.price_change_percent >= 0 ? "text-accent" : "text-danger"}>{fmt(coin.price_change_percent)}%</td>
                <td>{fmt(coin.rsi)}</td>
                <td><span className={`pill ${coin.ema50 > coin.ema200 ? "buy" : "sell"}`}>{coin.ema50 > coin.ema200 ? "Bull" : "Bear"}</span></td>
                <td><span className="score">{coin.rating}</span></td>
              </tr>
            ))}
            {!coins.length && <EmptyRow cols={7} text="No market data loaded" />}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LogsView() {
  const [logs, setLogs] = React.useState<LogEntry[]>([]);
  const [error, setError] = React.useState("");
  const load = React.useCallback(async () => {
    try {
      setError("");
      setLogs((await api.get("/logs")).data);
    } catch (err) {
      setError(readError(err));
    }
  }, []);
  React.useEffect(() => void load(), [load]);
  return (
    <section className="space-y-5">
      <Header title="Logs" subtitle="Signals, trading actions and operational events">
        <button className="btn" onClick={load}><RefreshCw size={16} /> Refresh</button>
      </Header>
      {error && <Alert tone="danger" text={error} />}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Time</th><th>Level</th><th>Message</th></tr></thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}><td>{new Date(log.created_at).toLocaleString()}</td><td><span className="pill">{log.level}</span></td><td>{log.message}</td></tr>
            ))}
            {!logs.length && <EmptyRow cols={3} text="No logs yet" />}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SettingsView() {
  const [settings, setSettings] = React.useState({
    exchange: "binance",
    api_key: "",
    secret_key: "",
    passphrase: "",
    risk_percent: 1,
    daily_risk_percent: 3,
    max_positions: 3,
    min_rating: 80,
    scan_interval: "5m",
    stop_loss_percent: 1.5,
    take_profit_percent: 3,
    trailing_stop_percent: 0.8,
    atr_stop_multiplier: 1.5,
    risk_reward_ratio: 2,
    breakeven_trigger_r: 1,
    breakeven_offset_percent: 0.05,
    partial_take_profit_r: 1,
    partial_close_percent: 50
  });
  const [message, setMessage] = React.useState<ActionMessage | null>(null);
  const [error, setError] = React.useState("");

  React.useEffect(() => {
    void api.get("/settings").then(({ data }) => {
      setSettings((current) => ({
        ...current,
        exchange: data.exchange,
        risk_percent: data.risk_percent,
        daily_risk_percent: data.daily_risk_percent,
        max_positions: data.max_positions,
        min_rating: data.min_rating,
        scan_interval: data.scan_interval,
        stop_loss_percent: data.stop_loss_percent,
        take_profit_percent: data.take_profit_percent,
        trailing_stop_percent: data.trailing_stop_percent,
        atr_stop_multiplier: data.atr_stop_multiplier,
        risk_reward_ratio: data.risk_reward_ratio,
        breakeven_trigger_r: data.breakeven_trigger_r,
        breakeven_offset_percent: data.breakeven_offset_percent,
        partial_take_profit_r: data.partial_take_profit_r,
        partial_close_percent: data.partial_close_percent
      }));
    }).catch((err) => setError(readError(err)));
  }, []);

  function update<K extends keyof typeof settings>(key: K, value: (typeof settings)[K]) {
    setSettings((current) => ({ ...current, [key]: value }));
  }

  async function save() {
    try {
      setError("");
      await api.put("/settings", settings);
      setMessage({ ok: true, message: "Settings saved" });
      setSettings((current) => ({ ...current, api_key: "", secret_key: "", passphrase: "" }));
    } catch (err) {
      setError(readError(err));
    }
  }

  async function testTelegram() {
    try {
      setError("");
      setMessage((await api.post<ActionMessage>("/settings/telegram/test")).data);
    } catch (err) {
      setError(readError(err));
    }
  }

  return (
    <section className="space-y-5">
      <Header title="Settings" subtitle="Exchange credentials, risk model and Telegram checks">
        <button className="btn primary" onClick={save}><Save size={16} /> Save</button>
      </Header>
      {error && <Alert tone="danger" text={error} />}
      {message && <Alert tone={message.ok ? "good" : "danger"} text={message.message} />}
      <div className="settings-grid">
        <div className="panel-block">
          <div className="table-title">Exchange Keys</div>
          <label className="field">Exchange<select value={settings.exchange} onChange={(event) => update("exchange", event.target.value)}><option value="binance">Binance</option><option value="bybit">Bybit</option></select></label>
          <label className="field">API Key<input type="password" value={settings.api_key} onChange={(event) => update("api_key", event.target.value)} placeholder="masked after save" /></label>
          <label className="field">Secret Key<input type="password" value={settings.secret_key} onChange={(event) => update("secret_key", event.target.value)} placeholder="masked after save" /></label>
          <label className="field">Passphrase<input type="password" value={settings.passphrase} onChange={(event) => update("passphrase", event.target.value)} placeholder="optional" /></label>
        </div>
        <div className="panel-block">
          <div className="table-title">Risk Controls</div>
          <label className="field">Risk per trade<input type="number" value={settings.risk_percent} onChange={(event) => update("risk_percent", Number(event.target.value))} /></label>
          <label className="field">Daily risk<input type="number" value={settings.daily_risk_percent} onChange={(event) => update("daily_risk_percent", Number(event.target.value))} /></label>
          <label className="field">Max positions<input type="number" value={settings.max_positions} onChange={(event) => update("max_positions", Number(event.target.value))} /></label>
          <label className="field">Minimum rating<input type="number" value={settings.min_rating} onChange={(event) => update("min_rating", Number(event.target.value))} /></label>
          <label className="field">Stop loss<input type="number" value={settings.stop_loss_percent} onChange={(event) => update("stop_loss_percent", Number(event.target.value))} /></label>
          <label className="field">Take profit<input type="number" value={settings.take_profit_percent} onChange={(event) => update("take_profit_percent", Number(event.target.value))} /></label>
          <label className="field">Trailing stop<input type="number" value={settings.trailing_stop_percent} onChange={(event) => update("trailing_stop_percent", Number(event.target.value))} /></label>
          <label className="field">ATR stop multiplier<input type="number" value={settings.atr_stop_multiplier} onChange={(event) => update("atr_stop_multiplier", Number(event.target.value))} /></label>
          <label className="field">Risk reward ratio<input type="number" value={settings.risk_reward_ratio} onChange={(event) => update("risk_reward_ratio", Number(event.target.value))} /></label>
          <label className="field">Breakeven trigger R<input type="number" value={settings.breakeven_trigger_r} onChange={(event) => update("breakeven_trigger_r", Number(event.target.value))} /></label>
          <label className="field">Breakeven offset<input type="number" value={settings.breakeven_offset_percent} onChange={(event) => update("breakeven_offset_percent", Number(event.target.value))} /></label>
          <label className="field">Partial take profit R<input type="number" value={settings.partial_take_profit_r} onChange={(event) => update("partial_take_profit_r", Number(event.target.value))} /></label>
          <label className="field">Partial close %<input type="number" value={settings.partial_close_percent} onChange={(event) => update("partial_close_percent", Number(event.target.value))} /></label>
          <label className="field">Scan interval<select value={settings.scan_interval} onChange={(event) => update("scan_interval", event.target.value)}><option value="1m">1m</option><option value="5m">5m</option><option value="15m">15m</option><option value="1h">1h</option></select></label>
        </div>
        <div className="panel-block">
          <div className="table-title">Telegram</div>
          <p className="muted">Token and allowed chat IDs are configured in Railway variables. Use this check after deploying the telegram worker.</p>
          <button className="btn" onClick={testTelegram}><ShieldCheck size={16} /> Send test notification</button>
        </div>
      </div>
    </section>
  );
}

function Header(props: { title: string; subtitle: string; children?: React.ReactNode }) {
  return (
    <div className="header">
      <div>
        <h2>{props.title}</h2>
        <p>{props.subtitle}</p>
      </div>
      <div className="action-row">{props.children}</div>
    </div>
  );
}

function Metric(props: { label: string; value: string; tone?: "good" | "bad" }) {
  return <div className={`metric ${props.tone ?? ""}`}><span>{props.label}</span><strong>{props.value}</strong></div>;
}

function StatusItem(props: { label: string; value: string; good?: boolean }) {
  const icon = props.good === false ? <XCircle size={16} /> : <CheckCircle2 size={16} />;
  return <div className="status-item">{icon}<span>{props.label}</span><strong>{props.value}</strong></div>;
}

function Alert(props: { tone: "good" | "danger"; text: string }) {
  return <div className={`alert ${props.tone}`}>{props.text}</div>;
}

function EmptyRow(props: { cols: number; text: string }) {
  return <tr><td colSpan={props.cols} className="empty">{props.text}</td></tr>;
}

function fmt(value: number | undefined) {
  return Number(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function readError(err: unknown) {
  if (typeof err === "object" && err && "response" in err) {
    const response = (err as { response?: { data?: { detail?: string } } }).response;
    return response?.data?.detail ?? "Request failed";
  }
  return "Request failed";
}

createRoot(document.getElementById("root")!).render(<App />);
