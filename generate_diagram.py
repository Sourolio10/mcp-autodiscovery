"""Generate architecture diagram image for README."""
import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
except ImportError:
    print("Installing matplotlib...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib"])
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ── Canvas ─────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(18, 10))
ax.set_xlim(0, 18)
ax.set_ylim(0, 10)
ax.axis("off")
fig.patch.set_facecolor("#0F1117")
ax.set_facecolor("#0F1117")

# ── Colour palette ──────────────────────────────────────────────────
C = {
    "bg":        "#0F1117",
    "panel":     "#1A1D2E",
    "border":    "#2E3250",
    "claude":    "#7C3AED",   # violet
    "claude_lt": "#A78BFA",
    "meta":      "#2563EB",   # blue
    "meta_lt":   "#93C5FD",
    "parser":    "#0891B2",   # cyan
    "parser_lt": "#67E8F9",
    "gen":       "#059669",   # emerald
    "gen_lt":    "#6EE7B7",
    "registry":  "#D97706",   # amber
    "registry_lt":"#FCD34D",
    "dyn":       "#DB2777",   # pink
    "dyn_lt":    "#F9A8D4",
    "exec":      "#DC2626",   # red
    "exec_lt":   "#FCA5A5",
    "api":       "#475569",   # slate
    "api_lt":    "#94A3B8",
    "arrow":     "#64748B",
    "white":     "#F8FAFC",
    "muted":     "#94A3B8",
}

def box(ax, x, y, w, h, color, label, sublabel=None, radius=0.25, alpha=0.15):
    """Draw a rounded rectangle with a fill, border, and text."""
    bg = FancyBboxPatch((x, y), w, h,
                        boxstyle=f"round,pad=0,rounding_size={radius}",
                        linewidth=1.8, edgecolor=color,
                        facecolor=color, alpha=alpha)
    ax.add_patch(bg)
    border = FancyBboxPatch((x, y), w, h,
                            boxstyle=f"round,pad=0,rounding_size={radius}",
                            linewidth=1.8, edgecolor=color,
                            facecolor="none")
    ax.add_patch(border)
    cy = y + h / 2 + (0.15 if sublabel else 0)
    ax.text(x + w / 2, cy, label,
            ha="center", va="center", fontsize=10, fontweight="bold", color=color)
    if sublabel:
        ax.text(x + w / 2, y + h / 2 - 0.25, sublabel,
                ha="center", va="center", fontsize=7.5, color=C["muted"])

def arrow(ax, x0, y0, x1, y1, color=C["arrow"], label=None, curved=False):
    style = "arc3,rad=0.2" if curved else "arc3,rad=0.0"
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=1.6, connectionstyle=style,
                                mutation_scale=14))
    if label:
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        ax.text(mx + 0.08, my + 0.12, label,
                fontsize=7, color=color, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.2", fc=C["bg"], ec="none", alpha=0.85))

# ── Title ───────────────────────────────────────────────────────────
ax.text(9, 9.5, "mcp-autodiscovery — Architecture",
        ha="center", va="center", fontsize=16, fontweight="bold",
        color=C["white"])
ax.text(9, 9.1, "Dynamically register any OpenAPI spec as live MCP tools at runtime",
        ha="center", va="center", fontsize=9.5, color=C["muted"])

# ── MCP Server outer panel ──────────────────────────────────────────
server_panel = FancyBboxPatch((3.6, 0.5), 9.8, 7.8,
                              boxstyle="round,pad=0,rounding_size=0.35",
                              linewidth=2, edgecolor=C["border"],
                              facecolor=C["panel"])
ax.add_patch(server_panel)
ax.text(8.5, 8.15, "mcp-autodiscovery  (MCP Server)",
        ha="center", va="center", fontsize=9, color=C["muted"],
        fontweight="bold")

# ── Claude Desktop (left) ──────────────────────────────────────────
box(ax, 0.3, 5.5, 2.8, 1.5, C["claude"], "Claude Desktop",
    "User / AI Agent")
box(ax, 0.3, 3.2, 2.8, 1.5, C["claude"], "list_tools()",
    "called by framework")
box(ax, 0.3, 0.9, 2.8, 1.5, C["claude"], "call_tool(name, args)",
    "dynamic tool invoked")

# ── Meta Tools ──────────────────────────────────────────────────────
box(ax, 3.9, 6.3, 3.6, 1.4, C["meta"], "Meta Tools  (always present)",
    "discover_api · list_discovered_apis · forget_api")

# ── Parser ──────────────────────────────────────────────────────────
box(ax, 3.9, 4.5, 1.55, 1.4, C["parser"], "Parser",
    "URL / JSON / YAML\n$ref resolution")

# ── Generator ───────────────────────────────────────────────────────
box(ax, 5.8, 4.5, 1.65, 1.4, C["gen"], "Generator",
    "OpenAPI ops\n→ Tool + config")

# ── Registry ────────────────────────────────────────────────────────
box(ax, 7.8, 4.5, 1.7, 1.4, C["registry"], "Registry",
    "thread-safe\nin-memory store")

# ── Dynamic Tools ───────────────────────────────────────────────────
box(ax, 9.85, 4.5, 3.3, 1.4, C["dyn"], "Dynamic Tools",
    "weather__get_forecast\npets__listPets  ·  stripe__charge ...")

# ── Executor ────────────────────────────────────────────────────────
box(ax, 3.9, 2.2, 5.5, 1.4, C["exec"], "HTTP Executor",
    "path · query · header · body params  →  real HTTP request")

# ── External APIs (right) ──────────────────────────────────────────
box(ax, 14.2, 6.0, 3.4, 1.4, C["api"], "Any OpenAPI Spec",
    "URL or raw JSON/YAML")
box(ax, 14.2, 3.8, 3.4, 1.4, C["api"], "External API",
    "Stripe · GitHub · OpenMeteo\nPetstore · or any REST API")

# ── Arrows — discover flow ──────────────────────────────────────────
# Claude → Meta Tools
arrow(ax, 3.1, 6.25, 3.9, 6.85, C["claude_lt"], "discover_api(url, name)")
# Meta Tools → Parser
arrow(ax, 5.5, 6.3, 5.5, 5.9,  C["meta_lt"])
# Spec URL → Parser
arrow(ax, 14.2, 6.7, 7.1, 5.55, C["api_lt"], "fetch spec", curved=True)
# Parser → Generator
arrow(ax, 5.45, 5.2, 5.8, 5.2, C["parser_lt"])
# Generator → Registry
arrow(ax, 7.45, 5.2, 7.8, 5.2, C["gen_lt"])
# Registry → Dynamic Tools
arrow(ax, 9.5, 5.2, 9.85, 5.2, C["registry_lt"], "register")

# ── Arrows — list_tools flow ───────────────────────────────────────
arrow(ax, 3.1, 3.95, 9.85, 5.05, C["claude_lt"], "list_tools()", curved=True)

# ── Arrows — call_tool flow ────────────────────────────────────────
# Claude → Dynamic Tools
arrow(ax, 3.1, 1.25, 9.85, 4.65, C["dyn_lt"], "call_tool(name, args)", curved=True)
# Dynamic Tools → Executor
arrow(ax, 11.5, 4.5, 7.5, 3.6,  C["dyn_lt"])
# Executor → External API
arrow(ax, 9.4, 2.9, 14.2, 4.5,  C["exec_lt"], "HTTP GET/POST...", curved=True)
# External API → Executor (return)
arrow(ax, 14.2, 4.1, 9.4, 2.65, C["api_lt"], "JSON response", curved=True)
# Executor → Claude (result)
arrow(ax, 3.9, 2.9, 3.1, 1.55, C["exec_lt"], "result")

# ── Step labels ─────────────────────────────────────────────────────
steps = [
    (1.45, 7.35,  "1  discover_api",   C["claude_lt"]),
    (1.45, 4.95,  "2  list_tools",     C["claude_lt"]),
    (1.45, 2.65,  "3  call_tool",      C["claude_lt"]),
]
for sx, sy, stxt, sc in steps:
    ax.text(sx, sy, stxt, ha="center", va="center", fontsize=8,
            color=sc, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", fc=C["bg"], ec=sc, lw=1.2))

# ── Legend ──────────────────────────────────────────────────────────
legend_items = [
    (C["claude"],   "Claude Desktop / User"),
    (C["meta"],     "Meta Tools (permanent)"),
    (C["parser"],   "Parser"),
    (C["gen"],      "Generator"),
    (C["registry"], "Registry"),
    (C["dyn"],      "Dynamic Tools"),
    (C["exec"],     "HTTP Executor"),
    (C["api"],      "External / Spec"),
]
lx, ly = 0.3, 0.65
ax.text(lx, ly, "Legend:", fontsize=7.5, color=C["muted"], fontweight="bold")
for i, (color, label) in enumerate(legend_items):
    ix = lx + (i % 4) * 2.9 + (0 if i < 4 else 0)
    iy = ly - 0.4 - (i // 4) * 0.4
    ax.add_patch(mpatches.Rectangle((ix - 0.02, iy - 0.12), 0.22, 0.22,
                                    color=color, alpha=0.85))
    ax.text(ix + 0.28, iy, label, fontsize=7, color=C["muted"], va="center")

# ── Save ────────────────────────────────────────────────────────────
out = Path(__file__).parent / "assets" / "architecture.png"
out.parent.mkdir(exist_ok=True)
plt.tight_layout(pad=0)
plt.savefig(out, dpi=160, bbox_inches="tight", facecolor=C["bg"])
plt.close()
print(f"Saved: {out}")
