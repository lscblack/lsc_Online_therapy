FROM python:3.13-slim
WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY pyproject.toml .
COPY app ./app
# CPU-only torch first (sentence-transformers/e5 embeddings); avoids the multi-GB CUDA wheels.
# Set EMBEDDING_PROVIDER=fake only for smoke tests; real RAG needs e5 (model downloads on first use).
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install .
COPY alembic ./alembic
COPY alembic.ini .
EXPOSE 8000
# Behind a gateway set TRUSTED_PROXIES (app limiter) and FORWARDED_ALLOW_IPS (uvicorn).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-127.0.0.1}\""]
