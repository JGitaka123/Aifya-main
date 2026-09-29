FROM python:3.12-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir uv

# Institutional Knowledge (RAG) runs inside this image now. INSTALL_EMBEDDINGS=1
# (the default) adds the 'embeddings' extra so BGE-M3 semantic vectors keep
# working exactly as they did when this was a separate service; the system
# packages cover PyMuPDF and the CPU torch wheel. Build with
# --build-arg INSTALL_EMBEDDINGS=0 for a much smaller image, in which case the
# auto embedding backend falls back to the hashed (lexical) embedding.
ARG INSTALL_EMBEDDINGS=1
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN if [ "$INSTALL_EMBEDDINGS" = "1" ]; then \
        uv pip install --system --no-cache ".[embeddings]" ; \
    else \
        uv pip install --system --no-cache . ; \
    fi

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
