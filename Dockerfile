# Use Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Set working directory
WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install uv

# Copy project configuration files and source directory
COPY pyproject.toml README.md uv.lock ./
COPY src/ ./src/

# Install dependencies using uv
# We copy pyproject.toml and use it to install the environment
RUN uv pip install --system -e .

# Copy application source code
COPY . .

# Ensure storage/temp directories exist for uploads/PDF generation
RUN mkdir -p /tmp/reports

# Expose the Railway provided port
EXPOSE ${PORT}

# Run the FastAPI server
CMD ["python", "server.py"]
