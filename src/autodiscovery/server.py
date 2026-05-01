from __future__ import annotations

import asyncio
import json
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .executor import APIExecutor
from .generator import generate_tools
from .parser import OpenAPIParser
from .registry import ToolRegistry

# ---------------------------------------------------------------------------
# Server and shared state
# ---------------------------------------------------------------------------

_registry = ToolRegistry()
_server = Server("mcp-autodiscovery")

# ---------------------------------------------------------------------------
# Meta-tool definitions (always present, never dynamically removed)
# ---------------------------------------------------------------------------

_DISCOVER_TOOL = types.Tool(
    name="discover_api",
    description=(
        "Load an OpenAPI spec from a URL or raw JSON/YAML string and register every "
        "operation as a callable MCP tool. After calling this, all registered tools "
        "appear in the tool list and can be invoked immediately."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": (
                    "URL pointing to an OpenAPI spec (JSON or YAML), "
                    "or the raw spec content as a string."
                ),
            },
            "api_name": {
                "type": "string",
                "description": (
                    "Short identifier for this API, e.g. 'github' or 'stripe'. "
                    "Used as the prefix for every registered tool name."
                ),
            },
            "base_url": {
                "type": "string",
                "description": (
                    "Base URL for API calls, e.g. 'https://api.github.com'. "
                    "Overrides the 'servers' field in the spec when provided."
                ),
            },
            "auth_header": {
                "type": "string",
                "description": "Header name for authentication, e.g. 'Authorization' or 'X-API-Key'.",
            },
            "auth_value": {
                "type": "string",
                "description": "Header value, e.g. 'Bearer <token>' or a raw API key.",
            },
        },
        "required": ["source", "api_name"],
    },
)

_LIST_APIS_TOOL = types.Tool(
    name="list_discovered_apis",
    description="List every API that has been discovered along with its registered tool count.",
    inputSchema={"type": "object", "properties": {}},
)

_FORGET_API_TOOL = types.Tool(
    name="forget_api",
    description="Unregister all tools belonging to a previously discovered API.",
    inputSchema={
        "type": "object",
        "properties": {
            "api_name": {
                "type": "string",
                "description": "The api_name used when the API was discovered.",
            },
        },
        "required": ["api_name"],
    },
)

_META_TOOLS: dict[str, types.Tool] = {
    t.name: t for t in [_DISCOVER_TOOL, _LIST_APIS_TOOL, _FORGET_API_TOOL]
}

# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@_server.list_tools()
async def list_tools() -> list[types.Tool]:
    return list(_META_TOOLS.values()) + _registry.get_all_tools()


@_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    if name == "discover_api":
        return await _handle_discover(arguments)
    if name == "list_discovered_apis":
        return _handle_list_apis()
    if name == "forget_api":
        return _handle_forget(arguments)
    if _registry.has_tool(name):
        return await _handle_dynamic(name, arguments)
    raise ValueError(f"Unknown tool: '{name}'")


# ---------------------------------------------------------------------------
# Meta-tool handlers
# ---------------------------------------------------------------------------


async def _handle_discover(args: dict[str, Any]) -> list[types.TextContent]:
    source: str = args["source"]
    api_name: str = args["api_name"]
    base_url: str | None = args.get("base_url")
    auth_header: str | None = args.get("auth_header")
    auth_value: str | None = args.get("auth_value")

    try:
        parser = OpenAPIParser()
        spec = await parser.load(source)
        tool_configs = generate_tools(spec, api_name, base_url, auth_header, auth_value)
        _registry.register_api(api_name, tool_configs)

        result = {
            "status": "success",
            "api_name": api_name,
            "tools_registered": len(tool_configs),
            "tool_names": [t.name for t, _ in tool_configs],
        }
    except Exception as exc:
        result = {"status": "error", "api_name": api_name, "error": str(exc)}

    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


def _handle_list_apis() -> list[types.TextContent]:
    apis = _registry.list_apis()
    payload = {"discovered_apis": apis, "total_tools": sum(v["tool_count"] for v in apis.values())}
    return [types.TextContent(type="text", text=json.dumps(payload, indent=2))]


def _handle_forget(args: dict[str, Any]) -> list[types.TextContent]:
    api_name: str = args["api_name"]
    removed = _registry.forget_api(api_name)
    result = {"status": "success", "api_name": api_name, "tools_removed": removed}
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


async def _handle_dynamic(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    config = _registry.get_tool_config(name)
    if config is None:
        raise ValueError(f"No execution config found for tool '{name}'")
    executor = APIExecutor()
    result = await executor.execute(config, arguments)
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await _server.run(
            read_stream,
            write_stream,
            _server.create_initialization_options(),
        )


def main_sync() -> None:
    asyncio.run(main())
