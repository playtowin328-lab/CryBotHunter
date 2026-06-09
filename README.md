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
MARKET_DATA_MODE=paper
CORS_ORIGINS=https://your-frontend-domain.up.railway.app
TELEGRAM_BOT_TOKEN=123456:telegram-token-from-botfather
TELEGRAM_ALLOWED_CHAT_IDS=123456789
TRADER_LOOP_SECONDS=60
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
MARKET_DATA_MODE=paper
TELEGRAM_BOT_TOKEN=123456:telegram-token-from-botfather
TELEGRAM_ALLOWED_CHAT_IDS=123456789
TRADER_LOOP_SECONDS=60
```

Set `MARKET_DATA_MODE=ccxt` to use live exchange market data through CCXT while keeping `PAPER_TRADING=true`. Keep `LIVE_TRADING_ENABLED=false` until order execution is reviewed, tested, and deliberately enabled.

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
- `/stop`

## Current MVP Behavior

- Uses paper trading by default through `PAPER_TRADING=true`.
- Supports a dedicated `APP_PROCESS=trader` worker that loops automatically, manages open positions, and scans for new entries.
- Registers/logs in users with JWT.
- Stores exchange API keys encrypted and returns only masked values.
- Scans synthetic market data and calculates ratings from volume, trend, volatility, volume growth, and liquidity.
- Produces BUY, SELL, or WAIT signals based on EMA/RSI/price/volume/rating rules.
- Applies risk checks before opening paper positions.
- Sends Telegram notifications when a paper position is opened.
- Returns an execution report for every manual scan: scanned, opened, skipped, and decision reasons.
- Manages open positions through `/api/v1/trading/tick`: current price, floating PnL, stop loss, take profit, trailing stop, and close reasons.
- Provides system status, sample backtest metrics, and Telegram test notification API.
- Persists positions, trades, signals, settings, and logs.
- Exposes dashboard, market, logs, settings, positions, and trading endpoints.

## Next Production Steps

- Wire `ExchangeClient` to authenticated CCXT clients for Binance and Bybit.
- Add live candle ingestion and persist historical candles for 100,000+ samples.
- Train and version ML models for long/short probability.
- Expand backtesting to replay historical candles.
- Replace Telegram polling with webhook mode if lower latency is needed.
- Add pytest coverage for strategy, risk manager, auth, and trading engine.
