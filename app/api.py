from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import QueryRequest, QueryResponse
from app.services.citation_validator import validate_citations
from app.services.mock_retriever import MockRetriever
from app.services.rag import RAGService


app = FastAPI(
    title="Agentic Law API",
    description="Evidence-grounded legal research prototype",
    version="0.1.0",
)


retriever = MockRetriever()
rag_service = RAGService(retriever)


frontend_dir = Path(__file__).parent / "frontend"

app.mount(
    "/static",
    StaticFiles(directory=frontend_dir),
    name="static",
)


@app.get("/")
def home():
    return FileResponse(frontend_dir / "index.html")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "retriever": "mock",
        "rag": "mock",
    }


@app.post("/api/query", response_model=QueryResponse)
def query(request: QueryRequest):

    response = rag_service.answer(
        query=request.query,
        top_k=request.top_k,
        as_of_year=request.as_of_year,
        query_doc_id=request.query_doc_id,
    )

    if not validate_citations(
        response.citations,
        response.passages,
    ):
        raise ValueError(
            "Generated citations do not match retrieved passages."
        )

    return response