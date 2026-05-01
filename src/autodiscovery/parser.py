from __future__ import annotations

import json
from typing import Any

import httpx
import yaml


class OpenAPIParser:
    """Load and normalize an OpenAPI 3.x spec from a URL or raw JSON/YAML string."""

    async def load(self, source: str) -> dict[str, Any]:
        if source.startswith("http://") or source.startswith("https://"):
            content = await self._fetch(source)
        else:
            content = source

        spec = self._parse(content)
        self._assert_openapi(spec)
        return self._resolve_refs(spec, spec)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch(self, url: str) -> str:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    def _parse(self, content: str) -> dict[str, Any]:
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        result = yaml.safe_load(content)
        if not isinstance(result, dict):
            raise ValueError("Parsed spec is not a mapping")
        return result

    def _assert_openapi(self, spec: dict) -> None:
        if "openapi" not in spec and "swagger" not in spec:
            raise ValueError("Source does not appear to be an OpenAPI/Swagger spec")

    def _resolve_refs(self, node: Any, root: dict) -> Any:
        """Resolve all internal $ref pointers (e.g. '#/components/schemas/Pet')."""
        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str):
                ref = node["$ref"]
                if ref.startswith("#/"):
                    resolved = self._follow_ref(ref, root)
                    # Merge any sibling keys (allOf/description overrides) on top
                    siblings = {k: v for k, v in node.items() if k != "$ref"}
                    merged = {**self._resolve_refs(resolved, root), **siblings}
                    return merged
                # External refs passed through unchanged
                return node
            return {k: self._resolve_refs(v, root) for k, v in node.items()}
        if isinstance(node, list):
            return [self._resolve_refs(item, root) for item in node]
        return node

    def _follow_ref(self, ref: str, root: dict) -> Any:
        parts = ref.lstrip("#/").split("/")
        node: Any = root
        for part in parts:
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict):
                node = node[part]
            else:
                raise KeyError(f"Cannot navigate into {type(node)} with key '{part}'")
        return node
