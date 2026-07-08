"""狀態/機密目錄解析（state dir）與 chmod-600 寫檔。

裝好的 CLI 沒有原本 repo 的 ``.secrets/``，所以 state dir 用以下優先序解析：

1. 明確傳入的 ``override``（例如 ``--out`` 的父目錄，或程式呼叫）。
2. 環境變數 ``MIHOME_CTL_HOME``。
3. 從 cwd 往上找最近的 ``./.secrets``（讓它在 SmartHome 之類的 repo 內當
   submodule 跑時，仍寫回同一個 ``.secrets``，沿用既有快取 session）。
4. 退回 platformdirs 的 user state dir（獨立安裝時）。

機密檔名沿用舊工具（``mi-tokens.json`` 等），以相容既有的 ``.secrets/``。
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
    """所有機密/快取檔的根目錄。"""

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
        return cls(Path(platformdirs.user_state_dir(APP_NAME)))

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


def write_secret(path: str | os.PathLike[str], data: str) -> None:
    """以 0600 權限原子寫入（覆蓋）。父目錄自動建立。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(data)
