FROM python:3.12-slim

WORKDIR /app/api

COPY requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt

# Keep image input minimal: only runtime app package is needed.
COPY app /app/api/app

ENV PYTHONPATH=/app/api

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
