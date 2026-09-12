# Tài Liệu Bàn Giao Tối Ưu Hóa (Handoff)
Tài liệu này lưu trữ các kế hoạch tối ưu hóa hệ thống Quant Trading lấy cảm hứng từ DeepSeek, được tách ra để tiện thực thi trên một luồng hội thoại (conversation) độc lập trong tương lai.

Khi bắt đầu một luồng hội thoại mới, bạn chỉ cần yêu cầu Agent đọc file này và chọn mục muốn triển khai.

---

## 1. Tối ưu Fundamental Agent: Thay thế RAG tĩnh bằng Agentic Tool Calling & MLA

**Vấn đề hiện tại:** 
Hệ thống sử dụng RAG (qua `search_financial_records` / ChromaDB) cắt nhỏ (chunking) văn bản. Vector search dễ gây mất ngữ cảnh (Context Loss) đối với các bảng biểu tài chính dài và thông tin liền mạch. Tuy nhiên, nếu nhét toàn bộ lịch sử hàng chục năm của công ty vào LLM thì lại quá tốn kém và nhiễu.

**Cách tiếp cận đề xuất:**
Áp dụng **Agentic Tool Calling** kết hợp với khả năng đọc hiểu ngữ cảnh siêu dài (MLA) của Gemini 1.5 Pro. Thay vì mớm sẵn dữ liệu tĩnh, ta trao quyền cho Agent tự quyết định cần đọc gì:

1. **Cung cấp Tool lấy báo cáo nguyên văn (Full-text):** Tạo tool `get_full_financial_report(ticker, doc_type, year_quarter)`. Khi gọi, LLM sẽ nhận được nguyên văn bản báo cáo 10-K hoặc 10-Q của một khoảng thời gian cụ thể (ví dụ: 10-K năm ngoái + 10-Q các quý năm nay).
2. **Cung cấp Tool tìm kiếm Vector cho Tin Tức (RAG):** Giữ lại RAG nhưng đổi thành tool `search_vector_database(ticker, query)` để LLM tự tra cứu các sự kiện, tin tức ngắn có độ nhiễu cao.
3. **Luồng thực thi thông minh:** LLM tự động suy luận: *"Để đánh giá lợi thế cạnh tranh của Apple lúc này, tôi cần gọi tool lấy 10-K năm 2023, và 10-Q quý 1 2024. Đọc xong thấy thiếu thông tin về AI, tôi sẽ gọi tiếp tool Vector Search để tìm tin tức liên quan"*.

**Mục tiêu kỳ vọng:**
- LLM được đọc dữ liệu tài chính mạch lạc, có tính hệ thống nhờ Long-Context (2M tokens).
- Tối ưu chi phí (cost) và giảm độ nhiễu, vì Agent chỉ lấy đúng bản 10-K/10-Q của thời điểm cần phân tích.
- Hệ thống linh hoạt tối đa, xử lý được cả dài hạn (10-K) lẫn biến động ngắn hạn (10-Q, News).

---

## 2. Tối ưu Go Backfill Service: DualPipe (Overlap I/O)

**Vấn đề hiện tại:** 
Trong `cmd/backfill-job/main.go`, tiến trình kéo dữ liệu nến (OHLCV) từ API thị trường và lưu vào Postgres có thể đang chạy một cách tuần tự (Tuần tự hóa I/O Network và I/O Disk).

**Cách tiếp cận (Lấy cảm hứng từ thuật toán DualPipe của DeepSeek):**
DeepSeek tối ưu bằng cách cho phép tiến trình tính toán (Compute) và truyền dữ liệu (Communication) "gối đầu" lên nhau (Overlap). Trong Go, ta dùng `Goroutines` và `Channels` để thiết lập một Pipeline Concurrency tương tự:
1. **Worker Pool 1 (Network Fetchers):** Tập hợp các goroutine chuyên gọi HTTP API để tải batch dữ liệu nến về. Tải xong đẩy ngay vào Channel `A`.
2. **Worker Pool 2 (DB Inserters):** Lắng nghe Channel `A` và thực hiện batch insert/copy vào Database (Sử dụng Postgres Bulk Insert hoặc `COPY`). 
3. **Tái sử dụng bộ nhớ (Slice Pool):** Sử dụng package `pkg/slicepool` đã có trong dự án để cấp phát bộ nhớ mảng nến thay vì tạo GC pressure liên tục.

**Mục tiêu kỳ vọng:**
- Không có khoảnh khắc nào CPU hoặc Băng thông mạng phải nằm chờ (Idle) vì I/O đĩa. Tối đa hóa throughput cho việc backfill hàng triệu nến lịch sử.
