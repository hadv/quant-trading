from langchain.tools import tool
import logging
from app.core.rag.vector_store import vector_store

logger = logging.getLogger(__name__)

@tool
def search_financial_records(ticker: str, query: str) -> str:
    """
    Search the vector database for financial reports, fundamental data, and news related to a specific ticker.
    Use this tool when you need more context about a company to evaluate its Moat Score and Intrinsic Value.
    
    Args:
        ticker (str): The stock ticker symbol (e.g., FPT, HPG).
        query (str): The specific question or topic to search for (e.g., "chiến lược phát triển AI", "rủi ro nợ vay").
        
    Returns:
        str: The concatenated snippets of relevant documents found in the database.
    """
    logger.info(f"LLM called tool search_financial_records with ticker={ticker}, query={query}")
    
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
        logger.error(f"Error executing search_financial_records: {e}")
        return f"Error retrieving data: {e}"
