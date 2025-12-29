"""
FastAPI Backend for RAG Chatbot
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import sys
from pathlib import Path

# Add paths for imports
rag_llm_path = Path(__file__).parent.parent / "src" / "RAG" / "LLM"
sys.path.insert(0, str(rag_llm_path))

from src.RAG.LLM.llm import GeminiRAG
from backend.logger import RAGLogger

# Initialize FastAPI app
app = FastAPI(title="RAG Chatbot API", version="1.0.0")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Global variables
rag_system = None
logger = None


# Request/Response models
class QuestionRequest(BaseModel):
    question: str
    top_k: Optional[int] = 5


class RetrievedDocument(BaseModel):
    rank: int
    content: str
    score: float
    metadata: Dict


class AnswerResponse(BaseModel):
    question: str
    answer: str
    retrieved_documents: List[RetrievedDocument]
    num_documents: int
    model_name: str


@app.on_event("startup")
async def startup_event():
    """Initialize RAG system on startup"""
    global rag_system, logger

    print("🚀 Starting FastAPI backend...")

    # Load API key
    import os
    from dotenv import load_dotenv

    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("❌ GEMINI_API_KEY not found in .env file")

    # Initialize RAG system
    print("🔄 Initializing RAG system...")
    rag_system = GeminiRAG(api_key=api_key)

    # Initialize logger
    log_file = Path(__file__).parent / "rag_logs.csv"
    logger = RAGLogger(log_file=str(log_file))

    print("✅ Backend ready!")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "RAG Chatbot API",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    """Check if RAG system is initialized"""
    if rag_system is None:
        raise HTTPException(
            status_code=503, detail="RAG system not initialized"
        )
    return {"status": "healthy", "rag_initialized": True}


@app.post("/chat", response_model=AnswerResponse)
async def chat(request: QuestionRequest):
    """
    Main chat endpoint

    Receives a question, retrieves relevant documents, generates answer,
    and logs everything to CSV
    """
    if rag_system is None:
        raise HTTPException(
            status_code=503, detail="RAG system not initialized"
        )

    try:
        # Get answer from RAG system
        result = rag_system.answer(
            question=request.question,
            top_k=request.top_k,
            stream=False,
            verbose=True,
        )

        # Format retrieved documents for response
        retrieved_docs = []
        for i, source in enumerate(result["sources"], 1):
            doc = RetrievedDocument(
                rank=i,
                content=source.content,
                score=source.score,
                metadata=source.metadata,
            )
            retrieved_docs.append(doc)

        # Prepare response
        response = AnswerResponse(
            question=result["question"],
            answer=result["answer"],
            retrieved_documents=retrieved_docs,
            num_documents=result["num_sources"],
            model_name=result["model_name"],
        )

        # Log to CSV
        sources_for_log = [
            {
                "content": doc.content,
                "score": doc.score,
                "metadata": doc.metadata,
            }
            for doc in retrieved_docs
        ]

        logger.log(
            question=result["question"],
            sources=sources_for_log,
            model_name=result["model_name"],
        )

        return response

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing request: {str(e)}"
        )


# Run with: uvicorn main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
