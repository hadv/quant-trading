from langchain.tools import tool
import logging
import os
import boto3
import requests
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
    
    s3_bucket = os.getenv("S3_BUCKET_NAME", "quant-trading")
    s3_endpoint = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
    ocr_api_url = os.getenv("PROTONX_OCR_API_URL", "http://localhost:8080/ocr")
    
    try:
        s3 = boto3.client(
            's3',
            endpoint_url=s3_endpoint,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
        )
        
        prefix = f"financial-reports/{ticker.upper()}/{year_quarter}_{doc_type}"
        
        response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=prefix)
        if 'Contents' not in response or not response['Contents']:
            return f"No financial report found for {ticker} ({doc_type} {year_quarter})."
            
        # Get the first matching file (e.g. .pdf or .txt)
        file_key = response['Contents'][0]['Key']
        logger.info(f"Found report file: {file_key}")
        
        file_obj = s3.get_object(Bucket=s3_bucket, Key=file_key)
        file_content = file_obj['Body'].read()
        
        if file_key.lower().endswith('.pdf'):
            logger.info("PDF file detected, sending to ProtonX OCR API...")
            files = {'file': (os.path.basename(file_key), file_content, 'application/pdf')}
            
            # Allow up to 120 seconds for the OCR API to process a large PDF
            ocr_response = requests.post(ocr_api_url, files=files, timeout=120)
            ocr_response.raise_for_status()
            
            result = ocr_response.json()
            return result.get('text', result.get('markdown', str(result)))
            
        else:
            # Assume text based
            return file_content.decode('utf-8')
            
    except Exception as e:
        logger.error(f"Error fetching/parsing report for {ticker}: {e}")
        return f"Error retrieving report data: {str(e)}"
