from typing import List, Optional

from pydantic import BaseModel


class Passage(BaseModel):
    chunk_id: str
    doc_id: str
    case_name: str
    year: Optional[int] = None
    page: Optional[int] = None
    section: Optional[str] = None
    text: str
    score: Optional[float] = None


class QueryRequest(BaseModel):
    query: str
    query_doc_id: Optional[str] = None
    as_of_year: Optional[int] = None
    top_k: int = 5
    use_graph: bool = False


class Citation(BaseModel):
    citation_id: int
    chunk_id: str
    doc_id: str
    case_name: str
    page: Optional[int] = None
    supporting_text: str


class QueryResponse(BaseModel):
    query: str
    answer: str
    passages: List[Passage]
    citations: List[Citation]
    mode: str