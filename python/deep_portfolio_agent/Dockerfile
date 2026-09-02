FROM python:3.11-slim

# Thiết lập biến môi trường
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# Đặt thư mục làm việc
WORKDIR /app

# Cài đặt system dependencies nếu cần (VD: cho psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy toàn bộ mã nguồn
COPY . .

# Đặt user non-root để bảo mật
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Lệnh khởi chạy Agent
CMD ["python", "-m", "app.main"]
