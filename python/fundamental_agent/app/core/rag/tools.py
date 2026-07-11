from langchain.tools import tool
import logging
from app.core.rag.vector_store import vector_store

logger = logging.getLogger(__name__)

@tool
def search_vector_database(ticker: str, query: str) -> str:
    """
    Search the vector database for short news, recent events, or specific snippets related to a specific ticker.
    Use this tool when you need targeted, small pieces of context (like breaking news or specific risk events) 
    that might not be captured in the annual/quarterly reports.
    
    Args:
        ticker (str): The stock ticker symbol (e.g., FPT, HPG).
        query (str): The specific question or topic to search for (e.g., "chiến lược phát triển AI", "rủi ro nợ vay").
        
    Returns:
        str: The concatenated snippets of relevant documents found in the database.
    """
    logger.info(f"LLM called tool search_vector_database with ticker={ticker}, query={query}")
    
    # We can use the ticker as a metadata filter to narrow down results
    try:
        results = vector_store.similarity_search(
            query=query, 
            k=3, 
            filter={"ticker": ticker}
        )
        
        if not results:
            # Fallback without filter in case metadata is missing
            results = vector_store.similarity_search(query=f"{ticker} {query}", k=3)
            
        if not results:
            return f"No financial records found for {ticker} regarding '{query}'."
            
        context = "\n\n---\n\n".join([doc.page_content for doc in results])
        return f"Found the following context for {ticker}:\n\n{context}"
        
    except Exception as e:
        logger.error(f"Error executing search_vector_database: {e}")
        return f"Error retrieving data: {e}"

@tool
def get_full_financial_report(ticker: str, doc_type: str, year_quarter: str) -> str:
    """
    Retrieve the full-text financial report (e.g., 10-K for annual, 10-Q for quarterly) for a given ticker and time period.
    Use this tool when you need deep context to evaluate a company's Moat Score, competitive advantage, and long-term strategy.
    
    Args:
        ticker (str): The stock ticker symbol (e.g., FPT, VCB, HPG).
        doc_type (str): The type of document, typically "10-K" (annual) or "10-Q" (quarterly).
        year_quarter (str): The time period, e.g., "2023", "Q1-2024".
        
    Returns:
        str: The raw, full text of the financial report.
    """
    logger.info(f"LLM called tool get_full_financial_report with ticker={ticker}, doc_type={doc_type}, year_quarter={year_quarter}")
    
    # MOCK DATA FOR DEMONSTRATION PURPOSES
    # In a real system, this would query a database (e.g., Postgres, MongoDB) or an object store (e.g., S3) 
    # to fetch the actual long-form document.
    
    if ticker.upper() == "FPT":
        return f"""
        [MOCK FULL REPORT {doc_type} {year_quarter} FOR FPT]
        Báo cáo chi tiết:
        1. Tổng quan: FPT tiếp tục duy trì vị thế dẫn đầu trong mảng công nghệ thông tin tại Việt Nam. Doanh thu chuyển đổi số thị trường nước ngoài tăng trưởng 25% so với cùng kỳ.
        2. Lợi thế cạnh tranh (Moat): Nguồn nhân lực kỹ sư phần mềm dồi dào, chi phí cạnh tranh so với Ấn Độ và Đông Âu. Khả năng cung cấp dịch vụ End-to-End từ tư vấn đến triển khai hệ thống AI/Cloud.
        3. Rủi ro: Rủi ro tỷ giá do doanh thu chủ yếu từ nước ngoài (Nhật Bản, Mỹ). Rủi ro cạnh tranh nhân sự chất lượng cao.
        4. Chiến lược tương lai: Mở rộng thâu tóm các công ty tư vấn tại Mỹ để tăng cường năng lực mảng AI và Data Analytics.
        """
    elif ticker.upper() == "VCB":
         return f"""
        [MOCK FULL REPORT {doc_type} {year_quarter} FOR VCB]
        Báo cáo chi tiết:
        1. Tổng quan: Ngân hàng TMCP Ngoại thương Việt Nam ghi nhận mức lợi nhuận trước thuế cao nhất ngành. Tỷ lệ nợ xấu (NPL) được kiểm soát ở mức cực kỳ thấp dưới 1%.
        2. Lợi thế cạnh tranh (Moat): Thương hiệu mạnh nhất trong ngành ngân hàng, nguồn vốn huy động giá rẻ (CASA) cực lớn giúp chi phí vốn (Cost of Funds) luôn ở mức thấp nhất hệ thống. Quan hệ chặt chẽ với các tổng công ty nhà nước và doanh nghiệp FDI.
        3. Rủi ro: Tín dụng chủ yếu tập trung vào các tập đoàn lớn, nếu có cú sốc vĩ mô sẽ chịu ảnh hưởng.
        """
    elif ticker.upper() == "HPG":
         return f"""
        [MOCK FULL REPORT {doc_type} {year_quarter} FOR HPG]
        Báo cáo chi tiết:
        1. Tổng quan: Hòa Phát tiếp tục giữ thị phần thép xây dựng số 1 Việt Nam. Lợi nhuận phục hồi nhờ giá than cốc giảm và sản lượng bán hàng tăng trưởng trở lại.
        2. Lợi thế cạnh tranh (Moat): Lợi thế quy mô (Economies of Scale) lớn nhất Đông Nam Á với khu liên hợp Dung Quất. Chuỗi giá trị khép kín từ quặng sắt, than đá đến thép thành phẩm giúp HPG có giá thành sản xuất thấp nhất khu vực, tạo rào cản gia nhập khổng lồ.
        3. Dự án tương lai: Dung Quất 2 đang triển khai đúng tiến độ, dự kiến bổ sung 5.6 triệu tấn thép cuộn cán nóng (HRC) mỗi năm, giúp HPG vươn lên thành nhà sản xuất HRC lớn nhất Đông Nam Á.
        """
    else:
        return f"""
        [MOCK FULL REPORT {doc_type} {year_quarter} FOR {ticker}]
        Dữ liệu chi tiết cho mã {ticker} hiện chưa có trong cơ sở dữ liệu mock.
        Tuy nhiên, doanh nghiệp tiếp tục hoạt động kinh doanh cốt lõi với biên lợi nhuận ổn định.
        """
