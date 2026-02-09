# Base image (stable with Pyrogram)
FROM python:3.11.8-slim

# Set work directory
WORKDIR /app

# Install system dependencies (IMPORTANT)
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy files
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Optional (Flask keep-alive)
EXPOSE 5000

# Run bot (unbuffered logs)
CMD ["python", "-u", "bot.py"]
