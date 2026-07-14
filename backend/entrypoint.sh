#!/bin/sh
set -e

alembic upgrade head

process=$(printf '%s' "${APP_PROCESS:-web}" | tr -d '"' | tr -d "'")

case "$process" in
  telegram)
    exec python -m app.telegram_worker
    ;;
  trader)
    exec python -m app.trader_worker
    ;;
  candles)
    exec python -m app.candle_worker
    ;;
  optimizer)
    exec python -m app.optimizer_worker
    ;;
  rl)
    exec python -m app.rl_worker
    ;;
  web|"")
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  *)
    echo "Unknown APP_PROCESS=$APP_PROCESS; starting web process"
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
esac
