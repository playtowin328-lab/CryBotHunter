# Crypto AI Trader

MVP scaffold for an automated crypto trading system with FastAPI, PostgreSQL, Redis, React, Docker, market scoring, strategy evaluation, risk checks, paper trading, encrypted exchange credentials, logs, and ML/backtesting extension points.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Redis, CCXT-ready services, Pandas, NumPy, APScheduler
- ML: XGBoost, LightGBM, Scikit-Learn dependencies and prediction service interface
- Frontend: React, TypeScript, TailwindCSS, Vite, Axios
- Infrastructure: Docker Compose, Nginx

## Run

1. Copy `.env.example` to `.env`.
2. Replace `JWT_SECRET` and `ENCRYPTION_KEY`.
3. Start services:

```bash
docker compose up --build
```

Open:

- Frontend: http://localhost:5173
- Nginx gateway: http://localhost:8080
- API docs: http://localhost:8000/docs

## Deploy to Railway

Create one Railway project with four services:

- PostgreSQL database
- Redis database
- `backend` service from this GitHub repository with root directory `backend`
- `frontend` service from this GitHub repository with root directory `frontend`
- `telegram-bot` worker service from this GitHub repository with root directory `backend`
- `trader-worker` worker service from this GitHub repository with root directory `backend`

Backend variables:

```env
APP_PROCESS=web
ENVIRONMENT=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
JWT_SECRET=replace-with-long-random-secret
ENCRYPTION_KEY=fernet-key-generated-for-production
PAPER_TRADING=true
LIVE_TRADING_ENABLED=false
EXCHANGE_SANDBOX_ENABLED=true
ALLOW_LIVE_TRADING_WITHOUT_SANDBOX=false
MARKET_DATA_MODE=paper
CORS_ORIGINS=https://your-frontend-domain.up.railway.app
TELEGRAM_BOT_TOKEN=123456:telegram-token-from-botfather
TELEGRAM_ALLOWED_CHAT_IDS=123456789
TRADER_LOOP_SECONDS=60
LLM_PROVIDER=none
OPENAI_API_KEY=
LLM_MODEL=gpt-4.1-mini
AI_COMMITTEE_ENABLED=true
AI_COMMITTEE_MIN_CONSENSUS=0.66
MAX_GROSS_EXPOSURE_PERCENT=300
MAX_SYMBOL_EXPOSURE_PERCENT=100
```

Frontend variables:

```env
VITE_API_BASE_URL=https://your-backend-domain.up.railway.app/api/v1
```

Telegram worker variables:

```env
APP_PROCESS=telegram
ENVIRONMENT=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
JWT_SECRET=the-same-secret-as-backend
ENCRYPTION_KEY=the-same-fernet-key-as-backend
PAPER_TRADING=true
TELEGRAM_BOT_TOKEN=123456:telegram-token-from-botfather
TELEGRAM_ALLOWED_CHAT_IDS=123456789
```

Trader worker variables:

```env
APP_PROCESS=trader
ENVIRONMENT=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
JWT_SECRET=the-same-secret-as-backend
ENCRYPTION_KEY=the-same-fernet-key-as-backend
PAPER_TRADING=true
LIVE_TRADING_ENABLED=false
EXCHANGE_SANDBOX_ENABLED=true
ALLOW_LIVE_TRADING_WITHOUT_SANDBOX=false
MARKET_DATA_MODE=paper
TELEGRAM_BOT_TOKEN=123456:telegram-token-from-botfather
TELEGRAM_ALLOWED_CHAT_IDS=123456789
TRADER_LOOP_SECONDS=60
AI_COMMITTEE_ENABLED=true
AI_COMMITTEE_MIN_CONSENSUS=0.66
MAX_GROSS_EXPOSURE_PERCENT=300
MAX_SYMBOL_EXPOSURE_PERCENT=100
```

Set `MARKET_DATA_MODE=ccxt` to use live exchange market data through CCXT while keeping `PAPER_TRADING=true`. For exchange testnet execution, set `PAPER_TRADING=false`, `LIVE_TRADING_ENABLED=true`, and keep `EXCHANGE_SANDBOX_ENABLED=true`. Keep `ALLOW_LIVE_TRADING_WITHOUT_SANDBOX=false` until live execution is reviewed, tested, and deliberately approved.

Use `POST /api/v1/market/history/ingest` to persist OHLCV candles for backtesting and future ML datasets.

Use `POST /api/v1/strategy-lab/optimize` to run a parameter grid search against stored candles and save the strongest strategy configurations. Use `GET /api/v1/strategy-lab/results` to show the latest optimizer results in the dashboard.

Use `POST /api/v1/agents/analyze` to run the AI Trade Committee: market, trend, momentum, liquidity, volatility, optional LLM, and risk agents. Every agent decision is stored in `agent_decisions` for auditability.

Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY` to enable the optional LLM advisor. It can only advise through structured JSON; it cannot open trades directly.

Use `GET /health/deep` to check database, Redis, panic state, paper mode, market data mode, and LLM provider.

Use `POST /api/v1/trading/panic` to pause new entries and `POST /api/v1/trading/resume` to resume them. Telegram supports `/panic` and `/resume`.

Generate public domains in each Railway service under Settings -> Networking. Keep `PAPER_TRADING=true` until live exchange execution has been reviewed and tested.

Generate `ENCRYPTION_KEY` with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The backend Dockerfile runs migrations on startup and listens on Railway's `$PORT`. The frontend Dockerfile builds static assets and serves them through Nginx on Railway's `$PORT`.

## Telegram Bot

Create a bot with Telegram `@BotFather`, copy the bot token, and set it as `TELEGRAM_BOT_TOKEN`.

To find your chat ID:

1. Temporarily leave `TELEGRAM_ALLOWED_CHAT_IDS` empty.
2. Deploy the `telegram-bot` Railway service.
3. Send `/chatid` to your bot.
4. Copy the returned number into `TELEGRAM_ALLOWED_CHAT_IDS`.
5. Redeploy the `telegram-bot` service.

Supported commands:

- `/start`
- `/chatid`
- `/balance`
- `/stats`
- `/positions`
- `/panic`
- `/resume`
- `/stop`

## Current MVP Behavior

- Uses paper trading by default through `PAPER_TRADING=true`.
- Blocks non-sandbox live exchange execution unless `ALLOW_LIVE_TRADING_WITHOUT_SANDBOX=true` is deliberately set.
- Supports a dedicated `APP_PROCESS=trader` worker that loops automatically, manages open positions, and scans for new entries.
- Registers/logs in users with JWT.
- Stores exchange API keys encrypted and returns only masked values.
- Scans synthetic market data and calculates ratings from volume, trend, volatility, volume growth, and liquidity.
- Produces BUY, SELL, or WAIT signals based on EMA/RSI/price/volume/rating rules.
- Detects market regimes such as trending, ranging, high volatility, and low liquidity before accepting entries.
- Applies risk checks before opening paper positions.
- Blocks entries when portfolio or single-symbol exposure exceeds configured limits.
- Uses the AI Trade Committee as an optional final entry gate before opening positions.
- Opens positions with ATR-aware stop/take planning and moves stops to breakeven after configured R-multiple progress.
- Takes partial profit at a configured R-multiple, reduces remaining exposure, and lets the rest run with breakeven/trailing logic.
- Sends Telegram notifications when a paper position is opened.
- Returns an execution report for every manual scan: scanned, opened, skipped, and decision reasons.
- Manages open positions through `/api/v1/trading/tick`: current price, floating PnL, stop loss, take profit, trailing stop, and close reasons.
- Stores every execution attempt in `orders`, including status, filled amount, average price, fee, and paper slippage.
- Reconciles local order state through `POST /api/v1/orders/reconcile` and Telegram `/reconcile`.
- Runs strategy backtests through `/api/v1/trading/backtest` using stored candles.
- Runs Strategy Lab optimization through `/api/v1/strategy-lab/optimize` and stores top strategy configurations.
- Provides safe AI Trade Committee decisions through `/api/v1/agents/analyze`; agents vote, veto weak setups, and audit every decision while deterministic risk checks remain the gate.
- Supports an optional OpenAI-backed LLM advisor behind `LLM_PROVIDER=openai`; disagreements force WAIT rather than increasing risk.
- Provides panic/resume controls through API and Telegram.
- Provides deep health checks through `/health/deep`.
- Blocks new entries through a performance guard when recent win rate, loss streak, or total profit falls below thresholds.
- Provides system status, sample backtest metrics, and Telegram test notification API.
- Persists positions, trades, signals, settings, and logs.
- Exposes dashboard, market, logs, settings, positions, and trading endpoints.

## Next Production Steps

- Wire `ExchangeClient` to authenticated CCXT clients for Binance and Bybit.
- Add live candle ingestion and persist historical candles for 100,000+ samples.
- Train and version ML models for long/short probability.
- Expand Strategy Lab with walk-forward validation, multi-symbol optimization, and ML feature selection.
- Replace Telegram polling with webhook mode if lower latency is needed.
- Add pytest coverage for strategy, risk manager, auth, and trading engine.
