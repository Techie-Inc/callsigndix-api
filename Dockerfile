FROM python:3.11-slim

# Create a non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8081

# Run the application
CMD ["python", "main.py"] 