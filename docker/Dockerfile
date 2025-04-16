FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies needed for the API server
RUN pip install --no-cache-dir uvicorn[standard] gunicorn

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data logs

# Expose the API port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV PYTHONUNBUFFERED=1

# Set default command
CMD ["python", "-m", "src.shelly_manager.interfaces.api.server"] 