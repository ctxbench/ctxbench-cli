from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.datasets.lattes.mcp_server import LattesMCPServer
from copa.datasets.lattes.provider import LattesProvider
from copa.datasets.lattes.tools import LattesToolService


def _contexts_dir() -> str:
    return str((Path.cwd() / "datasets" / "lattes" / "context").resolve())


def test_provider_lists_and_returns_sections():
    provider = LattesProvider()

    sections = provider.list_sections(contexts_dir=_contexts_dir(), lattes_id="2342739419247924")
    profile = provider.get_section(
        contexts_dir=_contexts_dir(),
        lattes_id="2342739419247924",
        section_name="profile",
    )

    assert "profile" in sections
    assert isinstance(profile, dict)
    assert "summary" in profile


def test_tool_service_exposes_section_tools():
    service = LattesToolService(contexts_dir=_contexts_dir())

    tools = service.list_tools()
    sections = service.call_tool("listSections", {"lattesId": "2342739419247924"}).content
    profile = service.call_tool(
        "getSection",
        {"lattesId": "2342739419247924", "sectionName": "profile"},
    ).content

    assert {tool.name for tool in tools} == {"listSections", "getSection"}
    assert "profile" in sections
    assert isinstance(profile, dict)


def test_mcp_server_routes_section_tools():
    server = LattesMCPServer(contexts_dir=_contexts_dir())

    tools = server.list_tools()
    result = server.call_tool(
        "getSection",
        {"lattesId": "2342739419247924", "sectionName": "profile"},
    )

    assert any(tool.name == "getSection" for tool in tools)
    assert isinstance(result.content, dict)
