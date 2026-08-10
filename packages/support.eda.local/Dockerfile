FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app/support \
    SUPPORT_CONFIG=/config/default_rules.yaml

COPY support/ /app/support/
COPY support/config/default_rules.yaml /config/default_rules.yaml

RUN useradd --create-home --uid 1000 support \
    && mkdir -p /data/support \
    && chown -R support:support /data/support /config

USER support

CMD ["python3", "-m", "support.runner.main"]
