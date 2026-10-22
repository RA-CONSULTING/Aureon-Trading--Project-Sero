# Aureon Fusion status service. It does not place orders.
# Build from the repository root:
#   docker build -t aureon-fusion:local .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    AUREON_LIVE_TRADING=0 \
    AUREON_FUSION_ARM_LIVE= \
    AUREON_FUSION_BIND=0.0.0.0 \
    AUREON_FUSION_PORT=8765 \
    BINANCE_TESTNET=true \
    PAPER_MODE=true

RUN groupadd -r aureon && useradd -r -g aureon -d /app aureon
WORKDIR /app

COPY --chown=aureon:aureon aureon_fusion /app/aureon_fusion
COPY --chown=aureon:aureon organism /app/organism
COPY --chown=aureon:aureon sources/NEXUS-LIVE-FEED-/organism /app/sources/NEXUS-LIVE-FEED-/organism
COPY --chown=aureon:aureon sources/Aureon-Trading--Project-Sero/organism /app/sources/Aureon-Trading--Project-Sero/organism
COPY --chown=aureon:aureon aureon-os-upstream/aureon/__init__.py /app/aureon-os-upstream/aureon/__init__.py
COPY --chown=aureon:aureon aureon-os-upstream/aureon/organism /app/aureon-os-upstream/aureon/organism
COPY --chown=aureon:aureon aureon-os-upstream/aureon/bio/plant_atlas/__init__.py /app/aureon-os-upstream/aureon/bio/plant_atlas/__init__.py
COPY --chown=aureon:aureon aureon-os-upstream/aureon/strategies/quantum_quackers.py /app/aureon-os-upstream/aureon/strategies/quantum_quackers.py
COPY --chown=aureon:aureon sources/AUREON-QUANTUM-TRADING-SYSTEM-AQTS-/README.md /app/sources/AUREON-QUANTUM-TRADING-SYSTEM-AQTS-/README.md
COPY --chown=aureon:aureon sources/NEXUS-LIVE-FEED-/src/server.js /app/sources/NEXUS-LIVE-FEED-/src/server.js

USER aureon
EXPOSE 8765

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=2).read()"]

ENTRYPOINT ["python", "-m", "aureon_fusion.http_service"]
