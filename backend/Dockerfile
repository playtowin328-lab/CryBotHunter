FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "alembic upgrade head && if [ \"$APP_PROCESS\" = \"telegram\" ]; then python -m app.telegram_worker; elif [ \"$APP_PROCESS\" = \"trader\" ]; then python -m app.trader_worker; elif [ \"$APP_PROCESS\" = \"candles\" ]; then python -m app.candle_worker; elif [ \"$APP_PROCESS\" = \"optimizer\" ]; then python -m app.optimizer_worker; else uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
