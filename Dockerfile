# ==========================================
# PET_SHOP Python Backend Dockerfile
# Python 3.11-slim - Lightweight & Fast
# ==========================================
FROM python:3.11-slim

WORKDIR /app

# Install curl for docker healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy requirements file first for layer caching
COPY requirements.txt .

# Install python dependencies with timeout and retries for stability
RUN pip install --no-cache-dir --default-timeout=100 --retries=10 -r requirements.txt

# Copy application source code
COPY . .

# Ensure upload directory exists
RUN mkdir -p public/uploads

# Expose backend API port
EXPOSE 5000

ENV PORT=5000
ENV PYTHONUNBUFFERED=1

# Health check to ensure server is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Run Uvicorn ASGI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
