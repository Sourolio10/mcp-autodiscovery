from __future__ import annotations

import threading
from typing import Any

from mcp.types import Tool


class ToolRegistry:
    """Thread-safe in-memory store for dynamically discovered API tools."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._apis: dict[str, list[str]] = {}       # api_name → [tool_name, ...]
        self._tools: dict[str, Tool] = {}            # tool_name → Tool
        self._configs: dict[str, dict[str, Any]] = {} # tool_name → execution config

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def register_api(self, api_name: str, tool_configs: list[tuple[Tool, dict[str, Any]]]) -> None:
        with self._lock:
            self._drop_api(api_name)
            names: list[str] = []
            for tool, config in tool_configs:
                self._tools[tool.name] = tool
                self._configs[tool.name] = config
                names.append(tool.name)
            self._apis[api_name] = names

    def forget_api(self, api_name: str) -> int:
        with self._lock:
            return self._drop_api(api_name)

    def _drop_api(self, api_name: str) -> int:
        names = self._apis.pop(api_name, [])
        for name in names:
            self._tools.pop(name, None)
            self._configs.pop(name, None)
        return len(names)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_all_tools(self) -> list[Tool]:
        with self._lock:
            return list(self._tools.values())

    def get_tool_config(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            return self._configs.get(name)

    def list_apis(self) -> dict[str, Any]:
        with self._lock:
            return {
                api_name: {
                    "tool_count": len(names),
                    "tools": names,
                }
                for api_name, names in self._apis.items()
            }

    def has_tool(self, name: str) -> bool:
        with self._lock:
            return name in self._tools
