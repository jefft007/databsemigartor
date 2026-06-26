FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build deps for common DB drivers
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential default-libmysqlclient-dev libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements (if present) and install
COPY requirements.txt ./requirements.txt
COPY backend/requirements.txt ./backend/requirements.txt

RUN pip install --upgrade pip
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi
RUN if [ -f backend/requirements.txt ]; then pip install --no-cache-dir -r backend/requirements.txt; fi

# Copy project
COPY . .

# Default: run tests (override with a different command when running container)
CMD ["pytest", "-q"]
