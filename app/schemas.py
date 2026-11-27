from typing import List, Optional

from pydantic import BaseModel, Field


class CaseAnalysisRequest(BaseModel):
    facts: str = ""
    legal_issues: str = ""
    petitioner_arguments: str = ""
    respondent_arguments: str = ""
    evidence: str = ""
    statutes: str = ""
    question: str = ""

    top_k: int = Field(default=5, ge=1, le=20)

    use_graph: bool = True


class LegalQuery(BaseModel):
    full_query: str

    facts_query: str = ""
    issues_query: str = ""
    arguments_query: str = ""
    evidence_query: str = ""
    statutes_query: str = ""


class Passage(BaseModel):
    chunk_id: str
    doc_id: str

    case_name: str

    page: Optional[int] = None
    section: Optional[str] = None

    text: str

    lexical_score: Optional[float] = None
    semantic_score: Optional[float] = None
    graph_score: Optional[float] = None
    combined_score: Optional[float] = None

    relevance_reasons: List[str] = []


class Citation(BaseModel):
    citation_id: int

    chunk_id: str
    doc_id: str

    case_name: str

    page: Optional[int] = None
    section: Optional[str] = None

    supporting_text: str


class PrecedentResult(BaseModel):
    doc_id: str
    case_name: str

    score: Optional[float] = None

    reasons: List[str] = []

    passages: List[Passage] = []


class CaseAnalysisResponse(BaseModel):
    analysis: str

    precedents: List[PrecedentResult]

    citations: List[Citation]

    retrieval_mode: str