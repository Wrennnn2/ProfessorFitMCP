import pytest
from pytest_httpx import HTTPXMock
from professor_fit_mcp.services.homepage import HomepageService

_HTML_WITH_PROF = """
<html>
<head><title>Alice Smith - Associate Professor</title></head>
<body>
  <h1>Alice Smith</h1>
  <p>Associate Professor of Computer Science</p>
  <p>Email: <a href="mailto:alice@cs.example.edu">alice@cs.example.edu</a></p>
  <p><a href="https://ailab.example.edu">AI Research Lab</a></p>
  <p>I am looking for motivated PhD students to join my group.</p>
</body>
</html>
"""

_HTML_MINIMAL = """
<html><body><p>No useful info here.</p></body></html>
"""


@pytest.fixture
def svc():
    return HomepageService()


@pytest.mark.asyncio
async def test_extract_position(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(url="https://example.edu/alice", text=_HTML_WITH_PROF)
    result = await svc.fetch("https://example.edu/alice")
    assert result["position"] == "Associate Professor"


@pytest.mark.asyncio
async def test_extract_email(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(url="https://example.edu/alice", text=_HTML_WITH_PROF)
    result = await svc.fetch("https://example.edu/alice")
    assert result["email"] == "alice@cs.example.edu"


@pytest.mark.asyncio
async def test_extract_accepting_students_signal(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(url="https://example.edu/alice", text=_HTML_WITH_PROF)
    result = await svc.fetch("https://example.edu/alice")
    assert result["accepting_signal"] is not None
    assert result["accepting_signal"]["signal"] == "possibly_open"
    assert "looking for" in result["accepting_signal"]["snippet"].lower()


@pytest.mark.asyncio
async def test_no_position_found(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(url="https://example.edu/min", text=_HTML_MINIMAL)
    result = await svc.fetch("https://example.edu/min")
    assert result["position"] is None
    assert result["email"] is None
    assert result["accepting_signal"] is None


@pytest.mark.asyncio
async def test_fetch_error_returns_empty(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(url="https://example.edu/bad", status_code=404)
    result = await svc.fetch("https://example.edu/bad")
    assert result["position"] is None
    assert result["error"] is not None
