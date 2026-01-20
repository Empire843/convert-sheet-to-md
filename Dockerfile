FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy web application
COPY web/ ./web/

# Create volumes for input and output
VOLUME ["/app/uploads", "/app/output"]

# Set Python path
ENV PYTHONPATH=/app

# Expose port for web server
EXPOSE 5000

# Run web server
CMD ["python", "web/app.py"]
