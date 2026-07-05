import logging
from app.core.rag.vector_store import vector_store
from app.core.rag.ingestion import ingest_documents

logger = logging.getLogger(__name__)

async def mock_ingest_data():
    """Mock function that uses the standard ingest pipeline if DB is empty."""
    try:
        collection = vector_store._collection
        if collection.count() == 0:
            logger.info("Vector DB is empty. Running mock ingestion...")
            
            raw_texts = [
                "Báo cáo tài chính Q2/2026 của FPT: Doanh thu tăng trưởng mạnh mẽ đạt 20%, biên lợi nhuận ròng đạt 15%. Công ty có lợi thế cạnh tranh rất lớn nhờ nguồn nhân lực dồi dào và các hợp đồng AI quốc tế. Gần đây, FPT đã trúng thầu dự án lớn ở Nhật Bản, hứa hẹn đem lại dòng tiền tự do dồi dào trong 3 năm tới. Tỷ lệ nợ trên vốn chủ sở hữu duy trì ở mức an toàn 0.4.",
                "Báo cáo tài chính Q2/2026 của VCB: Tỷ lệ nợ xấu ở mức thấp kỷ lục 0.7%. Tỷ lệ P/B là 2.5, cho thấy thị trường định giá cao chất lượng tài sản của ngân hàng. CASA (Tiền gửi không kỳ hạn) tăng trưởng 12%, giúp tối ưu hóa chi phí vốn (COF). Lợi thế cạnh tranh của VCB đến từ tệp khách hàng FDI và doanh nghiệp nhà nước lớn.",
                "Báo cáo tài chính Q2/2026 của HPG: Dòng tiền tự do đạt 5000 tỷ. Tỷ lệ Nợ/Vốn chủ sở hữu là 0.8. Giá nguyên vật liệu giảm giúp HPG cải thiện biên lợi nhuận đáng kể. HPG có lợi thế kinh tế theo quy mô (Economies of Scale) lớn nhất Đông Nam Á, giúp họ kiểm soát giá thép nội địa."
            ]
            metadatas = [{"ticker": "FPT"}, {"ticker": "VCB"}, {"ticker": "HPG"}]
            
            # Tái sử dụng hàm chuẩn
            ingest_documents(raw_texts, metadatas)
            
    except Exception as e:
        logger.error(f"Error checking or running mock data ingestion: {e}")
