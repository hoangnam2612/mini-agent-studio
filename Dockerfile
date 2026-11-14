# ---- Stage 1: Build ----
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
# Cài vào /install rồi chép sang /usr/local — bản cũ cài vào /root/.local nên user
# không phải root (appuser) không đọc được uvicorn (Permission denied).
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: Production ----
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY --from=builder /install /usr/local

# Security: run as non-root user
RUN useradd -m appuser

# Copy application code
COPY . .

# Create data directory with correct ownership
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# --proxy-headers: lấy IP thật từ X-Forwarded-For do Caddy gửi (giới hạn đăng nhập theo IP).
# Cổng 8000 chỉ mở cho mạng compose và 127.0.0.1 nên tin mọi proxy là chấp nhận được.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
