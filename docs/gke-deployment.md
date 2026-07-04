# Hướng dẫn triển khai hệ thống Quant Trading trên GKE

Tài liệu này cung cấp các bước từ đầu đến cuối để thiết lập và triển khai hệ thống **Quant Trading (Backfill Service & Database)** lên Google Kubernetes Engine (GKE) theo chuẩn Production.

## 1. Yêu cầu hệ thống (Prerequisites)
- [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install) đã được cài đặt và đăng nhập.
- `kubectl` và `kustomize` đã được cài đặt.
- Bạn đã có một Project trên GCP (thay thế `<YOUR-GCP-PROJECT-ID>` bằng ID thật của bạn).

---

## 2. Khởi tạo GKE Cluster
Bạn cần tạo một GKE Cluster (khuyến nghị dùng Autopilot hoặc Standard với Workload Identity được bật).

```bash
gcloud container clusters create-auto quant-trading-cluster \
    --region=asia-southeast1 \
    --project=<YOUR-GCP-PROJECT-ID>
```
Lấy thông tin xác thực để `kubectl` có thể kết nối tới cụm:
```bash
gcloud container clusters get-credentials quant-trading-cluster \
    --region=asia-southeast1 \
    --project=<YOUR-GCP-PROJECT-ID>
```

---

## 3. Cài đặt các Infrastructure chung
Bao gồm StorageClass cho SSD để chạy CloudNativePG (Database).

```bash
# Áp dụng cấu hình hạ tầng
kubectl apply -k k8s/infrastructure/
```

> **Lưu ý:** StorageClass `gke-premium-rwo` sẽ được tạo để CloudNativePG có thể tự động cấp phát ổ SSD (hiệu năng cao) thay vì ổ HDD tiêu chuẩn.

---

## 4. Thiết lập Workload Identity
Workload Identity giúp Pod (Job) trong GKE xác thực với các dịch vụ của GCP một cách an toàn mà không cần lưu trữ Service Account Key (.json).

**Bước 4.1: Tạo Google Cloud IAM Service Account**
```bash
gcloud iam service-accounts create backfill-gcp-sa \
    --project=<YOUR-GCP-PROJECT-ID>
```

**Bước 4.2: Cấp quyền cho IAM Service Account** (ví dụ: quyền đọc/ghi BigQuery, Cloud Storage)
```bash
# Ví dụ cấp quyền Storage Admin
gcloud projects add-iam-policy-binding <YOUR-GCP-PROJECT-ID> \
    --member="serviceAccount:backfill-gcp-sa@<YOUR-GCP-PROJECT-ID>.iam.gserviceaccount.com" \
    --role="roles/storage.admin"
```

**Bước 4.3: Liên kết IAM Service Account với Kubernetes Service Account**
```bash
# Cho phép Kubernetes SA (backfill-worker-sa) được mạo danh IAM SA
gcloud iam service-accounts add-iam-policy-binding backfill-gcp-sa@<YOUR-GCP-PROJECT-ID>.iam.gserviceaccount.com \
    --role roles/iam.workloadIdentityUser \
    --member "serviceAccount:<YOUR-GCP-PROJECT-ID>.svc.id.goog[quant-trading/backfill-worker-sa]"
```

**Bước 4.4: Cập nhật file manifest**
Đảm bảo bạn đã thay đổi ID của GCP Project trong file `k8s/apps/backfill-job/base/serviceaccount.yaml`:
```yaml
annotations:
  iam.gke.io/gcp-service-account: "backfill-gcp-sa@<YOUR-GCP-PROJECT-ID>.iam.gserviceaccount.com"
```

---

## 5. Cấu hình Secret Manager (Khuyến nghị)
Hệ thống hiện tại cần secret `cnpg-cluster-app-secret` để chứa thông tin kết nối DB (`uri`, `jdbc-uri`).
Trên GKE, khuyến nghị:
1. Lưu chuỗi kết nối vào **Google Secret Manager**.
2. Cài đặt **External Secrets Operator (ESO)** vào cluster.
3. Tạo file `ExternalSecret` để ESO tự động đồng bộ từ GCP Secret Manager thành Kubernetes Secret `cnpg-cluster-app-secret`.

---

## 6. Triển khai Ứng dụng
Nếu bạn không dùng ArgoCD mà muốn deploy trực tiếp (thủ công) để test:

```bash
# Tạo namespace
kubectl create namespace quant-trading

# Deploy Database Changelog (ConfigMap)
kubectl apply -k db/

# Deploy Backfill Service & Migrate Job
kubectl apply -k k8s/apps/backfill-job/overlays/prod/
```

Nếu dùng **ArgoCD**:
1. Cài đặt ArgoCD lên cluster.
2. Tạo các Application Object của ArgoCD trỏ tới repository này (chỉ định các thư mục `k8s/infrastructure`, `db/`, `k8s/apps/backfill-job/overlays/prod`).
3. Ứng dụng sẽ tự động sync và deploy.
