# Quant Trading

Dự án Quant Trading (theo chuẩn Clean Architecture & GitOps) phục vụ cho hệ thống Backtest đệ quy và giao dịch.

Hiện tại, dự án đang chứa service đầu tiên:
- **Backfill Service**: Chịu trách nhiệm kéo dữ liệu nến (OHLCV) từ thị trường và lưu trữ vào cơ sở dữ liệu.

## Cấu trúc thư mục

- `cmd/backfill-job/`: Điểm khởi chạy của ứng dụng, chứa hàm `main()` và `Dockerfile`.
- `db/changelog/`: Các file SQL migration được quản lý bởi Liquibase.
- `internal/`: Logic nghiệp vụ lõi (Clean Architecture).
  - `domain/`: Khai báo Entity và Interface.
  - `infrastructure/`: Implement kết nối Database (Postgres), gọi API thị trường, và cài đặt Telemetry.
  - `usecase/`: Chứa nghiệp vụ điều phối chính (Backfill Service).
- `k8s/`: Cấu hình triển khai lên Kubernetes thông qua Kustomize và ArgoCD.
- `pkg/`: Các package dùng chung (ví dụ: Slice Pool để tối ưu bộ nhớ).

---

## Hướng dẫn chạy nhanh ở Local (Không cần Kubernetes)

Để phát triển và chạy thử ứng dụng trên máy cá nhân một cách nhanh chóng, dự án đã cung cấp sẵn file `docker-compose.yml` chứa database Postgres và công cụ Migration Liquibase.

### Yêu cầu
- Đã cài đặt [Docker](https://www.docker.com/) và [Docker Compose](https://docs.docker.com/compose/).
- Đã cài đặt [Go](https://go.dev/) (>= 1.21).

### Bước 1: Khởi động Database và chạy DB Migration
Mở terminal ở thư mục gốc của dự án và chạy:
```bash
docker-compose up -d
```
Lệnh này sẽ:
1. Khởi động một container Postgres (`db`) ở port 5432.
2. Khởi động một container `liquibase` chạy một lần duy nhất để tạo các bảng (daily_candles, outbox_events) vào Postgres, sau đó nó sẽ tự động thoát (Exit 0).

Bạn có thể kiểm tra xem Liquibase đã chạy thành công chưa bằng lệnh:
```bash
docker-compose logs liquibase
```

### Bước 2: Chạy ứng dụng Go
Đảm bảo bạn đã cài đủ thư viện:
```bash
go mod tidy
```
Sau đó, cấp chuỗi kết nối Database qua biến môi trường và chạy code:

**Trên macOS/Linux:**
```bash
DATABASE_URL="postgres://user:pass@localhost:5432/quantdb" go run cmd/backfill-job/main.go
```

**Trên Windows (PowerShell):**
```powershell
$env:DATABASE_URL="postgres://user:pass@localhost:5432/quantdb"
go run cmd/backfill-job/main.go
```
Bạn sẽ thấy log in ra ứng dụng đang kéo dữ liệu và lưu vào database.

---

## Hướng dẫn Build và Deploy lên Kubernetes (Production)

Hệ thống được thiết kế theo chuẩn GitOps. Việc deploy lên Production sẽ thông qua ArgoCD tự động hóa.

### 1. Build và Push Docker Image
Mỗi khi có thay đổi mã nguồn, bạn cần build Docker image và đẩy lên Container Registry (ví dụ: GitHub Container Registry). Thường bước này được CI/CD (GitHub Actions) làm tự động.

Chạy thử thủ công:
```bash
docker build -f cmd/backfill-job/Dockerfile -t ghcr.io/hadv/quant-backfill:v1.0.0 .
docker push ghcr.io/hadv/quant-backfill:v1.0.0
```

### 2. Cập nhật Kustomize (GitOps)
Sửa file `k8s/apps/backfill-job/overlays/prod/kustomization.yaml` để cập nhật tag image mới:
```yaml
images:
  - name: ghcr.io/hadv/quant-backfill
    newName: ghcr.io/hadv/quant-backfill
    newTag: v1.0.0 # Đổi tag thành phiên bản vừa build
```

Sau đó **Commit & Push** code lên GitHub.

### 3. ArgoCD Deploy
Khi code được push lên nhánh `main`:
1. ArgoCD phát hiện thay đổi trên Git.
2. **PreSync Hook**: ArgoCD sẽ tạo ra K8s Job tên `db-migration` chạy image Liquibase. Job này mount ConfigMap chứa mã nguồn SQL ở thư mục `db/` và kết nối tới database Cluster (thông qua CNPG Secret) để cập nhật DB Schema.
3. **Sync**: Sau khi DB migrate thành công, ArgoCD sẽ deploy K8s Job `backfill-market-data` để chạy logic lấy dữ liệu của bạn trên Cluster.
