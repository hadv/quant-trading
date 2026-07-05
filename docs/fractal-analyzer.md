# Fractal Analyzer

`fractal_analyzer` là một service bằng Python chịu trách nhiệm phân tích động học thị trường thông qua lý thuyết Phân dạng (Fractal Theory) và Hình học Fractal.

## Chức năng cốt lõi
- **Lắng nghe thị trường**: Bắt các sự kiện `DailyCandleClosed` (nến ngày đóng cửa) từ Kafka.
- **Tính toán Chỉ báo Fractal**: 
  - Lưu trữ giá nến vào DB nội bộ để tạo chuỗi dữ liệu lịch sử.
  - Sử dụng thư viện `hurst` và các thuật toán nội bộ để tính **Hurst Exponent (H)** và **Fractal Dimension (D)**.
- **Xác định Chế độ Thị trường (Regime)**: Dựa vào hệ số Hurst để kết luận thị trường đang ở trạng thái nào:
  - `H > 0.5`: Trending (Có xu hướng rõ ràng).
  - `H = 0.5`: Random Walk (Bước đi ngẫu nhiên).
  - `H < 0.5`: Mean-reverting (Đảo chiều trung bình).
- **Phân phối rủi ro**: Phát sinh sự kiện `FractalRiskAssessed` (kèm mức độ rủi ro và regime) trở lại Kafka để các Agent khác hoặc hệ thống Giao dịch điều chỉnh tỷ trọng vốn.

## Kiến trúc (Python + FastAPI)
- **`app/main.py`**: Điểm khởi chạy của FastAPI, thiết lập vòng đời (lifespan) cho Database và Kafka Consumer.
- **`app/core/engine.py`**: Chứa logic lõi về thuật toán chuỗi thời gian (time-series analysis) và tính toán Hurst.
- **`app/infrastructure/`**: Kết nối với Kafka (`aiokafka`) và Postgres (`asyncpg`). Quản lý schema bằng Alembic.
- **`app/services/event_consumer.py`**: Hàm xử lý chính khi nhận được message Kafka, điều phối việc lưu trữ DB, tính toán và phát event đầu ra.

## Yêu cầu môi trường
Tạo file `.env` (hoặc thiết lập biến môi trường) trước khi chạy:
```env
DATABASE_URL=postgresql://user:pass@db:5432/fractaldb
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

## Chạy Migration (Alembic)
Tương tự Fundamental Agent, Fractal Analyzer sử dụng Postgres để lưu lịch sử giá và kết quả tính toán. Để tạo bảng, bạn cần chạy:
```bash
docker-compose exec fractal_analyzer alembic upgrade head
```

## Luồng sự kiện (Event Flow)
1. **Input**: `market.events` -> `{ "event_type": "DailyCandleClosed", "ticker": "...", "close_price": ... }`
2. **Output**: `analysis.events` -> `{ "event_type": "FractalRiskAssessed", "ticker": "...", "hurst_exponent": 0.65, "regime": "Trending" }`
