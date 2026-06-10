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

# Install dependencies
COPY pyproject.toml .
RUN pip install --upgrade pip
RUN pip install .

# Copy project
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Run the bot
CMD ["python", "-m", "stayssh.bot.main"]
