FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home authority
COPY contract.py service.py firestore_ledger.py provider_boundary.py live_executor.py cloud_state.py release_gate.py release_controller.py ./
USER 10001
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 120 --access-logfile /dev/null --error-logfile - \"${AUREON_SERVICE_MODULE:-service}:create_app()\""]

