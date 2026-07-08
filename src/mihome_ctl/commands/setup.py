"""``setup`` — one-step onboarding: install the ``mihome-ir`` agent skill and
register the MCP server for Claude, so ``uv tool install mihome-ctl`` gets you
everything.

Self-contained by default (copies the skill bundled in the wheel — no Node
needed). ``--npx`` delegates skill install to the vercel-labs ``skills`` CLI
(``npx skills add ...``) instead.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

REPO = "daviddwlee84/mihome-ctl"
SKILL_NAME = "mihome-ir"


def _bundled_skill_text() -> str | None:
    # Shipped in the wheel via hatchling force-include: mihome_ctl/_skill/SKILL.md
    try:
        res = files("mihome_ctl") / "_skill" / "SKILL.md"
        if res.is_file():
            return res.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        pass
    # Dev fallback (editable install): repo-relative skills/mihome-ir/SKILL.md
    for up in Path(__file__).resolve().parents:
        cand = up / "skills" / SKILL_NAME / "SKILL.md"
        if cand.is_file():
            return cand.read_text(encoding="utf-8")
    return None


def _skills_dir(project: bool) -> Path:
    base = Path.cwd() if project else Path.home()
    return base / ".claude" / "skills"


def setup(
    project: bool = False,
    npx: bool = False,
    skill_only: bool = False,
    mcp_only: bool = False,
    dry_run: bool = False,
) -> int:
    """Install the mihome-ir agent skill + register the MCP server for Claude."""
    scope = "project (./.claude)" if project else "user (~/.claude)"

    if not mcp_only:
        if npx:
            cmd = ["npx", "-y", "skills", "add", REPO, "--skill", SKILL_NAME, "-a", "claude-code"]
            if not project:
                cmd.append("-g")
            print(f"[mihome-ctl] installing skill via: {' '.join(cmd)}")
            if not dry_run:
                subprocess.run(cmd, check=False)
        else:
            text = _bundled_skill_text()
            if text is None:
                print(
                    "[mihome-ctl] bundled SKILL.md not found; retry with --npx "
                    f"(npx skills add {REPO} --skill {SKILL_NAME})",
                    file=sys.stderr,
                )
                return 1
            dest = _skills_dir(project) / SKILL_NAME / "SKILL.md"
            print(f"[mihome-ctl] installing '{SKILL_NAME}' skill → {dest}  [{scope}]")
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text, encoding="utf-8")

    if not skill_only:
        claude = shutil.which("claude")
        registered = False
        if claude and not dry_run:
            args = [claude, "mcp", "add", "mihome-ctl"]
            if not project:
                args += ["-s", "user"]
            args += ["--", "mihome-ctl-mcp"]
            r = subprocess.run(args, capture_output=True, text=True)
            registered = r.returncode == 0
            if registered:
                print("[mihome-ctl] ✅ registered MCP server via `claude mcp add`")
            else:
                print(f"[mihome-ctl] ⚠️ `claude mcp add` failed: {r.stderr.strip()}")
        if not registered:
            cfg = {"mcpServers": {"mihome-ctl": {"command": "mihome-ctl-mcp"}}}
            print("[mihome-ctl] register the MCP server with Claude — either run:")
            print("    claude mcp add mihome-ctl -- mihome-ctl-mcp")
            print("  or add to claude_desktop_config.json:")
            print(json.dumps(cfg, indent=2))

    print("\n[mihome-ctl] done — restart Claude to pick up the skill + MCP server.")
    return 0
