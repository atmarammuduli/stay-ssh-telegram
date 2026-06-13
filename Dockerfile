# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    tmux \
    openssh-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies and package
COPY pyproject.toml .
COPY tmux_ssh_telegram ./tmux_ssh_telegram
RUN pip install --upgrade pip
RUN pip install .

# Copy remaining project files (tests, docs, etc.)
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Copy entrypoint
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Run the bot
ENTRYPOINT ["./entrypoint.sh"]
