from professor_fit_mcp.models.common import SourcedField
from professor_fit_mcp.models.paper import Paper
from professor_fit_mcp.models.professor import Professor, compute_seniority


def test_sourced_field_defaults():
    f = SourcedField(value=None)
    assert f.confidence == "unknown"
    assert f.sources == []


def test_sourced_field_with_data():
    f = SourcedField(value="Stanford University", sources=["openalex", "homepage"], confidence="high")
    assert f.value == "Stanford University"
    assert len(f.sources) == 2


def test_paper_minimal():
    p = Paper(title="Test Paper", year=2024, source="openalex")
    assert p.title == "Test Paper"
    assert p.abstract is None


def test_professor_minimal():
    prof = Professor(openalex_id="A123", name="Alice Smith")
    assert prof.openalex_id == "A123"
    assert prof.relevance_signal is None
    assert prof.concepts == []


def test_compute_seniority():
    assert compute_seniority(2024) == "new_ap"
    assert compute_seniority(2020) == "early"
    assert compute_seniority(2014) == "mid-career"
    assert compute_seniority(2005) == "senior"


def test_professor_dict_serialization():
    prof = Professor(openalex_id="A123", name="Alice Smith")
    d = prof.model_dump()
    assert d["openalex_id"] == "A123"
    assert "recent_papers" in d
