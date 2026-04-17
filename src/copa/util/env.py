from __future__ import annotations

import os
import re
from typing import Any


_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def resolve_env_placeholders(value: Any) -> Any:
    if isinstance(value, str):
        return _resolve_string(value)
    if isinstance(value, list):
        return [resolve_env_placeholders(item) for item in value]
    if isinstance(value, dict):
        env_name = value.get("$env")
        if isinstance(env_name, str):
            default = value.get("default")
            return _resolve_env_var(env_name, default if default is None or isinstance(default, str) else str(default))
        return {key: resolve_env_placeholders(item) for key, item in value.items()}
    return value


def apply_lattes_mcp_env_overrides(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    config = value.get("mcp_server")
    if not isinstance(config, dict):
        return value

    resolved = dict(config)
    server_url = os.getenv("LATTES_MCP_URL")
    auth_token = os.getenv("LATTES_MCP_TOKEN")

    if server_url:
        resolved["server_url"] = server_url
        resolved.pop("url", None)
    if auth_token:
        resolved["auth_token"] = auth_token
        headers = dict(resolved.get("headers") or {})
        headers.pop("Authorization", None)
        headers.pop("authorization", None)
        resolved["headers"] = headers

    if "authorization" in resolved and "auth_token" not in resolved:
        resolved["auth_token"] = resolved.pop("authorization")
    else:
        resolved.pop("authorization", None)

    auth_token_value = resolved.get("auth_token")
    if isinstance(auth_token_value, str) and auth_token_value:
        headers = dict(resolved.get("headers") or {})
        headers.pop("Authorization", None)
        headers.pop("authorization", None)
        resolved["headers"] = headers

    payload = dict(value)
    payload["mcp_server"] = resolved
    return payload


def _resolve_string(value: str) -> str:
    match = _ENV_PATTERN.fullmatch(value)
    if match:
        env_name, default = match.groups()
        return _resolve_env_var(env_name, default)

    def replace(match_obj: re.Match[str]) -> str:
        env_name, default = match_obj.groups()
        return _resolve_env_var(env_name, default)

    return _ENV_PATTERN.sub(replace, value)


def _resolve_env_var(name: str, default: str | None = None) -> str:
    env_value = os.getenv(name)
    if env_value is not None:
        return env_value
    if default is not None:
        return default
    raise ValueError(f"Missing required environment variable: {name}")
