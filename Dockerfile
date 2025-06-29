FROM ghcr.io/astral-sh/uv:python3.13-bookworm

LABEL maintainer="Tim Molteno <tim@elec.ac.nz>"

# Set environment variables for uv and Python
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Create app directory
WORKDIR /app

# Copy only requirements first for maximum caching
COPY requirements.txt ./

# Create virtual environment and install dependencies
# This layer will be cached unless requirements.txt changes
RUN uv venv && \
    uv pip install -r requirements.txt

# Copy pyproject.toml if it exists (optional, for future use)
COPY pyproject.toml* ./

# Copy application code last (changes most frequently)
COPY ./app/ /app/

# Expose port
EXPOSE 8876

# Run the application using the installed waitress
CMD [".venv/bin/waitress-serve", "--port", "8876", "restful_api:app"]