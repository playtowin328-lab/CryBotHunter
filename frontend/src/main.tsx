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
import { ActionMessage, AgentAnalysis, AgentDecision, api, BacktestReport, Dashboard, HistoryBatchIngest, HistoryIngest, HistoryReadiness, LogEntry, MarketCoin, Order, PerformanceGuard, StrategyOptimization, SystemStatus, TradingRun, TradingTick, UserSettings, WalkForwardReport } from "./api/client";
import "./styles.css";

type View = "dashboard" | "market" | "agents" | "logs" | "settings";

function App() {
  const [view, setView] = React.useState<View>("dashboard");
  const [tokenReady, setTokenReady] = React.useState(Boolean(localStorage.getItem("token")));
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
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
            <h1>Крипто AI Трейдер</h1>
            <p>Панель управления торговым ботом с paper-режимом, проверками риска и Telegram-операциями.</p>
          </div>
          {error && <Alert tone="danger" text={error} />}
          <label className="field">
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" />
          </label>
          <label className="field">
            Пароль
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Минимум 8 символов" />
          </label>
          <div className="action-row">
            <button className="btn primary flex-1" onClick={() => login("login")}><KeyRound size={16} /> Войти</button>
            <button className="btn flex-1" onClick={() => login("register")}>Регистрация</button>
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
            <NavButton active={view === "dashboard"} onClick={() => setView("dashboard")} icon={<Activity size={16} />} label="Панель" />
            <NavButton active={view === "market"} onClick={() => setView("market")} icon={<BarChart3 size={16} />} label="Рынок" />
            <NavButton active={view === "agents"} onClick={() => setView("agents")} icon={<Bot size={16} />} label="Агенты" />
            <NavButton active={view === "logs"} onClick={() => setView("logs")} icon={<Terminal size={16} />} label="Логи" />
            <NavButton active={view === "settings"} onClick={() => setView("settings")} icon={<Settings size={16} />} label="Настройки" />
            <button className="icon-btn" onClick={logout} title="Выйти"><LogOut size={16} /></button>
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
      <Header title="AI-агенты" subtitle="Рыночные и риск-решения с полной историей проверок">
        <button className="btn primary" onClick={analyze} disabled={loading}><Bot size={16} /> {loading ? "Анализирую" : "Анализ BTC"}</button>
      </Header>
      {error && <Alert tone="danger" text={error} />}
      {analysis && (
        <div className="status-strip">
          <StatusItem label="Итоговое действие" value={translateAction(analysis.final_action)} good={analysis.approved} />
          <StatusItem label="Уверенность" value={`${fmt(analysis.final_confidence * 100)}%`} />
          <StatusItem label="Консенсус" value={`${fmt(analysis.consensus_score * 100)}%`} good={analysis.consensus_score >= 0.66} />
          <StatusItem label="Рыночный агент" value={translateAction(analysis.market.action)} good={analysis.market.action !== "WAIT"} />
          <StatusItem label="AI-советник" value={analysis.llm ? translateAction(analysis.llm.action) : "Выкл"} good={!analysis.llm || analysis.llm.action !== "WAIT"} />
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
            <div className="table-title">Торговый комитет</div>
            <table>
              <thead><tr><th>Агент</th><th>Голос</th><th>Уверенность</th><th>Причина</th></tr></thead>
              <tbody>
                {analysis.committee.map((item) => (
                  <tr key={item.agent_name}>
                    <td>{item.agent_name}</td>
                    <td><ActionPill action={item.action} /></td>
                    <td>{fmt(item.confidence * 100)}%</td>
                    <td>{item.rationale}</td>
                  </tr>
                ))}
                {!analysis.committee.length && <EmptyRow cols={4} text="Голосов комитета пока нет" />}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div className="table-wrap">
        <div className="table-title">Последние решения агентов</div>
        <table>
          <thead><tr><th>Агент</th><th>Пара</th><th>Действие</th><th>Уверенность</th><th>Обоснование</th></tr></thead>
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
            {!decisions.length && <EmptyRow cols={5} text="Решений агентов пока нет" />}
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
        <Metric label="Уверенность" value={`${fmt(decision.confidence * 100)}%`} />
        <p className="muted">{decision.rationale}</p>
      </div>
    </div>
  );
}

function ActionPill({ action }: { action: AgentDecision["action"] }) {
  const tone = action === "BUY" || action === "ALLOW" ? "buy" : action === "SELL" || action === "BLOCK" ? "sell" : "";
  return <span className={`pill ${tone}`}>{translateAction(action)}</span>;
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
  const [walkForward, setWalkForward] = React.useState<WalkForwardReport | null>(null);
  const [historyResult, setHistoryResult] = React.useState<HistoryIngest | null>(null);
  const [batchHistory, setBatchHistory] = React.useState<HistoryBatchIngest | null>(null);
  const [readiness, setReadiness] = React.useState<HistoryReadiness[]>([]);
  const [run, setRun] = React.useState<TradingRun | null>(null);
  const [tick, setTick] = React.useState<TradingTick | null>(null);
  const [error, setError] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      setError("");
      const [dashboardRes, statusRes, guardRes, backtestRes, ordersRes, optimizationsRes, readinessRes] = await Promise.all([
        api.get("/dashboard"),
        api.get("/trading/status"),
        api.get("/trading/guard"),
        api.get("/trading/backtest/sample"),
        api.get("/orders"),
        api.get("/strategy-lab/results"),
        api.get("/market/history/readiness")
      ]);
      setData(dashboardRes.data);
      setStatus(statusRes.data);
      setGuard(guardRes.data);
      setBacktest(backtestRes.data);
      setOrders(ordersRes.data);
      setOptimizations(optimizationsRes.data);
      setReadiness(readinessRes.data);
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

  async function runWalkForward() {
    try {
      setLoading(true);
      setError("");
      const symbol = encodeURIComponent("BTC/USDT");
      const { data } = await api.post<WalkForwardReport>(`/trading/backtest/walk-forward?symbol=${symbol}&timeframe=1h&limit=1000`);
      setWalkForward(data);
    } catch (err) {
      setError(readError(err));
    } finally {
      setLoading(false);
    }
  }

  async function ingestBatchHistory() {
    try {
      setLoading(true);
      setError("");
      const { data } = await api.post<HistoryBatchIngest>("/market/history/ingest/batch");
      setBatchHistory(data);
      setReadiness((await api.get<HistoryReadiness[]>("/market/history/readiness")).data);
    } catch (err) {
      setError(readError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-5">
      <Header title="Панель" subtitle="Портфель, риск-состояние и сводка работы бота">
        <button className="btn" onClick={load}><RefreshCw size={16} /> Обновить</button>
        <button className="btn" onClick={loadHistoryAndBacktest} disabled={loading}><BarChart3 size={16} /> Бэктест BTC</button>
        <button className="btn" onClick={runWalkForward} disabled={loading}><BarChart3 size={16} /> Walk-forward</button>
        <button className="btn" onClick={ingestBatchHistory} disabled={loading}><RefreshCw size={16} /> Загрузить свечи</button>
        <button className="btn" onClick={optimizeStrategy} disabled={loading}><Settings size={16} /> Оптимизировать</button>
        <button className="btn" onClick={managePositions} disabled={loading}><Activity size={16} /> Проверить позиции</button>
        <button className="btn primary" onClick={runTrading} disabled={loading}><Play size={16} /> {loading ? "Запуск" : "Сканировать"}</button>
      </Header>
      {error && <Alert tone="danger" text={error} />}
      <div className="status-strip">
        <StatusItem label="Режим" value={status?.paper_trading ? "Paper-торговля" : "Live-торговля"} good={status?.paper_trading ?? true} />
        <StatusItem label="Биржа" value={status?.exchange ?? "-"} />
        <StatusItem label="Telegram" value={status?.telegram_enabled ? `${status.telegram_chat_count} чат` : "Отключен"} good={Boolean(status?.telegram_enabled)} />
        <StatusItem label="Открытые позиции" value={String(status?.open_positions ?? 0)} />
        <StatusItem
          label="Экспозиция"
          value={`${fmt(status?.gross_exposure_percent)}%`}
          good={(status?.gross_exposure_percent ?? 0) <= (status?.max_gross_exposure_percent ?? 300)}
        />
        <StatusItem label="Комитет" value={status?.ai_committee_enabled ? `${fmt((status.ai_committee_min_consensus ?? 0) * 100)}%` : "Выкл"} good={status?.ai_committee_enabled ?? true} />
        <StatusItem label="Защита" value={guard?.allowed ? "Разрешено" : "Заблокировано"} good={guard?.allowed ?? true} />
      </div>
      <div className="metric-grid">
        <Metric label="Баланс" value={`$${fmt(data?.balance)}`} />
        <Metric label="PnL за день" value={`$${fmt(data?.pnl_day)}`} tone={(data?.pnl_day ?? 0) >= 0 ? "good" : "bad"} />
        <Metric label="PnL за неделю" value={`$${fmt(data?.pnl_week)}`} />
        <Metric label="Win Rate" value={`${fmt(data?.win_rate)}%`} />
        <Metric label="Сделки" value={String(data?.trades_count ?? 0)} />
      </div>
      {run && (
        <div className="panel-block">
          <div className="table-title">Последний запуск: просканировано {run.scanned}, открыто {run.opened}, пропущено {run.skipped}</div>
          <DecisionList run={run} />
        </div>
      )}
      {tick && (
        <Alert
          tone={tick.closed > 0 ? "good" : "good"}
          text={`Менеджер позиций проверил ${tick.checked}, закрыл ${tick.closed}, обновил ${tick.updated.length}.`}
        />
      )}
      <div className="two-col">
        <PositionsTable data={data} onChanged={load} />
        <div className="panel-block">
          <div className="table-title">Бэктест</div>
          {historyResult && <p className="muted">Загружено {historyResult.inserted} новых свечей {historyResult.timeframe} для {historyResult.symbol}.</p>}
          <div className="mini-grid">
            <Metric label="Win Rate" value={`${fmt(backtest?.win_rate)}%`} />
            <Metric label="Profit Factor" value={fmt(backtest?.profit_factor)} />
            <Metric label="Сделки" value={String(backtest?.trades_count ?? 0)} />
            <Metric label="Общая прибыль" value={`$${fmt(backtest?.total_profit)}`} tone={(backtest?.total_profit ?? 0) >= 0 ? "good" : "bad"} />
            <Metric label="Макс. просадка" value={`$${fmt(backtest?.max_drawdown)}`} tone="bad" />
            <Metric label="Средняя прибыль" value={`$${fmt(backtest?.average_profit)}`} tone="good" />
          </div>
          {walkForward && (
            <>
              <div className="table-title mt-4">Walk-forward</div>
              <div className="mini-grid">
                <Metric label="Окна" value={`${walkForward.profitable_windows}/${walkForward.window_count}`} />
                <Metric label="WF прибыль" value={`$${fmt(walkForward.total_profit)}`} tone={walkForward.total_profit >= 0 ? "good" : "bad"} />
                <Metric label="Среднее окно" value={`$${fmt(walkForward.average_window_profit)}`} />
                <Metric label="Средний Win Rate" value={`${fmt(walkForward.average_win_rate)}%`} />
                <Metric label="Средний PF" value={fmt(walkForward.average_profit_factor)} />
                <Metric label="Худшая просадка" value={`$${fmt(walkForward.max_drawdown)}`} tone="bad" />
              </div>
            </>
          )}
        </div>
      </div>
      <OrdersTable orders={orders} onChanged={load} />
      <ReadinessTable items={readiness} batch={batchHistory} />
      <OptimizationTable items={optimizations} />
    </section>
  );
}

function ReadinessTable({ items, batch }: { items: HistoryReadiness[]; batch: HistoryBatchIngest | null }) {
  return (
    <div className="table-wrap">
      <div className="table-title">Готовность датасета</div>
      {batch && <p className="muted">Последняя пачка добавила свечей: {Object.values(batch.inserted).reduce((sum, value) => sum + value, 0)}.</p>}
      <table>
        <thead>
          <tr><th>Пара</th><th>Таймфрейм</th><th>Свечи</th><th>Покрытие</th><th>Статус</th><th>Последняя свеча</th></tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={`${item.symbol}-${item.timeframe}`}>
              <td className="font-semibold">{item.symbol}</td>
              <td>{item.timeframe}</td>
              <td>{item.candles.toLocaleString()}</td>
              <td>{fmt(item.coverage_percent)}%</td>
              <td><span className={`pill ${item.ready ? "buy" : ""}`}>{item.ready ? "Готово" : "Сбор"}</span></td>
              <td>{item.last_timestamp ? new Date(item.last_timestamp).toLocaleString() : "-"}</td>
            </tr>
          ))}
          {!items.length && <EmptyRow cols={6} text="Данных о готовности датасета пока нет" />}
        </tbody>
      </table>
    </div>
  );
}

function OptimizationTable({ items }: { items: StrategyOptimization[] }) {
  return (
    <div className="table-wrap">
      <div className="table-title">Лучшие конфиги Strategy Lab</div>
      <table>
        <thead>
          <tr><th>Пара</th><th>Оценка</th><th>Стоп</th><th>Тейк</th><th>Трейл</th><th>Win Rate</th><th>Profit Factor</th><th>Итого</th></tr>
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
          {!items.length && <EmptyRow cols={8} text="Запусти оптимизацию, чтобы получить конфиги стратегии" />}
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
        <span>Аудит исполнения</span>
        <button className="btn compact" onClick={reconcile}>Сверить</button>
      </div>
      <table>
        <thead>
          <tr><th>Время</th><th>Пара</th><th>Сторона</th><th>Статус</th><th>Исполнено</th><th>Средняя цена</th><th>Комиссия</th><th>Проскальзывание</th></tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr key={order.id}>
              <td>{new Date(order.created_at).toLocaleString()}</td>
              <td className="font-semibold">{order.symbol}</td>
              <td><span className={`pill ${order.side === "buy" ? "buy" : "sell"}`}>{translateAction(order.side)}</span></td>
              <td>{translateStatus(order.status)}</td>
              <td>{fmt(order.filled_amount)}</td>
              <td>${fmt(order.average_price ?? 0)}</td>
              <td>${fmt(order.fee)}</td>
              <td>${fmt(order.slippage)}</td>
            </tr>
          ))}
          {!orders.length && <EmptyRow cols={8} text="Ордеров пока нет" />}
        </tbody>
      </table>
    </div>
  );
}

function PositionsTable(props: { data: Dashboard | null; onChanged: () => Promise<void> }) {
  const positions = props.data?.active_positions ?? [];
  return (
    <div className="table-wrap">
      <div className="table-title">Активные позиции</div>
      <table>
        <thead>
          <tr><th>Монета</th><th>Сторона</th><th>Вход</th><th>Стоп</th><th>Тейк</th><th>PnL</th><th></th></tr>
        </thead>
        <tbody>
          {positions.map((position) => (
            <tr key={position.id}>
              <td className="font-semibold">{position.symbol}</td>
              <td><span className={`pill ${position.side === "LONG" ? "buy" : "sell"}`}>{translateAction(position.side)}</span></td>
              <td>${fmt(position.entry_price)}</td>
              <td>${fmt(position.stop)}</td>
              <td>${fmt(position.take)}</td>
              <td className={position.pnl >= 0 ? "text-accent" : "text-danger"}>${fmt(position.pnl)}</td>
              <td><button className="btn compact" onClick={async () => { await api.post(`/positions/${position.id}/close`); await props.onChanged(); }}>Закрыть</button></td>
            </tr>
          ))}
          {!positions.length && <EmptyRow cols={7} text="Активных позиций пока нет" />}
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
          <span className={`pill ${item.signal === "BUY" ? "buy" : item.signal === "SELL" ? "sell" : ""}`}>{translateAction(item.signal)}</span>
          <strong>{item.symbol}</strong>
          <span>оценка {item.score}</span>
          <span className={item.action === "OPENED" ? "text-accent" : "text-slate-500"}>{translateAction(item.action)}</span>
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
      <Header title="Сканер рынка" subtitle="Рейтинг, тренд и снимок индикаторов">
        <button className="btn" onClick={load}><RefreshCw size={16} /> Обновить</button>
      </Header>
      {error && <Alert tone="danger" text={error} />}
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Монета</th><th>Цена</th><th>Объем 24ч</th><th>Изм.</th><th>RSI</th><th>Тренд</th><th>Режим</th><th>Рейтинг</th></tr>
          </thead>
          <tbody>
            {coins.map((coin) => (
              <tr key={coin.symbol}>
                <td className="font-semibold">{coin.symbol}</td>
                <td>${fmt(coin.price)}</td>
                <td>${fmt(coin.volume_24h)}</td>
                <td className={coin.price_change_percent >= 0 ? "text-accent" : "text-danger"}>{fmt(coin.price_change_percent)}%</td>
                <td>{fmt(coin.rsi)}</td>
                <td><span className={`pill ${coin.ema50 > coin.ema200 ? "buy" : "sell"}`}>{coin.ema50 > coin.ema200 ? "Бычий" : "Медвежий"}</span></td>
                <td><span className={`pill ${coin.regime === "TRENDING_UP" ? "buy" : coin.regime === "TRENDING_DOWN" || coin.regime === "HIGH_VOLATILITY" || coin.regime === "LOW_LIQUIDITY" ? "sell" : ""}`} title={coin.regime_reason}>{translateRegime(coin.regime)}</span></td>
                <td><span className="score">{coin.rating}</span></td>
              </tr>
            ))}
            {!coins.length && <EmptyRow cols={8} text="Рыночные данные пока не загружены" />}
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
      <Header title="Логи" subtitle="Сигналы, торговые действия и события системы">
        <button className="btn" onClick={load}><RefreshCw size={16} /> Обновить</button>
      </Header>
      {error && <Alert tone="danger" text={error} />}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Время</th><th>Уровень</th><th>Сообщение</th></tr></thead>
          <tbody>
            {logs.map((log) => (
              <tr key={log.id}><td>{new Date(log.created_at).toLocaleString()}</td><td><span className="pill">{log.level}</span></td><td>{log.message}</td></tr>
            ))}
            {!logs.length && <EmptyRow cols={3} text="Логов пока нет" />}
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
    api_key_masked: null as string | null,
    secret_key_masked: null as string | null,
    passphrase_masked: null as string | null,
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
    void api.get<UserSettings>("/settings").then(({ data }) => {
      setSettings((current) => ({
        ...current,
        exchange: data.exchange,
        api_key_masked: data.api_key_masked ?? null,
        secret_key_masked: data.secret_key_masked ?? null,
        passphrase_masked: data.passphrase_masked ?? null,
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
      const { api_key_masked, secret_key_masked, passphrase_masked, ...payload } = settings;
      void api_key_masked;
      void secret_key_masked;
      void passphrase_masked;
      const { data } = await api.put<UserSettings>("/settings", payload);
      setMessage({ ok: true, message: "Настройки сохранены" });
      setSettings((current) => ({
        ...current,
        api_key: "",
        secret_key: "",
        passphrase: "",
        api_key_masked: data.api_key_masked ?? current.api_key_masked,
        secret_key_masked: data.secret_key_masked ?? current.secret_key_masked,
        passphrase_masked: data.passphrase_masked ?? current.passphrase_masked
      }));
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
      <Header title="Настройки" subtitle="Ключи биржи, риск-модель и проверка Telegram">
        <button className="btn primary" onClick={save}><Save size={16} /> Сохранить</button>
      </Header>
      {error && <Alert tone="danger" text={error} />}
      {message && <Alert tone={message.ok ? "good" : "danger"} text={message.message} />}
      <div className="settings-grid">
        <div className="panel-block">
          <div className="table-title">Подключение Binance</div>
          <p className="muted">
            Здесь подключается реальная биржа. В Binance создай API key с доступом к Futures/Spot, вставь API Key и Secret Key, затем нажми «Сохранить».
          </p>
          <Alert
            tone={settings.api_key_masked && settings.secret_key_masked ? "good" : "danger"}
            text={settings.api_key_masked && settings.secret_key_masked ? `Binance подключен: ${settings.api_key_masked}` : "Binance еще не подключен: добавь API Key и Secret Key"}
          />
          <label className="field">Биржа<select value={settings.exchange} onChange={(event) => update("exchange", event.target.value)}><option value="binance">Binance</option><option value="bybit">Bybit</option></select></label>
          <label className="field">Binance API Key<input type="password" value={settings.api_key} onChange={(event) => update("api_key", event.target.value)} placeholder={settings.api_key_masked ?? "Вставь API Key из Binance"} /></label>
          <label className="field">Binance Secret Key<input type="password" value={settings.secret_key} onChange={(event) => update("secret_key", event.target.value)} placeholder={settings.secret_key_masked ?? "Вставь Secret Key из Binance"} /></label>
          <label className="field">Passphrase<input type="password" value={settings.passphrase} onChange={(event) => update("passphrase", event.target.value)} placeholder={settings.passphrase_masked ?? "Для Binance не нужна"} /></label>
        </div>
        <div className="panel-block">
          <div className="table-title">Контроль риска</div>
          <label className="field">Риск на сделку<input type="number" value={settings.risk_percent} onChange={(event) => update("risk_percent", Number(event.target.value))} /></label>
          <label className="field">Дневной риск<input type="number" value={settings.daily_risk_percent} onChange={(event) => update("daily_risk_percent", Number(event.target.value))} /></label>
          <label className="field">Макс. позиций<input type="number" value={settings.max_positions} onChange={(event) => update("max_positions", Number(event.target.value))} /></label>
          <label className="field">Мин. рейтинг<input type="number" value={settings.min_rating} onChange={(event) => update("min_rating", Number(event.target.value))} /></label>
          <label className="field">Стоп-лосс<input type="number" value={settings.stop_loss_percent} onChange={(event) => update("stop_loss_percent", Number(event.target.value))} /></label>
          <label className="field">Тейк-профит<input type="number" value={settings.take_profit_percent} onChange={(event) => update("take_profit_percent", Number(event.target.value))} /></label>
          <label className="field">Трейлинг-стоп<input type="number" value={settings.trailing_stop_percent} onChange={(event) => update("trailing_stop_percent", Number(event.target.value))} /></label>
          <label className="field">ATR множитель стопа<input type="number" value={settings.atr_stop_multiplier} onChange={(event) => update("atr_stop_multiplier", Number(event.target.value))} /></label>
          <label className="field">Risk/Reward<input type="number" value={settings.risk_reward_ratio} onChange={(event) => update("risk_reward_ratio", Number(event.target.value))} /></label>
          <label className="field">Триггер безубытка R<input type="number" value={settings.breakeven_trigger_r} onChange={(event) => update("breakeven_trigger_r", Number(event.target.value))} /></label>
          <label className="field">Отступ безубытка<input type="number" value={settings.breakeven_offset_percent} onChange={(event) => update("breakeven_offset_percent", Number(event.target.value))} /></label>
          <label className="field">Частичный тейк R<input type="number" value={settings.partial_take_profit_r} onChange={(event) => update("partial_take_profit_r", Number(event.target.value))} /></label>
          <label className="field">Частичное закрытие %<input type="number" value={settings.partial_close_percent} onChange={(event) => update("partial_close_percent", Number(event.target.value))} /></label>
          <label className="field">Интервал скана<select value={settings.scan_interval} onChange={(event) => update("scan_interval", event.target.value)}><option value="1m">1m</option><option value="5m">5m</option><option value="15m">15m</option><option value="1h">1h</option></select></label>
        </div>
        <div className="panel-block">
          <div className="table-title">Telegram</div>
          <p className="muted">Токен и разрешенные chat ID настраиваются в переменных Railway. Проверь после деплоя telegram-worker.</p>
          <button className="btn" onClick={testTelegram}><ShieldCheck size={16} /> Отправить тест</button>
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
  return Number(value ?? 0).toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

function translateAction(value: string) {
  const labels: Record<string, string> = {
    BUY: "Купить",
    buy: "Покупка",
    SELL: "Продать",
    sell: "Продажа",
    WAIT: "Ждать",
    ALLOW: "Разрешить",
    REDUCE_SIZE: "Уменьшить объем",
    BLOCK: "Блок",
    OPENED: "Открыто",
    SKIPPED: "Пропущено",
    LONG: "Лонг",
    SHORT: "Шорт"
  };
  return labels[value] ?? value;
}

function translateStatus(value: string) {
  const labels: Record<string, string> = {
    NEW: "Новый",
    FILLED: "Исполнен",
    CANCELLED: "Отменен",
    FAILED: "Ошибка",
    OPEN: "Открыта",
    CLOSED: "Закрыта"
  };
  return labels[value] ?? value;
}

function translateRegime(value: string) {
  const labels: Record<string, string> = {
    TRENDING_UP: "Рост",
    TRENDING_DOWN: "Падение",
    HIGH_VOLATILITY: "Высокая волатильность",
    LOW_LIQUIDITY: "Низкая ликвидность",
    RANGING: "Боковик",
    UNKNOWN: "Неизвестно"
  };
  return labels[value] ?? value;
}

function readError(err: unknown) {
  if (typeof err === "object" && err && "response" in err) {
    const response = (err as { response?: { data?: { detail?: string } } }).response;
    return translateError(response?.data?.detail) ?? "Запрос не выполнен";
  }
  return "Запрос не выполнен";
}

function translateError(value?: string) {
  if (!value) {
    return undefined;
  }
  const labels: Record<string, string> = {
    "Incorrect email or password": "Неверный email или пароль",
    "Email already registered": "Этот email уже зарегистрирован",
    "Registration failed": "Регистрация не удалась",
    "Request failed": "Запрос не выполнен"
  };
  return labels[value] ?? value;
}

createRoot(document.getElementById("root")!).render(<App />);
