FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies for WeasyPrint and audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  python3-dev \
  python3-cffi \
  libcairo2 \
  libpango-1.0-0 \
  libpangocairo-1.0-0 \
  libharfbuzz0b \
  libpangoft2-1.0-0 \
  libffi-dev \
  shared-mime-info \
  curl \
  && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Production image
FROM python:3.12-slim

WORKDIR /app

# Install runtime-only system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
  libcairo2 \
  libpango-1.0-0 \
  libpangocairo-1.0-0 \
  libharfbuzz0b \
  libpangoft2-1.0-0 \
  shared-mime-info \
  curl \
  && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create unprivileged user
RUN useradd -m -r aifya && chown -R aifya:aifya /app
USER aifya

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
