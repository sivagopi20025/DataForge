FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system dataforge && adduser --system --ingroup dataforge dataforge

COPY pyproject.toml README.md ./
COPY backend ./backend
COPY config ./config
COPY dataforge ./dataforge
COPY retail_generator.py ./retail_generator.py

RUN pip install --upgrade pip && pip install \
    "fastapi>=0.115" \
    "pydantic>=2.9" \
    "pydantic-settings>=2.6" \
    "sqlalchemy>=2.0" \
    "alembic>=1.13" \
    "psycopg[binary]>=3.2" \
    "uvicorn>=0.30" \
    "pyarrow>=14" \
    "boto3>=1.34"

RUN mkdir -p /var/lib/dataforge/output && chown -R dataforge:dataforge /var/lib/dataforge /app

USER dataforge

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
