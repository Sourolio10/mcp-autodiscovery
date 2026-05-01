"""
End-to-end demo: discover a real public API and call one of its tools.
Run: python demo.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from autodiscovery.parser import OpenAPIParser
from autodiscovery.generator import generate_tools
from autodiscovery.registry import ToolRegistry
from autodiscovery.executor import APIExecutor

# Public OpenAPI spec — no auth needed
SPEC_URL = "https://raw.githubusercontent.com/open-meteo/open-meteo/main/openapi.yml"
API_NAME = "weather"
BASE_URL = "https://api.open-meteo.com"


def separator(title: str) -> None:
    print(f"\n{'-' * 60}")
    print(f"  {title}")
    print('-' * 60)


async def main() -> None:
    registry = ToolRegistry()

    # ── Step 1: Load spec ──────────────────────────────────────────
    separator("STEP 1 — Loading OpenAPI spec")
    print(f"  Source: {SPEC_URL}")
    parser = OpenAPIParser()
    spec = await parser.load(SPEC_URL)
    print(f"  Title:  {spec.get('info', {}).get('title')}")
    print(f"  Paths:  {len(spec.get('paths', {}))}")

    # ── Step 2: Generate tools ─────────────────────────────────────
    separator("STEP 2 — Generating MCP tools from spec")
    tool_configs = generate_tools(spec, API_NAME, BASE_URL, None, None)
    registry.register_api(API_NAME, tool_configs)

    all_tools = registry.get_all_tools()
    print(f"  {len(all_tools)} tools registered:\n")
    for tool in all_tools:
        params = list(tool.inputSchema.get("properties", {}).keys())
        param_str = ", ".join(params) if params else "-"
        print(f"    * {tool.name}")
        print(f"      {tool.description[:80]}{'...' if len(tool.description) > 80 else ''}")
        print(f"      params: {param_str}\n")

    # ── Step 3: Call a tool live ───────────────────────────────────
    separator("STEP 3 - Calling weather forecast tool (Atlanta, GA)")

    tool_name = next((t.name for t in all_tools), None)

    if not tool_name:
        print("  No tool found.")
        return

    print(f"  Calling: {tool_name}")
    config = registry.get_tool_config(tool_name)
    executor = APIExecutor()
    # Atlanta coordinates
    result = await executor.execute(config, {
        "latitude": 33.749,
        "longitude": -84.388,
        "current": "temperature_2m,wind_speed_10m",
        "forecast_days": 1,
    })

    print(f"  Status code : {result['status_code']}")
    print(f"  Success     : {result['success']}")
    data = result["data"]
    if isinstance(data, dict) and "current" in data:
        current = data["current"]
        units = data.get("current_units", {})
        print(f"  Location    : lat={data.get('latitude')}  lon={data.get('longitude')}")
        print(f"  Temperature : {current.get('temperature_2m')} {units.get('temperature_2m', '')}")
        print(f"  Wind speed  : {current.get('wind_speed_10m')} {units.get('wind_speed_10m', '')}")
        print(f"  Time        : {current.get('time')}")
    else:
        print(f"  Response: {json.dumps(data, indent=2)[:400]}")

    # ── Step 4: Show what forget_api does ──────────────────────────
    separator("STEP 4 — Forgetting the API")
    removed = registry.forget_api(API_NAME)
    print(f"  Removed {removed} tools.")
    print(f"  Tools remaining: {len(registry.get_all_tools())}")

    separator("DONE — Full pipeline works end-to-end")


if __name__ == "__main__":
    asyncio.run(main())
