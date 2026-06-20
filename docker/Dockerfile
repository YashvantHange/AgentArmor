FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md /app/
COPY agentarmor /app/agentarmor
COPY benchmarks /app/benchmarks
COPY native /app/native

RUN pip install --no-cache-dir ".[ml]" \
    && python -m agentarmor.cli.main models download

ENV AGENTARMOR_MODEL_DIR=/root/.agentarmor/models
ENV AGENTARMOR_CONFIG=/app/AgentArmor.toml

COPY AgentArmor.toml /app/AgentArmor.toml

EXPOSE 8787

CMD ["python", "-m", "agentarmor.cli.main", "serve", "--host", "0.0.0.0", "--port", "8787", "--model-dir", "/root/.agentarmor/models"]
