import os
import logging
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)

# Constants
CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "/app/chroma_db")
COLLECTION_NAME = "financial_reports"
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

def get_vector_store() -> Chroma:
    """Returns a LangChain Chroma vector store instance."""
    
    # Initialize Google Embeddings
    # Make sure GOOGLE_API_KEY is set in the environment
    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
    
    # Ensure the directory exists
    os.makedirs(CHROMA_DB_DIR, exist_ok=True)
    
    # Initialize Chroma client
    client = chromadb.PersistentClient(
        path=CHROMA_DB_DIR,
        settings=Settings(anonymized_telemetry=False)
    )
    
    # Return LangChain wrapper
    vector_store = Chroma(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings
    )
    
    return vector_store

# We can pre-initialize a singleton
vector_store = get_vector_store()

