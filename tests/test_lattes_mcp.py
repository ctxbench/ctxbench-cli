from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.ai.models.base import AIRequest
from copa.datasets.lattes.mcp_server import LattesMCPServer
from copa.datasets.lattes.provider import LattesProvider
from copa.datasets.lattes.readers.html_reader import HtmlLattesReader
from copa.datasets.lattes.readers.json_reader import JsonLattesReader
from copa.datasets.lattes.tools import call_lattes_tool


def _fixture(name: str) -> Path:
    return Path.cwd() / "datasets" / "lattes" / "cvs" / name


def test_json_reader_extracts_publications_and_profile():
    reader = JsonLattesReader()

    curriculum = reader.read(str(_fixture("nabor.json")))

    assert curriculum.profile.name == "Nabor das Chagas Mendonça"
    assert curriculum.publications
    assert curriculum.publications[0].title == (
        "Performance and Resilience Impact of Microservice Granularity: An Empirical Evaluation Using Service Weaver and Amazon EKS"
    )
    assert curriculum.publications[0].kind == "journal"
    assert curriculum.publications[0].year == 2025
    assert curriculum.publications[0].doi == "10.1002/nem.70019"


def test_json_reader_tolerates_malformed_publications(tmp_path: Path):
    payload = {
        "meta": {"lattesId": "1"},
        "profile": {"name": "Example"},
        "production": {
            "bibliographical": [
                {"category": "Artigos completos publicados em periódicos", "year": 2024, "title": "Valid title"},
                "broken",
                {"category": "Trabalhos completos publicados em anais de congressos", "text": "AUTHOR . Partial title. Venue, 2023."},
            ]
        },
    }
    target = tmp_path / "sample.json"
    target.write_text(json.dumps(payload), encoding="utf-8")

    curriculum = JsonLattesReader().read(str(target))

    assert len(curriculum.publications) == 2
    assert curriculum.publications[1].title == "Partial title"
    assert curriculum.publications[1].year == 2023


def test_html_reader_extracts_publications_research_and_education():
    reader = HtmlLattesReader()

    curriculum = reader.read(str(_fixture("nabor.html")))

    assert curriculum.profile.name == "Nabor das Chagas Mendonça"
    assert "Arquitetura de software" in curriculum.research.lines_of_research
    assert curriculum.education
    assert curriculum.publications
    assert any(publication.year == 2026 for publication in curriculum.publications)
    assert any(publication.kind == "conference" for publication in curriculum.publications)


def test_html_reader_supports_latin1_documents(tmp_path: Path):
    source = _fixture("nabor.html").read_text(encoding="utf-8")
    latin1_path = tmp_path / "latin1.html"
    latin1_path.write_bytes(source.encode("latin-1", errors="ignore"))

    curriculum = HtmlLattesReader().read(str(latin1_path))

    assert curriculum.profile.name == "Nabor das Chagas Mendonça"
    assert curriculum.publications
    assert any(publication.kind == "journal" for publication in curriculum.publications)


def test_provider_binds_once_and_filters_publications_and_projects():
    class CountingReader:
        def __init__(self) -> None:
            self.calls = 0

        def read(self, path: str):
            self.calls += 1
            return JsonLattesReader().read(path)

    reader = CountingReader()
    provider = LattesProvider(readers={"json": reader})
    path = str(_fixture("nabor.json"))

    provider.bind(path=path, fmt="json")
    provider.bind(path=path, fmt="json")

    assert reader.calls == 1
    publications_2026 = provider.get_publications(start_year=2026, end_year=2026)
    assert len(publications_2026) == 3
    assert all(publication.year == 2026 for publication in publications_2026)
    projects_after_2020 = provider.get_projects(start_year=2020)
    assert projects_after_2020
    assert all(project.start_year is not None and project.start_year >= 2020 for project in projects_after_2020)


def test_provider_skips_entries_without_year_when_filtering():
    class NoYearReader:
        def read(self, path: str):
            curriculum = JsonLattesReader().read(str(_fixture("nabor.json")))
            curriculum.publications.append(
                curriculum.publications[0].model_copy(update={"year": None, "title": "No year"})
            )
            return curriculum

    provider = LattesProvider(readers={"json": NoYearReader()})
    provider.bind(path=str(_fixture("nabor.json")), fmt="json")

    filtered = provider.get_publications(start_year=2024)

    assert all(publication.year is not None for publication in filtered)
    assert all(publication.title != "No year" for publication in filtered)


def test_list_publications_tool_supports_all_filter_modes():
    provider = LattesProvider()
    provider.bind(path=str(_fixture("nabor.json")), fmt="json")

    all_items = call_lattes_tool(provider, "listPublications", {}).content
    start_only = call_lattes_tool(provider, "listPublications", {"startYear": 2026}).content
    end_only = call_lattes_tool(provider, "listPublications", {"endYear": 1995}).content
    bounded = call_lattes_tool(provider, "listPublications", {"startYear": 2026, "endYear": 2026}).content
    empty = call_lattes_tool(provider, "listPublications", {"startYear": 2100}).content

    assert len(all_items) >= len(start_only) >= len(bounded)
    assert all(item["year"] >= 2026 for item in start_only)
    assert all(item["year"] <= 1995 for item in end_only)
    assert {item["year"] for item in bounded} == {2026}
    assert empty == []


def test_mcp_server_binds_provider_using_context_path():
    provider = LattesProvider()
    server = LattesMCPServer(provider=provider)
    request = AIRequest(
        question="How many publications?",
        context="ignored in MCP",
        provider_name="mock",
        model_name="mock",
        strategy_name="mcp",
        context_format="json",
        params={},
        metadata={"context_path": str(_fixture("nabor.json"))},
    )

    server.bind(request)
    result = server.call_tool("listPublications", {"startYear": 2026, "endYear": 2026})

    assert len(result.content) == 3
