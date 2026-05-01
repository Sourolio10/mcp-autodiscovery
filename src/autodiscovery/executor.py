from __future__ import annotations

from typing import Any

import httpx


class APIExecutor:
    """Construct and fire an HTTP request from a tool call + its execution config."""

    async def execute(self, config: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
        method = config["method"]
        base_url = config["base_url"]
        path_template = config["path"]
        param_locations: dict[str, str] = config["param_locations"]
        auth_header: str | None = config.get("auth_header")
        auth_value: str | None = config.get("auth_value")
        has_body: bool = config.get("has_body", False)
        body_flattened: bool = config.get("body_flattened", True)

        path_params: dict[str, Any] = {}
        query_params: dict[str, Any] = {}
        header_params: dict[str, Any] = {}
        body_params: dict[str, Any] = {}

        for key, value in arguments.items():
            if key == "__body":
                body_params = value if isinstance(value, dict) else {"value": value}
                continue

            location = param_locations.get(key)
            if location == "path":
                path_params[key] = value
            elif location == "header":
                header_params[key] = value
            elif location == "query":
                query_params[key] = value
            else:
                # Unknown param: route to body if request has one, else query string
                if has_body:
                    body_params[key] = value
                else:
                    query_params[key] = value

        url = self._build_url(base_url, path_template, path_params)
        headers = dict(header_params)
        if auth_header and auth_value:
            headers[auth_header] = auth_value

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            kwargs: dict[str, Any] = {
                "method": method,
                "url": url,
                "headers": headers,
            }
            if query_params:
                kwargs["params"] = query_params
            if body_params and method in ("POST", "PUT", "PATCH"):
                kwargs["json"] = body_params

            response = await client.request(**kwargs)

        return {
            "status_code": response.status_code,
            "success": response.is_success,
            "headers": dict(response.headers),
            "data": self._parse_response(response),
        }

    def _build_url(self, base_url: str, path_template: str, path_params: dict[str, Any]) -> str:
        url = base_url + path_template
        for name, value in path_params.items():
            url = url.replace(f"{{{name}}}", str(value))
        return url

    def _parse_response(self, response: httpx.Response) -> Any:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                return response.json()
            except Exception:
                pass
        return response.text
