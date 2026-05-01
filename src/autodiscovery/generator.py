from __future__ import annotations

import re
from typing import Any

from mcp.types import Tool

_SKIP_METHODS = {"head", "options", "trace"}
_PATH_ITEM_KEYS = _SKIP_METHODS | {"get", "put", "post", "delete", "patch", "parameters", "summary", "description", "servers"}


def generate_tools(
    spec: dict[str, Any],
    api_name: str,
    base_url: str | None,
    auth_header: str | None,
    auth_value: str | None,
) -> list[tuple[Tool, dict[str, Any]]]:
    """
    Parse an OpenAPI spec and return (Tool, execution_config) pairs — one per
    operation. The execution_config carries everything the HTTP executor needs
    to construct and fire the request without touching the spec again.
    """
    resolved_base = _resolve_base_url(spec, base_url)
    results: list[tuple[Tool, dict[str, Any]]] = []

    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue

        # Parameters declared at path level apply to all operations unless overridden
        path_level_params: dict[str, dict] = {
            p["name"]: p for p in path_item.get("parameters", []) if isinstance(p, dict)
        }

        for method, operation in path_item.items():
            if method in _SKIP_METHODS or method not in {"get", "put", "post", "delete", "patch"}:
                continue
            if not isinstance(operation, dict):
                continue

            # Operation params override path-level params with the same name
            op_params: dict[str, dict] = {
                p["name"]: p for p in operation.get("parameters", []) if isinstance(p, dict)
            }
            merged_params = list({**path_level_params, **op_params}.values())

            request_body = operation.get("requestBody")
            tool_name = _make_tool_name(api_name, method, path, operation)
            description = _make_description(method, path, operation)
            input_schema = _build_input_schema(merged_params, request_body)

            tool = Tool(
                name=tool_name,
                description=description,
                inputSchema=input_schema,
            )

            body_schema = _extract_body_schema(request_body)
            config: dict[str, Any] = {
                "method": method.upper(),
                "path": path,
                "base_url": resolved_base,
                # name → "path"|"query"|"header" for every declared parameter
                "param_locations": {p["name"]: p.get("in", "query") for p in merged_params},
                "has_body": request_body is not None,
                # True when body is an object whose properties are flattened into top-level args
                "body_flattened": _is_flat_object(body_schema),
                "auth_header": auth_header,
                "auth_value": auth_value,
            }

            results.append((tool, config))

    return results


# ------------------------------------------------------------------
# Name / description helpers
# ------------------------------------------------------------------

def _sanitize(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_]", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.lower()


def _make_tool_name(api_name: str, method: str, path: str, operation: dict) -> str:
    prefix = _sanitize(api_name)
    if "operationId" in operation:
        suffix = _sanitize(operation["operationId"])
    else:
        # GET /pets/{petId} → get_pets_pet_id
        suffix = _sanitize(f"{method}_{path}")
    return f"{prefix}__{suffix}"


def _make_description(method: str, path: str, operation: dict) -> str:
    parts: list[str] = []
    summary = operation.get("summary", "").strip()
    description = operation.get("description", "").strip()
    if summary:
        parts.append(summary)
    if description and description != summary:
        # Trim long descriptions to keep the tool list scannable
        parts.append(description[:300] + ("…" if len(description) > 300 else ""))
    if not parts:
        parts.append(f"{method.upper()} {path}")
    return " | ".join(parts)


# ------------------------------------------------------------------
# Input schema builder
# ------------------------------------------------------------------

def _build_input_schema(parameters: list[dict], request_body: dict | None) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param in parameters:
        name = param.get("name")
        if not name:
            continue
        prop: dict[str, Any] = dict(param.get("schema") or {"type": "string"})
        if "description" in param:
            prop["description"] = param["description"]
        if "example" in param:
            prop["examples"] = [param["example"]]
        properties[name] = prop
        # Path params are implicitly required; others follow the 'required' field
        if param.get("in") == "path" or param.get("required"):
            required.append(name)

    if request_body:
        body_schema = _extract_body_schema(request_body)
        if _is_flat_object(body_schema):
            # Flatten object properties into the top-level schema
            for prop_name, prop_schema in body_schema.get("properties", {}).items():
                properties[prop_name] = prop_schema
            body_required = body_schema.get("required", [])
            if request_body.get("required") and body_required:
                required.extend(body_required)
        elif body_schema:
            # Non-object body: expose as a single __body argument
            properties["__body"] = {**body_schema, "description": "Request body"}
            if request_body.get("required"):
                required.append("__body")

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        # Deduplicate while preserving order
        seen: set[str] = set()
        schema["required"] = [r for r in required if not (r in seen or seen.add(r))]  # type: ignore[func-returns-value]
    return schema


def _extract_body_schema(request_body: dict | None) -> dict[str, Any]:
    if not request_body:
        return {}
    content = request_body.get("content") or {}
    json_content = content.get("application/json") or {}
    return json_content.get("schema") or {}


def _is_flat_object(schema: dict[str, Any]) -> bool:
    return schema.get("type") == "object" and "properties" in schema


# ------------------------------------------------------------------
# Base URL resolution
# ------------------------------------------------------------------

def _resolve_base_url(spec: dict[str, Any], override: str | None) -> str:
    if override:
        return override.rstrip("/")
    servers = spec.get("servers") or []
    if servers and isinstance(servers[0], dict):
        return servers[0].get("url", "").rstrip("/")
    # Swagger 2.x fallback
    host = spec.get("host", "")
    base_path = spec.get("basePath", "/").rstrip("/")
    schemes = spec.get("schemes", ["https"])
    scheme = schemes[0] if schemes else "https"
    return f"{scheme}://{host}{base_path}" if host else ""
