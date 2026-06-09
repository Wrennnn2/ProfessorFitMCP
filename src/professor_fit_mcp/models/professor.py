from typing import Optional

from pydantic import BaseModel, Field

from .common import SourcedField
from .paper import Paper


def compute_seniority(first_pub_year: int, current_year: int = 2026) -> str:
    """Estimate seniority from first publication year."""
    years = current_year - first_pub_year
    if years <= 3:
        return "new_ap"
    elif years <= 7:
        return "early"
    elif years <= 15:
        return "mid-career"
    else:
        return "senior"


class Professor(BaseModel):
    openalex_id: str
    dblp_pid: Optional[str] = None
    name: str
    institution: SourcedField = Field(default_factory=SourcedField)
    country_code: Optional[str] = None
    institution_tier: Optional[str] = None
    position: SourcedField = Field(default_factory=SourcedField)
    is_pi: SourcedField = Field(default_factory=SourcedField)
    h_index: SourcedField = Field(default_factory=SourcedField)
    citation_count: SourcedField = Field(default_factory=SourcedField)
    works_count: Optional[int] = None
    papers_last_3_years: Optional[int] = None
    first_pub_year: Optional[int] = None
    seniority: Optional[str] = None
    seniority_source: str = "unknown"
    homepage_url: Optional[str] = None
    homepage_source: Optional[str] = None
    homepage_search_query: Optional[str] = None
    concepts: list[str] = []
    recent_papers: list[Paper] = []
    email: Optional[str] = None
    lab_name: Optional[str] = None
    lab_url: Optional[str] = None
    accepting_students_signal: Optional[dict] = None
    relevance_signal: Optional[float] = None
