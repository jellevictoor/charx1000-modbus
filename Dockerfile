FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv pip install --system --no-cache pymodbus paho-mqtt

# Copy application
COPY read_energy_meters.py ./

# Run with unbuffered output for proper Docker logging
CMD ["python", "-u", "read_energy_meters.py"]
