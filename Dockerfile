FROM python:3.10-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock requirements.txt ./

# Install dependencies using requirements.txt (generated from uv)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data && chmod 777 /app/data

# Expose port
EXPOSE 8080

# Increase file descriptor limit
RUN echo "* soft nofile 65536" >> /etc/security/limits.conf && \
    echo "* hard nofile 65536" >> /etc/security/limits.conf

# Health check for Coolify
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/').read()" || exit 1

# Run the application with increased file descriptor limit
CMD ["sh", "-c", "ulimit -n 65536 && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
