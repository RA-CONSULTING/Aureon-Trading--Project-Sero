FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home entry
COPY public_entry.py ./
# Supplied from the VM only after generating its TLS key locally. Public
# certificate only; the explicit Docker COPY list cannot include the key.
COPY bridge-cert.pem ./bridge-cert.pem
USER 10001
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 4 --timeout 90 --limit-request-field_size 32768 --access-logfile /dev/null --error-logfile - 'public_entry:create_app()'"]
