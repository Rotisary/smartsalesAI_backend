FROM python:3.12-slim
 
WORKDIR /project
 
# Install system dependencies needed by pdfplumber and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
 
COPY requirements.txt .
RUN pip install -r requirements.txt
 
COPY . .
 