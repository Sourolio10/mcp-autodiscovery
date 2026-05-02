"""
Interactive catalog runner.
Usage: python run.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from getpass import getpass

import yaml

sys.path.insert(0, str(Path(__file__).parent / "src"))

from autodiscovery.parser import OpenAPIParser
from autodiscovery.generator import generate_tools
from autodiscovery.registry import ToolRegistry
from autodiscovery.executor import APIExecutor

CATALOG_PATH = Path(__file__).parent / "catalog" / "apis.yml"

# ── ANSI colours ────────────────────────────────────────────────────
R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

VIOLET = "\033[38;5;141m"
BLUE = "\033[38;5;75m"
CYAN = "\033[38;5;87m"
GREEN = "\033[38;5;114m"
YELLOW = "\033[38;5;221m"
ORANGE = "\033[38;5;215m"
RED = "\033[38;5;210m"
PINK = "\033[38;5;213m"
GRAY = "\033[38;5;245m"
WHITE = "\033[38;5;255m"


def c(text: str, colour: str) -> str:
    return f"{colour}{text}{R}"


def bar(char: str = "-", n: int = 62) -> str:
    return c(char * n, GRAY)


def section(title: str, colour: str = CYAN) -> None:
    print(f"\n{bar()}")
    print(c(f"  {title}", colour + BOLD))
    print(bar())


# ── Catalog loading ─────────────────────────────────────────────────

def load_catalog() -> list[dict]:
    with open(CATALOG_PATH) as f:
        data = yaml.safe_load(f)
    return data["apis"]


def print_menu(apis: list[dict]) -> None:
    print(f"\n{c('mcp-autodiscovery', VIOLET + BOLD)}  {c('API Catalog', WHITE + BOLD)}\n")

    no_auth = [a for a in apis if a.get("auth_type", "none") == "none"]
    needs_auth = [a for a in apis if a.get("auth_type", "none") != "none"]

    idx = 1
    print(c("  No API key required", GREEN + BOLD))
    for api in no_auth:
        api["_idx"] = idx
        print(f"  {c(str(idx), CYAN + BOLD)}  {c(api['name'], WHITE)}  {c(api['description'], GRAY)}")
        idx += 1

    print(f"\n{c('  API key required', YELLOW + BOLD)}")
    for api in needs_auth:
        api["_idx"] = idx
        note = f"  {c('(' + api['note'] + ')', ORANGE)}" if api.get("note") else ""
        print(f"  {c(str(idx), YELLOW + BOLD)}  {c(api['name'], WHITE)}  {c(api['description'], GRAY)}{note}")
        idx += 1

    print(f"\n  {c('0', RED)}  Exit\n")


def pick_api(apis: list[dict]) -> dict | None:
    all_apis = sorted(apis, key=lambda a: a["_idx"])
    while True:
        try:
            raw = input(c("  Pick a number: ", VIOLET + BOLD)).strip()
            n = int(raw)
        except (ValueError, EOFError):
            print(c("  Please enter a number.", RED))
            continue
        if n == 0:
            return None
        match = next((a for a in all_apis if a["_idx"] == n), None)
        if match:
            return match
        print(c(f"  No API #{n}. Try again.", RED))


def prompt_auth(api: dict) -> tuple[str | None, str | None]:
    auth_type = api.get("auth_type", "none")
    auth_header = api.get("auth_header")
    if auth_type == "none":
        return None, None

    labels = {
        "bearer": "Bearer token (will be sent as 'Bearer <token>')",
        "api_key": f"API key (header: {auth_header})",
        "basic": "Base64-encoded 'username:password'",
    }
    label = labels.get(auth_type, "credential")
    print(f"\n  {c(api['name'], WHITE)} requires authentication.")
    print(f"  {c(label, GRAY)}")
    raw = getpass(c("  Enter value (input hidden): ", YELLOW))
    if not raw.strip():
        print(c("  Skipped — some calls may fail with 401.", ORANGE))
        return None, None

    value = f"Bearer {raw.strip()}" if auth_type == "bearer" else raw.strip()
    return auth_header, value


# ── Core pipeline ───────────────────────────────────────────────────

async def run_api(api: dict) -> None:
    registry = ToolRegistry()

    # Step 1: load spec
    section(f"STEP 1  Loading  {api['name']}", BLUE)
    print(f"  {c('Spec:', GRAY)} {api['spec_url']}")
    if api.get("note"):
        print(f"  {c('Note:', ORANGE)} {api['note']}")

    try:
        parser = OpenAPIParser()
        spec = await parser.load(api["spec_url"])
    except Exception as exc:
        print(c(f"\n  Failed to load spec: {exc}", RED))
        return

    title = spec.get("info", {}).get("title", "?")
    paths = len(spec.get("paths", {}))
    print(f"  {c('Title:', GRAY)} {title}")
    print(f"  {c('Paths:', GRAY)} {paths}")

    # Step 2: auth
    auth_header, auth_value = prompt_auth(api)

    # Step 3: generate + register
    section("STEP 2  Registering tools", GREEN)
    tool_configs = generate_tools(spec, api["id"], api.get("base_url"), auth_header, auth_value)
    registry.register_api(api["id"], tool_configs)
    tools = registry.get_all_tools()
    print(f"  {c(str(len(tools)), GREEN + BOLD)} tools registered:\n")

    # Print first 20 tools, summarise the rest
    shown = tools[:20]
    for t in shown:
        params = list(t.inputSchema.get("properties", {}).keys())
        param_str = ", ".join(params[:6]) + (" ..." if len(params) > 6 else "") if params else "-"
        print(f"  {c('*', PINK)} {c(t.name, WHITE)}")
        print(f"    {c(t.description[:90] + ('...' if len(t.description) > 90 else ''), GRAY)}")
        print(f"    {c('params:', DIM)} {c(param_str, GRAY)}\n")

    if len(tools) > 20:
        print(f"  {c(f'... and {len(tools) - 20} more tools', GRAY)}\n")

    # Step 4: example call
    pattern = api.get("example_tool_pattern", "")
    example_tool = next((t for t in tools if pattern.lower() in t.name.lower()), tools[0] if tools else None)

    if not example_tool:
        print(c("\n  No tools to call — skipping example.", GRAY))
        return

    example_args = api.get("example_args") or {}
    section(f"STEP 3  Calling  {example_tool.name}", ORANGE)
    print(f"  {c('Args:', GRAY)} {json.dumps(example_args, ensure_ascii=False)}")

    config = registry.get_tool_config(example_tool.name)
    executor = APIExecutor()
    try:
        result = await executor.execute(config, example_args)
    except Exception as exc:
        print(c(f"\n  Request failed: {exc}", RED))
        return

    status_colour = GREEN if result["success"] else RED
    print(f"\n  {c('Status:', GRAY)} {c(str(result['status_code']), status_colour + BOLD)}")
    print(f"  {c('Success:', GRAY)} {c(str(result['success']), status_colour)}")

    hint = api.get("result_hint")
    if hint:
        print(f"  {c('Hint:', GRAY)} {hint}")

    data = result["data"]
    pretty = json.dumps(data, indent=2, ensure_ascii=False)
    lines = pretty.splitlines()
    preview = "\n".join(f"    {l}" for l in lines[:30])
    print(f"\n{c(preview, CYAN)}")
    if len(lines) > 30:
        print(c(f"    ... ({len(lines) - 30} more lines)", GRAY))

    # Step 5: cleanup
    section("STEP 4  Cleanup", VIOLET)
    removed = registry.forget_api(api["id"])
    print(f"  {c(str(removed), VIOLET + BOLD)} tools removed.  Registry: {c(str(len(registry.get_all_tools())), GREEN)} remaining.")

    section("DONE", GREEN)


# ── Entry point ─────────────────────────────────────────────────────

async def main() -> None:
    # Enable ANSI on Windows
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

    apis = load_catalog()
    print_menu(apis)

    # Accept number directly as CLI arg: python run.py 1
    if len(sys.argv) > 1:
        try:
            n = int(sys.argv[1])
            all_apis = sorted(apis, key=lambda a: a["_idx"])
            api = next((a for a in all_apis if a["_idx"] == n), None)
            if api is None:
                print(c(f"  No API #{n} in catalog.", RED))
                return
            print(c(f"  Selected: {api['name']}", VIOLET + BOLD))
        except ValueError:
            print(c(f"  Invalid argument '{sys.argv[1]}'. Pass a number from the menu.", RED))
            return
    else:
        api = pick_api(apis)
        if api is None:
            print(c("\n  Bye!\n", GRAY))
            return

    await run_api(api)


if __name__ == "__main__":
    asyncio.run(main())
