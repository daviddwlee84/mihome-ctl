"""``setup`` — one-step onboarding: install the ``mihome-ir`` agent skill and register
the MCP server for Claude, or ``--uninstall`` to remove them again.

Self-contained by default (copies the skill bundled in the wheel — no Node needed);
``--npx`` delegates skill install to the vercel-labs ``skills`` CLI instead. Prompts
for confirmation (listing exactly what it will do) unless ``--yes``/``-y``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import tyro

REPO = "daviddwlee84/mihome-ctl"
SKILL_NAME = "mihome-ir"
MCP_NAME = "mihome-ctl"

Yes = Annotated[bool, tyro.conf.arg(aliases=["-y"])]


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


def _confirm(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def setup(
    project: bool = False,
    npx: bool = False,
    skill_only: bool = False,
    mcp_only: bool = False,
    uninstall: bool = False,
    yes: Yes = False,
    dry_run: bool = False,
) -> int:
    """Install (or --uninstall) the mihome-ir agent skill + MCP server for Claude."""
    if uninstall:
        return _uninstall(project, skill_only, mcp_only, yes, dry_run)
    return _install(project, npx, skill_only, mcp_only, yes, dry_run)


def _install(project, npx, skill_only, mcp_only, yes, dry_run) -> int:
    scope = "project (./.claude)" if project else "user (~/.claude)"
    dest = _skills_dir(project) / SKILL_NAME / "SKILL.md"
    plan = []
    if not mcp_only:
        how = f"via `npx skills add {REPO}`" if npx else f"-> {dest}"
        plan.append(f"install '{SKILL_NAME}' agent skill {how}  [{scope}]")
    if not skill_only:
        plan.append(f"register MCP server '{MCP_NAME}' (mihome-ctl-mcp) with Claude")

    print("[mihome-ctl] setup will:")
    for p in plan:
        print(f"  - {p}")
    if dry_run:
        print("[mihome-ctl] (dry-run - nothing written)")
        return 0
    if not yes and not _confirm("Proceed?"):
        print("[mihome-ctl] aborted.")
        return 1

    if not mcp_only:
        if npx:
            cmd = ["npx", "-y", "skills", "add", REPO, "--skill", SKILL_NAME, "-a", "claude-code"]
            if not project:
                cmd.append("-g")
            subprocess.run(cmd, check=False)
        else:
            text = _bundled_skill_text()
            if text is None:
                print(
                    f"[mihome-ctl] bundled SKILL.md not found; retry with --npx "
                    f"(npx skills add {REPO} --skill {SKILL_NAME})",
                    file=sys.stderr,
                )
                return 1
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            print(f"[mihome-ctl] OK installed skill -> {dest}")
    if not skill_only:
        _register_mcp(project)
    print("\n[mihome-ctl] done - restart Claude to pick up the skill + MCP server.")
    return 0


def _register_mcp(project: bool) -> None:
    claude = shutil.which("claude")
    if claude:
        args = [claude, "mcp", "add", MCP_NAME]
        if not project:
            args += ["-s", "user"]
        args += ["--", "mihome-ctl-mcp"]
        r = subprocess.run(args, capture_output=True, text=True)
        if r.returncode == 0:
            print("[mihome-ctl] OK registered MCP server via `claude mcp add`")
            return
        print(f"[mihome-ctl] `claude mcp add` failed: {r.stderr.strip()}")
    cfg = {"mcpServers": {MCP_NAME: {"command": "mihome-ctl-mcp"}}}
    print("[mihome-ctl] register the MCP server with Claude - run:")
    print(f"    claude mcp add {MCP_NAME} -- mihome-ctl-mcp")
    print("  or add to claude_desktop_config.json:")
    print(json.dumps(cfg, indent=2))


def _uninstall(project, skill_only, mcp_only, yes, dry_run) -> int:
    skill_dir = _skills_dir(project) / SKILL_NAME
    plan = []
    if not mcp_only:
        plan.append(f"remove '{SKILL_NAME}' skill -> {skill_dir}")
    if not skill_only:
        plan.append(f"unregister MCP server '{MCP_NAME}' (`claude mcp remove`)")

    print("[mihome-ctl] uninstall will:")
    for p in plan:
        print(f"  - {p}")
    if dry_run:
        print("[mihome-ctl] (dry-run - nothing removed)")
        return 0
    if not yes and not _confirm("Remove these?"):
        print("[mihome-ctl] aborted.")
        return 1

    if not mcp_only:
        if skill_dir.exists():
            shutil.rmtree(skill_dir, ignore_errors=True)
            print(f"[mihome-ctl] OK removed {skill_dir}")
        else:
            print(f"[mihome-ctl] skill not found at {skill_dir}")
    if not skill_only:
        claude = shutil.which("claude")
        if claude:
            args = [claude, "mcp", "remove", MCP_NAME]
            if not project:
                args += ["-s", "user"]
            r = subprocess.run(args, capture_output=True, text=True)
            if r.returncode == 0:
                print("[mihome-ctl] OK unregistered MCP server")
            else:
                print(f"[mihome-ctl] `claude mcp remove` failed: {r.stderr.strip()}")
        else:
            print(f"[mihome-ctl] remove the MCP manually: claude mcp remove {MCP_NAME}")
    print("\n[mihome-ctl] done - restart Claude.")
    return 0
