from abc import ABC, abstractmethod
from typing import List

from app.schemas import LegalQuery, Passage


class Retriever(ABC):

    @abstractmethod
    def retrieve(
        self,
        query: LegalQuery,
        top_k: int = 5,
    ) -> List[Passage]:
        pass