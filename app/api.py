from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import (
    CaseAnalysisRequest,
    CaseAnalysisResponse,
)

from app.services.citation_validator import (
    validate_citations,
)

from app.services.mock_retriever import (
    MockRetriever,
)

from app.services.rag import RAGService


app = FastAPI(
    title="Agentic Law API",
    description=(
        "Logic-aware precedent retrieval and "
        "evidence-grounded legal research prototype."
    ),
    version="0.2.0",
)


retriever = MockRetriever()

rag_service = RAGService(
    retriever=retriever,
)


frontend_dir = (
    Path(__file__).parent
    / "frontend"
)


app.mount(
    "/static",
    StaticFiles(
        directory=frontend_dir,
    ),
    name="static",
)


@app.get("/")
def home():

    return FileResponse(
        frontend_dir / "index.html"
    )


@app.get("/health")
def health():

    return {
        "status": "ok",
        "version": "0.2.0",
        "retrieval": "mock-logic-aware",
    }


@app.post(
    "/api/analyze",
    response_model=CaseAnalysisResponse,
)
def analyze(
    request: CaseAnalysisRequest,
):

    response = rag_service.analyze(
        request
    )

    valid = validate_citations(
        response.citations,
        response.precedents,
    )

    if not valid:

        raise ValueError(
            "Citation validation failed."
        )

    return response