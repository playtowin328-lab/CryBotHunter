# Crypto AI Trader

MVP scaffold for an automated crypto trading system with FastAPI, PostgreSQL, Redis, React, Docker, market scoring, strategy evaluation, risk checks, paper trading, encrypted exchange credentials, logs, and ML/backtesting extension points.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, Redis, CCXT-ready services, Pandas, NumPy, APScheduler
- ML: XGBoost, LightGBM, Scikit-Learn, and an isolated Stable Baselines3 PPO training worker
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

Create one Railway project with these services:

- PostgreSQL database
- Redis database
- `backend` service from this GitHub repository with root directory `backend`
- `frontend` service from this GitHub repository with root directory `frontend`
- `telegram-bot` worker service from this GitHub repository with root directory `backend`
- `trader-worker` worker service from this GitHub repository with root directory `backend`
- `candle-worker` worker service from this GitHub repository with root directory `backend`
- `rl-worker` worker service from this GitHub repository with root directory `backend` and Dockerfile `Dockerfile.rl`

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
MARKET_DATA_MODE=ccxt
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
CANDLE_INGEST_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT
CANDLE_INGEST_TIMEFRAMES=1h
CANDLE_INGEST_LIMIT=500
CANDLE_INGEST_LOOP_SECONDS=300
CANDLE_DATASET_TARGET=5000
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
MARKET_DATA_MODE=ccxt
TELEGRAM_BOT_TOKEN=123456:telegram-token-from-botfather
TELEGRAM_ALLOWED_CHAT_IDS=123456789
TRADER_LOOP_SECONDS=60
SAFETY_CHECK_ENABLED=true
SAFETY_CHECK_SYMBOL=BTC/USDT
SAFETY_RETRY_ATTEMPTS=5
SAFETY_RETRY_INITIAL_SECONDS=2
SAFETY_RETRY_MAX_SECONDS=30
AI_COMMITTEE_ENABLED=true
AI_COMMITTEE_MIN_CONSENSUS=0.66
MAX_GROSS_EXPOSURE_PERCENT=300
MAX_SYMBOL_EXPOSURE_PERCENT=100
```

Candle worker variables:

```env
APP_PROCESS=candles
ENVIRONMENT=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
JWT_SECRET=the-same-secret-as-backend
ENCRYPTION_KEY=the-same-fernet-key-as-backend
PAPER_TRADING=true
MARKET_DATA_MODE=ccxt
CANDLE_INGEST_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT
CANDLE_INGEST_TIMEFRAMES=1h,15m
CANDLE_INGEST_LIMIT=500
CANDLE_INGEST_LOOP_SECONDS=300
CANDLE_DATASET_TARGET=5000
```

`PAPER_TRADING=true` controls order execution only. Paper orders and balances remain virtual while `MARKET_DATA_MODE=ccxt` reads real public exchange prices and candles. The legacy value `MARKET_DATA_MODE=paper` is treated as the same real public feed for backward compatibility. Synthetic data is available only with the explicit value `MARKET_DATA_MODE=synthetic` and must never be used by the RL trainer.

For exchange testnet execution, set `PAPER_TRADING=false`, `LIVE_TRADING_ENABLED=true`, and keep `EXCHANGE_SANDBOX_ENABLED=true`. Keep `ALLOW_LIVE_TRADING_WITHOUT_SANDBOX=false` until live execution is reviewed, tested, and deliberately approved.

For a live `trader-worker`, add the same exchange credentials that were saved through the web settings as Railway worker secrets and enable the private pre-flight:

```env
API_KEY=your-exchange-api-key
API_SECRET=your-exchange-secret
SAFETY_REQUIRE_API_CREDENTIALS=true
SAFETY_VALIDATE_PRIVATE_API=true
```

Do not add exchange secrets to the frontend or RL worker. In paper mode the pre-flight reads real public Binance time and `BTC/USDT` ticker data, but orders and balances remain virtual. In live mode it logs a prominent warning, requires both credentials, and validates them with `fetch_balance`. Invalid environment values, malformed exchange data, authentication failures, or exhausted network retries terminate the worker with exit code `1`, so Railway cannot start trading in a partially configured state. `SIGTERM` and `SIGINT` stop future loop iterations, interrupt PPO training through a Stable Baselines3 callback, and close tracked CCXT clients.

RL worker variables:

```env
APP_PROCESS=rl
ENVIRONMENT=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
JWT_SECRET=the-same-secret-as-backend
ENCRYPTION_KEY=the-same-fernet-key-as-backend
PAPER_TRADING=true
LIVE_TRADING_ENABLED=false
MARKET_DATA_MODE=ccxt
DEFAULT_EXCHANGE=binance
CANDLE_INGEST_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT
CANDLE_INGEST_TIMEFRAMES=1h
RL_TRAINER_ENABLED=true
RL_GATE_ENABLED=true
RL_TRAINING_TIMESTEPS=20000
RL_TRAINING_LIMIT=5000
RL_MIN_TRAINING_CANDLES=2000
RL_TRAINING_SEEDS=7,29
RL_REFRESH_HOURS=24
RL_PREDICTION_LOOP_SECONDS=300
SAFETY_CHECK_ENABLED=true
SAFETY_CHECK_SYMBOL=BTC/USDT
SAFETY_RETRY_ATTEMPTS=5
SAFETY_RETRY_INITIAL_SECONDS=2
SAFETY_RETRY_MAX_SECONDS=30
RL_VALIDATION_PERCENT=25
RL_MIN_VALIDATION_RETURN_PERCENT=0
RL_MIN_VALIDATION_PROFIT_FACTOR=1.05
RL_MIN_VALIDATION_TRADES=5
RL_MAX_VALIDATION_DRAWDOWN_PERCENT=15
RL_GATE_MIN_CONFIDENCE=0.55
RL_GATE_MAX_AGE_HOURS=6
RL_WAIT_RISK_MULTIPLIER=0.5
```

The RL service needs no Binance API key because OHLCV is public. Deploy it in the same Railway region that can reach Binance. Stable Baselines3 and CPU-only PyTorch are installed only by `Dockerfile.rl`; the web, trader, and Telegram images remain smaller.

You can run only the critical pre-flight locally or in a Railway shell with `python -m app.safety_manager`. The `rl` and `trader` entry points run it automatically before starting their work loops; Stable Baselines3 is imported only after the check passes.

Use `POST /api/v1/market/history/ingest` to persist OHLCV candles for one symbol, `POST /api/v1/market/history/ingest/batch` for configured symbols, and `GET /api/v1/market/history/readiness` to inspect dataset coverage for backtesting and future ML datasets.

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
- Uses real public exchange market data in paper mode and records candle provenance so synthetic rows cannot enter RL training.
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
- Runs walk-forward backtests through `/api/v1/trading/backtest/walk-forward` to validate optimized parameters on unseen windows.
- Runs Strategy Lab optimization through `/api/v1/strategy-lab/optimize` and stores top strategy configurations.
- Trains multiple seeded PPO candidates on older real candles, validates them chronologically on unseen candles with fees and slippage, and promotes only candidates that pass return, profit-factor, trade-count, and drawdown gates.
- Publishes promoted PPO decisions through the shared database; the trading engine uses them only as a veto or risk reducer behind deterministic risk controls.
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
- Accumulate a longer multi-timeframe real-market dataset and monitor model drift across market regimes.
- Expand Strategy Lab with multi-symbol optimization, ML feature selection, and automated model promotion rules.
- Replace Telegram polling with webhook mode if lower latency is needed.
- Add pytest coverage for strategy, risk manager, auth, and trading engine.
