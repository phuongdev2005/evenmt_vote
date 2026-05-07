FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium
RUN python -m playwright install chromium
RUN python -m playwright install-deps chromium

# Copy all sms_tool files
COPY . .

# Create necessary directories
RUN mkdir -p logs

# Default command
CMD ["python", "main.py", "--help"]
