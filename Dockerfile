# Use an appropriate base image, e.g., python:3.10-slim
FROM --platform=linux/amd64 python:3.11-slim

# Set environment variables (e.g., set Python to run in unbuffered mode)
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Copy your application's requirements and install them
COPY requirements.txt /app/

# Install Python dependencies without caching pip packages
RUN pip install -U -r /app/requirements.txt

# Copy your application code into the container
COPY . /app/

EXPOSE 8080

# Run as a non-root user
RUN useradd -m appuser && \
    chown -R appuser:appuser /app
USER appuser

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Run chainlit 
CMD ["python", "-m", "chainlit", "run", "chainlit-app.py", "-h", "--port", "8080"]