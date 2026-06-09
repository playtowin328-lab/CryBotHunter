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

Backend variables:

```env
ENVIRONMENT=production
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
JWT_SECRET=replace-with-long-random-secret
ENCRYPTION_KEY=fernet-key-generated-for-production
PAPER_TRADING=true
CORS_ORIGINS=https://your-frontend-domain.up.railway.app
```

Frontend variables:

```env
VITE_API_BASE_URL=https://your-backend-domain.up.railway.app/api/v1
```

Generate public domains in each Railway service under Settings -> Networking. Keep `PAPER_TRADING=true` until live exchange execution has been reviewed and tested.

Generate `ENCRYPTION_KEY` with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

The backend Dockerfile runs migrations on startup and listens on Railway's `$PORT`. The frontend Dockerfile builds static assets and serves them through Nginx on Railway's `$PORT`.

## Current MVP Behavior

- Uses paper trading by default through `PAPER_TRADING=true`.
- Registers/logs in users with JWT.
- Stores exchange API keys encrypted and returns only masked values.
- Scans synthetic market data and calculates ratings from volume, trend, volatility, volume growth, and liquidity.
- Produces BUY, SELL, or WAIT signals based on EMA/RSI/price/volume/rating rules.
- Applies risk checks before opening paper positions.
- Persists positions, trades, signals, settings, and logs.
- Exposes dashboard, market, logs, settings, positions, and trading endpoints.

## Next Production Steps

- Wire `ExchangeClient` to authenticated CCXT clients for Binance and Bybit.
- Add live candle ingestion and persist historical candles for 100,000+ samples.
- Train and version ML models for long/short probability.
- Expand backtesting to replay historical candles.
- Add Telegram bot runtime and webhook/polling setup.
- Add pytest coverage for strategy, risk manager, auth, and trading engine.
