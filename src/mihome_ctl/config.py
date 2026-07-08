"""State/secrets directory resolution (state dir) and chmod-600 file writes.

An installed CLI has no ``.secrets/`` from the original repo, so the state dir is
resolved in the following priority order:

1. An explicit ``override`` (e.g. the parent dir of ``--out``, or a programmatic
   call).
2. The ``MIHOME_CTL_HOME`` environment variable.
3. The nearest ``./.secrets`` found by walking up from the cwd (so that when run
   as a submodule inside a repo like SmartHome, it still writes back to the same
   ``.secrets`` and reuses the existing cached session).
4. Fall back to the user state dir (for a standalone install): honor
   ``XDG_STATE_HOME`` on every platform (incl. macOS), otherwise the platformdirs
   default. If ``XDG_STATE_HOME`` points at a not-yet-created dir but a legacy
   platformdirs dir already has data, keep the legacy one so nothing is orphaned.

Secret filenames follow the old tooling (``mi-tokens.json`` etc.) to stay
compatible with an existing ``.secrets/``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import platformdirs

APP_NAME = "mihome-ctl"
ENV_HOME = "MIHOME_CTL_HOME"


@dataclass(frozen=True)
class StateDir:
    """Root directory for all secret/cache files."""

    root: Path

    @classmethod
    def resolve(cls, override: str | os.PathLike[str] | None = None) -> StateDir:
        if override:
            return cls(Path(override).expanduser())
        env = os.environ.get(ENV_HOME)
        if env:
            return cls(Path(env).expanduser())
        cwd = Path.cwd()
        for parent in [cwd, *cwd.parents]:
            if (parent / ".secrets").is_dir():
                return cls(parent / ".secrets")
        # XDG-aware fallback: honor XDG_STATE_HOME even on macOS, but don't
        # orphan an existing legacy (~/Library/Application Support) cache.
        legacy = Path(platformdirs.user_state_dir(APP_NAME))
        xdg = os.environ.get("XDG_STATE_HOME")
        if xdg:
            cand = Path(xdg).expanduser() / APP_NAME
            return cls(legacy if (not cand.exists() and legacy.exists()) else cand)
        return cls(legacy)

    @property
    def tokens_json(self) -> Path:
        return self.root / "mi-tokens.json"

    @property
    def devices_md(self) -> Path:
        return self.root / "devices.md"

    @property
    def session_json(self) -> Path:
        return self.root / "mi-session.json"

    @property
    def ir_json(self) -> Path:
        return self.root / "mi-ir.json"

    def ir_code_json(self, matchid: str) -> Path:
        return self.root / f"ir-code-{matchid}.json"

    # --- MIoT-spec cache (public data, not secret) ---
    @property
    def spec_dir(self) -> Path:
        return self.root / "spec"

    @property
    def models_json(self) -> Path:
        return self.root / "miot-models.json"

    def spec_json(self, urn: str) -> Path:
        safe = urn.replace(":", "_").replace("/", "_")
        return self.spec_dir / f"{safe}.json"


def write_secret(path: str | os.PathLike[str], data: str) -> None:
    """Atomically write (overwriting) with 0600 permissions. The parent dir is created automatically."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(data)
