# Johny Sins - Production Docker image
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application (excluding dev/git via .dockerignore)
COPY . .

# Create data directory and non-root user for security
RUN mkdir -p /app/data && chown -R 1000:1000 /app
USER 1000

EXPOSE 8000

# Healthcheck for orchestrators (Kubernetes, Docker Swarm, etc.)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# Production: no reload, single worker (scheduler runs in-process)
ENV ENVIRONMENT=production
ENV PORT=8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
