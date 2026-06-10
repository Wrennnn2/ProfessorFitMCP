import httpx
import pytest
from pytest_httpx import HTTPXMock

from professor_fit_mcp.services.dblp import DBLPService


@pytest.fixture
def svc():
    return DBLPService()


_SEARCH_RESPONSE = {
    "result": {
        "hits": {
            "@sent": "1",
            "hit": [
                {
                    "@score": "4",
                    "info": {
                        "author": "Percy Liang",
                        "url": "https://dblp.org/pid/46/5782",
                    },
                }
            ],
        }
    }
}

_PERSON_XML = """<?xml version="1.0"?>
<dblpperson name="Percy Liang" pid="46/5782" n="150">
<person key="homepages/46/5782" mdate="2025-01-01">
  <author pid="46/5782">Percy Liang</author>
  <note type="affiliation">Stanford University, USA</note>
  <note label="former" type="affiliation">UC Berkeley, USA</note>
  <url>https://cs.stanford.edu/~pliang/</url>
  <url>https://scholar.google.com/citations?user=xyz</url>
  <url>https://orcid.org/0000-0000-0000-0000</url>
</person>
  <r><article key="journals/corr/Liang2023" mdate="2023-01-01">
    <author>Percy Liang</author>
    <year>2023</year>
  </article></r>
  <r><article key="journals/corr/Liang2010" mdate="2010-01-01">
    <year>2010</year>
  </article></r>
</dblpperson>"""


@pytest.mark.asyncio
async def test_search_person(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(
        url=httpx.URL(
            "https://dblp.org/search/author/api",
            params={"q": "Percy Liang", "format": "json", "h": "5"},
        ),
        json=_SEARCH_RESPONSE,
    )
    results = await svc.search_person("Percy Liang")
    assert len(results) == 1
    assert results[0]["pid"] == "46/5782"
    assert results[0]["name"] == "Percy Liang"


@pytest.mark.asyncio
async def test_get_person_record(httpx_mock: HTTPXMock, svc):
    httpx_mock.add_response(
        url="https://dblp.org/pid/46/5782.xml",
        text=_PERSON_XML,
        headers={"content-type": "application/xml"},
    )
    record = await svc.get_person_record("46/5782")
    # homepage = first non-aggregator <url> (scholar/orcid excluded)
    assert record["homepage_url"] == "https://cs.stanford.edu/~pliang/"
    # current affiliation = non-former affiliation note
    assert record["affiliation"] == "Stanford University, USA"
    assert "UC Berkeley, USA" in record["former_affiliations"]
    assert record["first_pub_year"] == 2010
    assert record["pid"] == "46/5782"
