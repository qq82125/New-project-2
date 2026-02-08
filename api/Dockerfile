FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY api /app/api
COPY migrations /app/migrations

ENV PYTHONPATH=/app/api

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
