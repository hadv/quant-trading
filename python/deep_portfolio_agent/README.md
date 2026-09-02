# Deep Portfolio Agent (The Quant Brain)

Deep Portfolio Agent là một cỗ máy định lượng sử dụng sự kết hợp giữa **Monte Carlo Simulation** (Giả lập ngẫu nhiên) và **Neural Network** (Mạng nơ-ron nhân tạo) để giải quyết bài toán quản trị rủi ro và phân bổ vốn trong không gian đa chiều (Deep BSDE/Feynman-Kac).

## Kiến trúc 

1. **Bộ mô phỏng Monte Carlo (`sde_simulator.py`)**: Sinh ra hàng chục ngàn quỹ đạo giá tương lai cho hàng trăm tài sản (Geometric Brownian Motion) dựa trên ma trận hiệp phương sai.
2. **Neural PDE Solver (`neural_solver.py`)**: Học cách phân bổ tỷ trọng vốn sao cho Sharpe Ratio đạt mức tối đa trên mọi kịch bản vũ trụ mô phỏng.
3. **Risk Management (`risk_manager.py`)**: Tính toán Value at Risk (VaR 95%) và Expected Shortfall (ES). Kích hoạt cảnh báo đỏ nếu danh mục lọt vào kịch bản thiên nga đen.

## Hướng dẫn Chạy trên GPU (Tối ưu Tốc độ)

Mã nguồn của hệ thống này được viết hoàn toàn bằng **JAX** và **Flax**. 
Về mặt code, các file `.py` đã **SẴN SÀNG 100% CHO GPU** (Trình biên dịch XLA sẽ tự động đảm nhiệm việc này mà không cần gọi `.to(device)` như PyTorch). 

Tuy nhiên, cấu hình mặc định trong `requirements.txt` đang thiết lập ở chế độ `jax[cpu]` nhằm đảm bảo tính tương thích phổ quát trên mọi môi trường. Nếu bạn muốn kích hoạt GPU, hãy làm theo hướng dẫn sau:

### 1. Dành cho Server/Cụm K8s dùng NVIDIA GPU
Sửa file `requirements.txt`:
- Xóa: `jax[cpu]>=...`
- Thêm: `jax[cuda12]` (hoặc phiên bản cuda tương ứng với server).

*(Khuyến nghị: Cập nhật `Dockerfile` dùng Base Image có chứa Nvidia CUDA nếu cần chạy trên Container).*

### 2. Dành cho MacBook (Apple Silicon M1/M2/M3)
Apple hỗ trợ JAX thông qua plugin Metal. Bạn chỉ cần cài thêm gói này vào môi trường ảo:
```bash
pip install jax-metal
```
Ngay lập tức XLA backend sẽ chuyển sang dùng GPU của máy Mac.

## Cách thức hoạt động
Chạy file Entrypoint:
```bash
python -m app.main
```
Agent sẽ chạy ngầm định kỳ (mặc định 1 giờ / 1 lần), đọc dữ liệu mới từ Database và ghi đè Tỷ trọng Mục tiêu (Target Weights) vào lại DB.
