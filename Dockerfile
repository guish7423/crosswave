FROM python:3.12-slim
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN addgroup --system --gid 1001 crosswave && \
    adduser --system --uid 1001 --gid 1001 --no-create-home crosswave

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire project
COPY app/ app/
COPY hq/ hq/
COPY templates/ templates/
COPY static/ static/
COPY index.html scripts/ docker-start.sh ./

# Fix permissions for non-root user
RUN chown -R crosswave:crosswave /app

# Switch to non-root user
USER crosswave

# Ports: 9999 CrossWave app, 13001 HQ bridge
EXPOSE 9999 13001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-9999}/health || curl -f http://localhost:${HQ_PORT:-13001}/health || exit 1

CMD bash docker-start.sh
