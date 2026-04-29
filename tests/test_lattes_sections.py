from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.datasets.lattes.mcp_server import LattesMCPServer
from copa.datasets.lattes.provider import LattesProvider
from copa.datasets.lattes.tools import LattesToolService, PUBLICATION_TYPE_ENUM, PUBLICATIONS_DESCRIPTION


def _contexts_dir() -> str:
    return str((Path.cwd() / "datasets" / "lattes" / "context").resolve())


def test_provider_returns_resource_payloads_and_filters_years():
    provider = LattesProvider()

    profile = provider.get_profile(
        contexts_dir=_contexts_dir(),
        lattes_id="2342739419247924",
    )
    publications = provider.get_publications(
        contexts_dir=_contexts_dir(),
        lattes_id="2342739419247924",
        start_year=2025,
        end_year=2026,
    )

    assert isinstance(profile, dict)
    assert "summary" in profile
    assert isinstance(publications, dict)
    assert publications["items"]
    assert all(2025 <= int(item["year"]) <= 2026 for item in publications["items"] if isinstance(item, dict) and "year" in item)


def test_provider_filters_publications_by_coauthor_and_type():
    provider = LattesProvider()

    publications = provider.get_publications(
        contexts_dir=_contexts_dir(),
        lattes_id="2342739419247924",
        coauthors=["Fabio Kon"],
        publication_type="journal",
    )

    assert publications["items"]
    assert all(
        isinstance(item, dict)
        and any(provider._text_contains_name(author, "Fabio Kon") for author in item.get("authors", []) if isinstance(author, str))
        and "periodicos" in provider._normalize_text(str(item.get("category", "")))
        for item in publications["items"]
    )


def test_tool_service_exposes_resource_tools():
    service = LattesToolService(contexts_dir=_contexts_dir())

    tools = service.list_tools()
    profile = service.call_tool(
        "get_profile",
        {"lattes_id": "2342739419247924"},
    ).content
    advisees = service.call_tool(
        "get_advisees",
        {"lattes_id": "2342739419247924"},
    ).content
    education = service.call_tool(
        "get_education",
        {"lattes_id": "2342739419247924", "start_year": 1995, "end_year": 2000},
    ).content

    assert "get_profile" in {tool.name for tool in tools}
    assert "get_publications" in {tool.name for tool in tools}
    assert "get_advisees" in {tool.name for tool in tools}
    assert isinstance(profile, dict)
    assert isinstance(advisees, dict)
    assert advisees["items"]
    assert {"level", "status", "student", "role"}.issubset(advisees["items"][0].keys())
    assert isinstance(education, dict)
    assert "items" in education


def test_publications_tool_uses_closed_enum_and_updated_guidance():
    service = LattesToolService(contexts_dir=_contexts_dir())

    publications_tool = next(tool for tool in service.list_tools() if tool.name == "get_publications")

    publication_type_schema = publications_tool.input_schema["properties"]["publication_type"]

    assert publications_tool.description == PUBLICATIONS_DESCRIPTION
    assert publication_type_schema["anyOf"][0]["enum"] == list(PUBLICATION_TYPE_ENUM)
    assert publication_type_schema["anyOf"][1] == {"type": "null"}


def test_provider_returns_grouped_supervisions():
    provider = LattesProvider()

    supervisions = provider.get_supervisions(
        contexts_dir=_contexts_dir(),
        lattes_id="9674541381385819",
    )

    assert isinstance(supervisions, dict)
    assert "masters" in supervisions
    assert "doctoral" in supervisions
    assert "undergraduate" in supervisions
    assert isinstance(supervisions["masters"]["completed"], list)
    assert isinstance(supervisions["masters"]["ongoing"], list)


def test_mcp_server_routes_resource_tools():
    server = LattesMCPServer(contexts_dir=_contexts_dir())

    tools = server.list_tools()
    result = server.call_tool(
        "get_profile",
        {"lattes_id": "2342739419247924"},
    )

    assert any(tool.name == "get_profile" for tool in tools)
    assert any(tool.name == "get_advisees" for tool in tools)
    assert any(tool.name == "get_publications" and tool.description == PUBLICATIONS_DESCRIPTION for tool in tools)
    assert isinstance(result.content, dict)
