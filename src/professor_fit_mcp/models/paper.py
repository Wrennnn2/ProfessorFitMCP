from typing import Optional

from pydantic import BaseModel


class Paper(BaseModel):
    title: str
    authors: list[str] = []
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    url: Optional[str] = None
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    source: str  # "openalex" | "dblp" | "arxiv"
