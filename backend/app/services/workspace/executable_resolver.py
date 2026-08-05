"""Resolve application executable paths without shelling out.

Resolution order:
1. An explicitly configured absolute path (if it exists).
2. Absolute candidate paths that exist.
3. Candidates resolvable via PATH (``shutil.which``).
4. Candidates found under common Windows install roots
   (LOCALAPPDATA, PROGRAMFILES, PROGRAMFILES(X86), PROGRAMW6432).

Every dependency (env vars, ``which`` implementation, search roots) is
injectable so tests never touch the real filesystem or PATH.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

WhichFn = Callable[[str], str | None]

_ROOT_ENV_KEYS = ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432")


class ExecutableResolver:
    def __init__(
        self,
        *,
        env: dict[str, str] | None = None,
        search_roots: list[Path] | None = None,
        which: WhichFn | None = None,
        path_exists: Callable[[Path], bool] | None = None,
    ) -> None:
        self._env = env if env is not None else dict(os.environ)
        self._which = which or shutil.which
        self._exists = path_exists or (lambda p: p.is_file())
        self._search_roots = (
            search_roots if search_roots is not None else self._default_roots()
        )

    def _default_roots(self) -> list[Path]:
        roots: list[Path] = []
        for key in _ROOT_ENV_KEYS:
            value = self._env.get(key)
            if value:
                roots.append(Path(value))
        return roots

    def resolve(
        self,
        *,
        configured_path: str = "",
        candidates: list[str] | None = None,
    ) -> Path | None:
        candidates = candidates or []

        if configured_path:
            configured = Path(configured_path)
            if self._exists(configured):
                return configured
            logger.warning("Configured executable path not found: %s", configured_path)

        for candidate in candidates:
            candidate_path = Path(candidate)
            if candidate_path.is_absolute() and self._exists(candidate_path):
                return candidate_path

        for candidate in candidates:
            found = self._which(candidate)
            if found:
                return Path(found)

        for candidate in candidates:
            name = Path(candidate).name
            for root in self._search_roots:
                for sub in self._candidate_subpaths(root, name):
                    if self._exists(sub):
                        return sub

        return None

    @staticmethod
    def _candidate_subpaths(root: Path, name: str) -> list[Path]:
        return [
            root / name,
            root / "Programs" / name,
            root / "Microsoft" / "WindowsApps" / name,
        ]
