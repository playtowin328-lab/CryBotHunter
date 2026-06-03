import React from "react";
import { createRoot } from "react-dom/client";
import { Activity, BarChart3, Bot, KeyRound, Play, RefreshCw, Settings, ShieldAlert, Terminal } from "lucide-react";
import { api, Dashboard, LogEntry, MarketCoin } from "./api/client";
import "./styles.css";

type View = "dashboard" | "market" | "logs" | "settings";

function App() {
  const [view, setView] = React.useState<View>("dashboard");
  const [tokenReady, setTokenReady] = React.useState(Boolean(localStorage.getItem("token")));
  const [email, setEmail] = React.useState("demo@example.com");
  const [password, setPassword] = React.useState("password123");

  async function login(mode: "login" | "register") {
    const { data } = await api.post(`/auth/${mode}`, { email, password });
    localStorage.setItem("token", data.access_token);
    setTokenReady(true);
  }

  if (!tokenReady) {
    return (
      <main className="min-h-screen bg-panel text-ink">
        <section className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 px-5">
          <div>
            <h1 className="text-3xl font-semibold tracking-normal">Crypto AI Trader</h1>
            <p className="mt-2 text-sm text-slate-600">Trading control panel</p>
          </div>
          <label className="field">
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="field">
            Password
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          <div className="flex gap-2">
            <button className="btn primary flex-1" onClick={() => login("login")}>
              <KeyRound size={16} /> Login
            </button>
            <button className="btn flex-1" onClick={() => login("register")}>
              Register
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-panel text-ink">
      <nav className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3">
          <div className="flex items-center gap-2 font-semibold">
            <Bot size={20} /> Crypto AI Trader
          </div>
          <div className="flex gap-1">
            <NavButton active={view === "dashboard"} onClick={() => setView("dashboard")} icon={<Activity size={16} />} label="Dashboard" />
            <NavButton active={view === "market"} onClick={() => setView("market")} icon={<BarChart3 size={16} />} label="Market" />
            <NavButton active={view === "logs"} onClick={() => setView("logs")} icon={<Terminal size={16} />} label="Logs" />
            <NavButton active={view === "settings"} onClick={() => setView("settings")} icon={<Settings size={16} />} label="Settings" />
          </div>
        </div>
      </nav>
      <div className="mx-auto max-w-7xl px-5 py-5">
        {view === "dashboard" && <DashboardView />}
        {view === "market" && <MarketView />}
        {view === "logs" && <LogsView />}
        {view === "settings" && <SettingsView />}
      </div>
    </main>
  );
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
  const load = React.useCallback(async () => setData((await api.get("/dashboard")).data), []);
  React.useEffect(() => void load(), [load]);

  async function runTrading() {
    await api.post("/trading/run-once");
    await load();
  }

  return (
    <section className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="section-title">Dashboard</h2>
        <button className="btn primary" onClick={runTrading}>
          <Play size={16} /> Run scan
        </button>
      </div>
      <div className="grid gap-3 md:grid-cols-5">
        <Metric label="Balance" value={`$${fmt(data?.balance)}`} />
        <Metric label="PnL day" value={`$${fmt(data?.pnl_day)}`} />
        <Metric label="PnL week" value={`$${fmt(data?.pnl_week)}`} />
        <Metric label="Win Rate" value={`${fmt(data?.win_rate)}%`} />
        <Metric label="Trades" value={String(data?.trades_count ?? 0)} />
      </div>
      <div className="table-wrap">
        <div className="table-title">Active Positions</div>
        <table>
          <thead>
            <tr><th>Coin</th><th>Entry</th><th>Current</th><th>PnL</th><th></th></tr>
          </thead>
          <tbody>
            {(data?.active_positions ?? []).map((position) => (
              <tr key={position.id}>
                <td>{position.symbol}</td>
                <td>${fmt(position.entry_price)}</td>
                <td>${fmt(position.current_price)}</td>
                <td className={position.pnl >= 0 ? "text-accent" : "text-danger"}>${fmt(position.pnl)}</td>
                <td><button className="btn compact" onClick={async () => { await api.post(`/positions/${position.id}/close`); await load(); }}>Close</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function MarketView() {
  const [coins, setCoins] = React.useState<MarketCoin[]>([]);
  const load = React.useCallback(async () => setCoins((await api.get("/market/scan")).data), []);
  React.useEffect(() => void load(), [load]);
  return (
    <section className="space-y-5">
      <div className="flex items-center justify-between">
        <h2 className="section-title">Market Scanner</h2>
        <button className="btn" onClick={load}><RefreshCw size={16} /> Refresh</button>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Coin</th><th>Price</th><th>24h Volume</th><th>Change</th><th>RSI</th><th>EMA50/200</th><th>Rating</th></tr>
          </thead>
          <tbody>
            {coins.map((coin) => (
              <tr key={coin.symbol}>
                <td>{coin.symbol}</td>
                <td>${fmt(coin.price)}</td>
                <td>${fmt(coin.volume_24h)}</td>
                <td className={coin.price_change_percent >= 0 ? "text-accent" : "text-danger"}>{fmt(coin.price_change_percent)}%</td>
                <td>{fmt(coin.rsi)}</td>
                <td>{fmt(coin.ema50)} / {fmt(coin.ema200)}</td>
                <td><span className="score">{coin.rating}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function LogsView() {
  const [logs, setLogs] = React.useState<LogEntry[]>([]);
  React.useEffect(() => void api.get("/logs").then(({ data }) => setLogs(data)), []);
  return (
    <section className="space-y-5">
      <h2 className="section-title">Logs</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Time</th><th>Level</th><th>Message</th></tr></thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}><td>{new Date(log.created_at).toLocaleString()}</td><td>{log.level}</td><td>{log.message}</td></tr>
            ))}
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
    take_profit_percent: 3
  });

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
        take_profit_percent: data.take_profit_percent
      }));
    });
  }, []);

  function update<K extends keyof typeof settings>(key: K, value: (typeof settings)[K]) {
    setSettings((current) => ({ ...current, [key]: value }));
  }

  async function save() {
    await api.put("/settings", settings);
    setSettings((current) => ({ ...current, api_key: "", secret_key: "", passphrase: "" }));
  }

  return (
    <section className="grid gap-5 lg:grid-cols-2">
      <div className="panel-block">
        <h2 className="section-title">Exchange Keys</h2>
        <label className="field">Exchange<select value={settings.exchange} onChange={(event) => update("exchange", event.target.value)}><option value="binance">Binance</option><option value="bybit">Bybit</option></select></label>
        <label className="field">API Key<input type="password" value={settings.api_key} onChange={(event) => update("api_key", event.target.value)} placeholder="masked after save" /></label>
        <label className="field">Secret Key<input type="password" value={settings.secret_key} onChange={(event) => update("secret_key", event.target.value)} placeholder="masked after save" /></label>
        <label className="field">Passphrase<input type="password" value={settings.passphrase} onChange={(event) => update("passphrase", event.target.value)} placeholder="optional" /></label>
        <button className="btn primary" onClick={save}><ShieldAlert size={16} /> Save encrypted</button>
      </div>
      <div className="panel-block">
        <h2 className="section-title">Risk</h2>
        <label className="field">Risk per trade<input type="number" value={settings.risk_percent} onChange={(event) => update("risk_percent", Number(event.target.value))} /></label>
        <label className="field">Daily risk<input type="number" value={settings.daily_risk_percent} onChange={(event) => update("daily_risk_percent", Number(event.target.value))} /></label>
        <label className="field">Max positions<input type="number" value={settings.max_positions} onChange={(event) => update("max_positions", Number(event.target.value))} /></label>
        <label className="field">Minimum rating<input type="number" value={settings.min_rating} onChange={(event) => update("min_rating", Number(event.target.value))} /></label>
        <label className="field">Stop loss<input type="number" value={settings.stop_loss_percent} onChange={(event) => update("stop_loss_percent", Number(event.target.value))} /></label>
        <label className="field">Take profit<input type="number" value={settings.take_profit_percent} onChange={(event) => update("take_profit_percent", Number(event.target.value))} /></label>
        <label className="field">Scan interval<select value={settings.scan_interval} onChange={(event) => update("scan_interval", event.target.value)}><option value="1m">1m</option><option value="5m">5m</option><option value="15m">15m</option><option value="1h">1h</option></select></label>
      </div>
    </section>
  );
}

function Metric(props: { label: string; value: string }) {
  return <div className="metric"><span>{props.label}</span><strong>{props.value}</strong></div>;
}

function fmt(value: number | undefined) {
  return Number(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

createRoot(document.getElementById("root")!).render(<App />);
