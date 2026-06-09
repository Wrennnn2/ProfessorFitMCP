import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from professor_fit_mcp.services.openalex import OpenAlexService


def _make_svc():
    return OpenAlexService(email="test@example.com")


def _author_response():
    return {
        "results": [
            {
                "id": "https://openalex.org/A123456",
                "display_name": "Percy Liang",
                "last_known_institutions": [
                    {"display_name": "Stanford University", "country_code": "US", "type": "education"}
                ],
                "summary_stats": {"h_index": 85, "i10_index": 120},
                "cited_by_count": 25000,
                "works_count": 150,
                "counts_by_year": [
                    {"year": 2024, "works_count": 8},
                    {"year": 2023, "works_count": 10},
                    {"year": 2022, "works_count": 9},
                ],
                "x_concepts": [
                    {"display_name": "Natural Language Processing", "score": 0.9},
                    {"display_name": "Machine Learning", "score": 0.8},
                ],
                "homepage_url": "https://cs.stanford.edu/~pliang/",
            }
        ]
    }


def _works_response():
    return {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "Holistic Evaluation of Language Models",
                "publication_year": 2024,
                "primary_location": {"source": {"display_name": "NeurIPS"}},
                "abstract_inverted_index": None,
                "authorships": [{"author": {"display_name": "Percy Liang"}}],
                "doi": "10.1234/test",
                "ids": {"arxiv": "https://arxiv.org/abs/2211.09110"},
            }
        ]
    }


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


def test_search_authors():
    svc = _make_svc()
    mock_resp = _mock_response(_author_response())

    async def _run():
        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await svc.search_authors("Percy Liang")

            call_args = client_instance.get.call_args
            assert "api.openalex.org/authors" in call_args[0][0]
            params = call_args[1]["params"]
            assert params["search"] == "Percy Liang"
            assert params["mailto"] == "test@example.com"

        assert len(results) == 1
        assert results[0]["openalex_id"] == "A123456"
        assert results[0]["name"] == "Percy Liang"
        assert results[0]["h_index"] == 85
        assert results[0]["institution"] == "Stanford University"
        assert results[0]["country_code"] == "US"
        assert results[0]["concepts"] == ["Natural Language Processing", "Machine Learning"]
        assert results[0]["homepage_url"] == "https://cs.stanford.edu/~pliang/"

    asyncio.run(_run())


def test_search_authors_with_institution_filter():
    svc = _make_svc()
    mock_resp = _mock_response(_author_response())

    async def _run():
        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await svc.search_authors("Percy Liang", institution="Stanford")

            call_args = client_instance.get.call_args
            params = call_args[1]["params"]
            assert "filter" in params
            assert "Stanford" in params["filter"]

    asyncio.run(_run())


def test_get_recent_works():
    svc = _make_svc()
    mock_resp = _mock_response(_works_response())

    async def _run():
        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            papers = await svc.get_recent_works("A123456", since_year=2022)

            call_args = client_instance.get.call_args
            assert "api.openalex.org/works" in call_args[0][0]
            params = call_args[1]["params"]
            assert "A123456" in params["filter"]
            assert "2022" in params["filter"]

        assert len(papers) == 1
        assert papers[0].title == "Holistic Evaluation of Language Models"
        assert papers[0].year == 2024
        assert papers[0].source == "openalex"
        assert papers[0].venue == "NeurIPS"
        assert papers[0].arxiv_id == "2211.09110"
        assert papers[0].authors == ["Percy Liang"]

    asyncio.run(_run())


def test_get_author():
    svc = _make_svc()
    author_data = _author_response()["results"][0]
    mock_resp = _mock_response(author_data)

    async def _run():
        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await svc.get_author("A123456")

            call_args = client_instance.get.call_args
            assert "api.openalex.org/authors/A123456" in call_args[0][0]

        assert result is not None
        assert result["openalex_id"] == "A123456"
        assert result["name"] == "Percy Liang"

    asyncio.run(_run())


def test_get_author_not_found():
    svc = _make_svc()
    mock_resp = _mock_response({}, status_code=404)

    async def _run():
        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(return_value=mock_resp)
            MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await svc.get_author("NONEXISTENT")

        assert result is None

    asyncio.run(_run())


def test_search_works_authors():
    svc = _make_svc()
    works_resp = _mock_response({
        "results": [
            {
                "id": "https://openalex.org/W1",
                "authorships": [
                    {"author": {"id": "https://openalex.org/A111", "display_name": "Alice"}},
                    {"author": {"id": "https://openalex.org/A222", "display_name": "Bob"}},
                ],
            },
            {
                "id": "https://openalex.org/W2",
                "authorships": [
                    {"author": {"id": "https://openalex.org/A111", "display_name": "Alice"}},
                ],
            },
        ],
    })
    author_detail = _author_response()["results"][0].copy()
    author_detail["id"] = "https://openalex.org/A111"
    author_resp = _mock_response(author_detail)

    async def _run():
        with patch("httpx.AsyncClient") as MockClient:
            client_instance = AsyncMock()
            client_instance.get = AsyncMock(side_effect=[works_resp, author_resp])
            MockClient.return_value.__aenter__ = AsyncMock(return_value=client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            results = await svc.search_works_authors("machine learning", limit=1)

        assert len(results) == 1
        assert results[0]["openalex_id"] == "A111"

    asyncio.run(_run())


def test_parse_abstract():
    from professor_fit_mcp.services.openalex import _parse_abstract

    inverted_index = {"Hello": [0], "world": [1], "this": [2], "is": [3], "a": [4], "test": [5]}
    assert _parse_abstract(inverted_index) == "Hello world this is a test"
    assert _parse_abstract(None) is None
    assert _parse_abstract({}) is None
