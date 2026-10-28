FROM python:3.13-slim

WORKDIR /app
COPY app.py ./app.py
COPY static ./static

RUN useradd --system --uid 10001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

ENV HOST=0.0.0.0 \
    PORT=8000 \
    EXPENSE_DB=/data/expense_ai.db

USER appuser
EXPOSE 8000
CMD ["python", "app.py"]
