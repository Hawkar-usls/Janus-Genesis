FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GENESIS_HOSTED_DATA_DIR=/data \
    GENESIS_HOSTED_BIND=0.0.0.0 \
    GENESIS_HOSTED_PORT=8787

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN useradd --create-home --uid 10001 genesis \
    && mkdir -p /data \
    && chown -R genesis:genesis /data /app

USER genesis

EXPOSE 8787

CMD ["python", "tools/genesis_hosted_gateway.py", "--data-dir", "/data"]
