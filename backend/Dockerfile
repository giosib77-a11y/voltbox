# syntax=docker/dockerfile:1
# მრავალსაფეხურიანი build — საბოლოო იმიჯში კომპილატორი და dev-პაკეტები არ რჩება.
FROM python:3.14-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build

COPY pyproject.toml README.md ./
COPY app ./app
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip && /opt/venv/bin/pip install .

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# root-ით არასდროს არ ვუშვებთ პროცესს
RUN useradd --create-home --uid 1000 voltbox
WORKDIR /srv/app

COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

USER voltbox
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').status==200 else 1)"

# gunicorn + uvicorn worker — გრეისფული რესტარტისა და worker-ების მართვისთვის
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "--timeout", "60", "--graceful-timeout", "30"]
