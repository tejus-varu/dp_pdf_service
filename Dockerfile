# Dockerfile at dp_pdf_service/Dockerfile

FROM python:3.10-slim
# (you can try 3.11-slim later if everything works, but 3.10 is safer for libs)

# Install system deps for Tesseract + PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    poppler-utils \
  && rm -rf /var/lib/apt/lists/*

# Work dir in container
WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Environment
ENV PYTHONUNBUFFERED=1 \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata/

# IMPORTANT: Render sets $PORT at runtime; use it, with fallback to 8000 for local dev
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
