#!/bin/sh
set -e

process=$(printf '%s' "${APP_PROCESS:-web}" | tr -d '"' | tr -d "'")

case "$process" in
  telegram|trader|candles|optimizer|rl|web|"")
    ;;
  *)
    echo "Unknown APP_PROCESS=$APP_PROCESS" >&2
    exit 64
    ;;
esac

run_migrations=$(printf '%s' "${RUN_MIGRATIONS:-}" | tr -d '"' | tr -d "'" | tr '[:upper:]' '[:lower:]')
if [ -z "$run_migrations" ]; then
  case "$process" in
    web|"") run_migrations=true ;;
    *) run_migrations=false ;;
  esac
fi

case "$run_migrations" in
  1|true|yes|on)
    alembic upgrade head
    ;;
  0|false|no|off)
    ;;
  *)
    echo "RUN_MIGRATIONS must be true or false" >&2
    exit 64
    ;;
esac

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
esac
