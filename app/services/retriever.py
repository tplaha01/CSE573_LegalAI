from abc import ABC, abstractmethod
from typing import List, Optional

from app.schemas import Passage


class Retriever(ABC):

    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        as_of_year: Optional[int] = None,
        exclude_doc_id: Optional[str] = None,
    ) -> List[Passage]:
        pass