# Fundamental Agent

`fundamental_agent` là một service bằng Python sử dụng Trí tuệ Nhân tạo (LLM) và Kỹ thuật Tăng cường Suy luận bằng Tìm kiếm (RAG) để đánh giá sức khỏe tài chính của các công ty.

## Chức năng cốt lõi
- **Lắng nghe thị trường**: Bắt sự kiện `DailyCandleClosed` từ Kafka.
- **Cache dữ liệu tài chính**: Truy vấn bảng `fundamental_data_cache` trong PostgreSQL nội bộ để lấy các chỉ số P/E, P/B, biên lợi nhuận, v.v.
- **RAG (Retrieval-Augmented Generation)**: Agent được cấp quyền sử dụng công cụ tìm kiếm vào cơ sở dữ liệu Vector (ChromaDB) để đọc Báo cáo tài chính, Biên bản họp Đại hội đồng cổ đông, hoặc tin tức vĩ mô nhằm thu thập thêm bằng chứng.
- **Chấm điểm**: LLM (hoạt động theo phong cách Warren Buffett) xuất ra:
  - `Intrinsic Value` (Định giá nội tại).
  - `Moat Score` (Điểm lợi thế cạnh tranh từ 1-10).
- **Lưu trữ & Phân phối**: Lưu kết quả vào bảng `fundamental_assessments` (Postgres) và bắn sự kiện `FundamentalScoreUpdated` lên Kafka để phục vụ luồng giao dịch.

## Kiến trúc (Clean Architecture + LangChain)
- **`app/main.py`**: Điểm khởi chạy của FastAPI. Quản lý vòng đời (lifespan) của Kafka, Database, và Data Ingestion.
- **`app/core/rag/`**: Chứa logic về bộ nhớ RAG:
  - `vector_store.py`: Cấu hình ChromaDB lưu trữ cục bộ và nhúng (embedding) qua Google Gemini API.
  - `tools.py`: Cung cấp công cụ `@tool` cho Agent để tìm kiếm dữ liệu.
- **`app/core/llm_engine.py`**: Trái tim của hệ thống. Sử dụng `create_tool_calling_agent` từ LangChain để điều phối chuỗi suy luận của LLM.
- **`app/infrastructure/`**: Kết nối với Kafka (`aiokafka`) và Postgres (`asyncpg`). Quản lý schema bằng Alembic.

## Yêu cầu môi trường
Tạo file `.env` (hoặc thiết lập biến môi trường) trước khi chạy:
```env
LLM_MODEL_NAME=gpt-3.5-turbo
OPENAI_API_KEY=sk-xxx...
GOOGLE_API_KEY=AIza... (Dành cho mô hình Embedding)
DATABASE_URL=postgresql://user:pass@db:5432/fundamentaldb
KAFKA_BROKERS=kafka:9092
```

## Chạy Migration (Alembic)
Agent yêu cầu phải chạy migration để tạo các bảng trong PostgreSQL:
```bash
docker-compose exec fundamental_agent alembic upgrade head
```

## Nguồn dữ liệu (Ingestion)
Hiện tại, tài liệu văn bản (Báo cáo tài chính) đang được nạp vào ChromaDB qua hàm giả lập `mock_ingest_data()` chạy lúc khởi động ứng dụng. Để mở rộng, bạn có thể bổ sung một event Kafka riêng (`FinancialNewsPublished`) để Agent tự động embed văn bản mới vào ChromaDB.
