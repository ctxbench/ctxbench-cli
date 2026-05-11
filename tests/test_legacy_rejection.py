from __future__ import annotations

import pytest

from copa.cli import build_parser


@pytest.mark.legacy_rejection
@pytest.mark.parametrize("command", ["query", "exec"])
def test_legacy_query_and_exec_commands_are_rejected(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args([command])

    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "invalid choice" in err
    assert f"'{command}'" in err


@pytest.mark.legacy_rejection
@pytest.mark.parametrize("flag", ["--question", "--repeat", "--ids"])
def test_legacy_selector_flags_are_rejected(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["execute", flag, "value"])

    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "unrecognized arguments" in err
    assert flag in err
