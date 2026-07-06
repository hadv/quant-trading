# Backfill Service & Data Fetcher

`backfill-job` là một tiến trình Go (Worker Pool) làm nhiệm vụ gọi API của nhà cung cấp dữ liệu chứng khoán (Market Data Provider), lấy dữ liệu lịch sử (Candles / OHLC) và lưu vào cơ sở dữ liệu. 

## 1. Cấu trúc Client

Module này sử dụng `domain.IMarketClient` interface, bao gồm 2 implementation:
- `RealMarketClient`: Sử dụng `net/http` để gọi HTTP GET request lấy dữ liệu thực tế từ nhà cung cấp. Hỗ trợ cơ chế Retry (Exponential Backoff) tự động khi gặp lỗi mạng.
- `MockMarketClient`: Dành cho môi trường phát triển (Dev/Local) hoặc Unit Test. Có khả năng tự động tiêm (inject) dữ liệu giả từ bộ nhớ thay vì gọi API thực. Dữ liệu mock được map thông qua `CandleDTO` và generic `transform` framework.

## 2. Cấu hình (Environment Variables)

Service nhận các biến môi trường sau để cấu hình quá trình chạy:

| Biến môi trường | Giải thích | Giá trị mặc định |
| :--- | :--- | :--- |
| `DATABASE_URL` | Chuỗi kết nối đến PostgreSQL | `postgres://user:pass@localhost:5432/quantdb` |
| `USE_MOCK_API` | Xác định xem có sử dụng Mock data hay không. Nếu `true`, Real Client sẽ bị tắt. | `true` (Trống sẽ mặc định là mock) |
| `MARKET_API_URL` | Base URL của nhà cung cấp API chứng khoán (nếu dùng API thật). | `https://api.example.com` |
| `MARKET_API_KEY` | Token xác thực truy cập API (nếu có). | `""` |

## 3. Cách chạy (Execution)

Bạn có thể chạy trực tiếp bằng lệnh Go:

**Chạy với Mock Data (mặc định):**
```bash
# Biến môi trường USE_MOCK_API mặc định là true nên chỉ cần:
go run cmd/backfill-job/main.go
```

**Chạy với dữ liệu thật:**
```bash
# Trên Windows PowerShell
$env:USE_MOCK_API="false"
$env:MARKET_API_URL="https://api.your-provider.com"
$env:MARKET_API_KEY="your-secret-token"
go run cmd/backfill-job/main.go

# Hoặc trên Linux/macOS
USE_MOCK_API=false MARKET_API_URL="https://api.your-provider.com" MARKET_API_KEY="your-secret-token" go run cmd/backfill-job/main.go
```

## 4. Kiến trúc tương lai (Roadmap)

Trong tương lai, module data fetcher này sẽ được mở rộng thành kiến trúc "Event-Driven & Cron-job" với các tiến trình:
1. `daily-price-job`: Chạy lúc 15:30 (VN) hoặc 04:30 (Mỹ) lấy giá đóng cửa và đánh thức **Đặc vụ Fractal**.
2. `financial-report-job`: Chạy trong các tháng báo cáo tài chính, tải PDF/JSON và đánh thức **Đặc vụ Cơ bản**.
3. `macro-news-job`: Quét tin tức RSS để cảnh báo phòng vệ rủi ro.
4. `watchdog`: Script Python kiểm tra giá thời gian thực 15 phút/lần chống Flash Crash.
