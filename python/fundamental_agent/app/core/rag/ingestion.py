import logging
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.core.rag.vector_store import vector_store, CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)

def ingest_documents(raw_texts: list[str], metadatas: list[dict]):
    """
    Standard pipeline to chunk and ingest text documents into ChromaDB.
    This function is ready for production use when real data is available.
    """
    try:
        # 1. Khởi tạo Text Splitter (Bộ chia nhỏ văn bản chuẩn)
        # Trong thực tế, chunk_size thường là 1000-2000 ký tự. Để test thì để nhỏ tùy ý.
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, 
            chunk_overlap=CHUNK_OVERLAP, 
            length_function=len,
            is_separator_regex=False,
        )
        
        # 2. Thực hiện Chunking
        docs = text_splitter.create_documents(raw_texts, metadatas=metadatas)
        
        # 3. Insert vào Vector DB
        if docs:
            vector_store.add_documents(documents=docs)
            logger.info(f"Ingested successfully. Total chunks created: {len(docs)}")
            
    except Exception as e:
        logger.error(f"Error during data ingestion: {e}")
        raise

