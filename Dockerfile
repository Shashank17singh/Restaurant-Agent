# Use the official Python image
FROM python:3.12-slim

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Set the working directory
WORKDIR /app

# Copy the dependency files and project metadata
COPY pyproject.toml uv.lock README.md ./

# Install dependencies using uv
# This creates a virtual environment at /app/.venv
RUN uv sync --frozen --no-dev

# Copy the rest of the application code
COPY . .

# Ensure the virtual environment's bin directory is in the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Default port (Cloud Run sets this automatically to 8080)
ENV PORT=8000
EXPOSE $PORT

# Start the FastAPI server on 0.0.0.0 to allow external connections
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
