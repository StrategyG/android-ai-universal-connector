# Generic container build for staging behind a trusted HTTPS reverse proxy.
# The gateway intentionally fails closed until OAuth environment values are configured.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    AIC_MCP_BIND_HOST=0.0.0.0 \
    AIC_MCP_PORT=8000

WORKDIR /app

RUN addgroup --system --gid 10001 aic \
    && adduser --system --uid 10001 --ingroup aic --home /nonexistent aic

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()" || exit 1

CMD ["aic-gateway"]
