# Multi-stage build for optimized image size
FROM python:3.12-slim as base

# Install system dependencies including Java for tabula-py
RUN apt-get update && apt-get install -y \
    default-jre \
    default-jdk \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set Java home
ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for batch results and logs
RUN mkdir -p batch_results tabula_tables

# Expose port
EXPOSE 8010

# Set environment variables
ENV PORT=8010
ENV PYTHONUNBUFFERED=1
ENV MONGO_DB_NAME=scp_verification_dev
ENV OLLAMA_MODEL=ollama/qwen2.5:7b
ENV OLLAMA_BASE_URL=http://127.0.0.1:11434
ENV OLLAMA_API_KEY=ollama
ENV LLM_TIMEOUT=600

# MinIO configuration (optional, can be overridden)
ENV MINIO_ENDPOINT=""
ENV MINIO_ACCESS_KEY=""
ENV MINIO_SECRET_KEY=""
ENV MINIO_BUCKET_NAME=""
ENV MINIO_REGION=""
ENV MINIO_SECURE=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8010/docs || exit 1

# Run the application
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8010"]

