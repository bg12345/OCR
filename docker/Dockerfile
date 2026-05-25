FROM python:3.14-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NLTK_DATA=/usr/local/share/nltk_data

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel \
    && sed 's/^opencv-python$/opencv-python-headless/' requirements.txt > requirements-docker.txt \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements-docker.txt \
    && /opt/venv/bin/python -m nltk.downloader -d /usr/local/share/nltk_data stopwords punkt_tab


FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSERACT_PATH=/usr/bin/tesseract \
    POPPLER_PATH=/usr/bin \
    NLTK_DATA=/usr/local/share/nltk_data \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libzbar0 \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-hin \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /usr/local/share/nltk_data /usr/local/share/nltk_data
COPY . .

EXPOSE 5000

CMD ["python", "run.py"]
