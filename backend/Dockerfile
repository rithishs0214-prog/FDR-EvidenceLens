# Backend image. Build context = the backend/ folder (set "Root Directory: backend" on Render).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# The Tesseract PROGRAM (pytesseract is only a wrapper) - this is why Vercel serverless cannot run the OCR.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -m appuser && mkdir -p /app/data/uploads && chown -R appuser /app
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}"]
