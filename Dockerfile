FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir 'bcrypt<5'

# Copy app
COPY app/ ./app/
COPY init_db.py .
COPY .turso_url .turso_token ./

# Persistent data directory for SQLite
RUN mkdir -p /data
ENV DATABASE_URL=sqlite:////data/churnguard.db

EXPOSE 8000

CMD python3 init_db.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
