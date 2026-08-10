FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Create non-root user for security
RUN useradd -m -u 1000 mcpuser

# Set working directory
WORKDIR /app

# Install pinned runtime dependencies.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy main entrypoint
COPY main.py /app/main.py

# Switch to non-root user
USER mcpuser

EXPOSE 8080
EXPOSE 8000

# Run the MCP server via main.py
CMD ["python", "main.py"]
