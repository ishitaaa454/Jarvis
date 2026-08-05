#!/usr/bin/env python3
"""List top-level windows for debugging (titles off by default)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workspace.window_manager import WindowManager, try_create_default_api


def main() -> int:
    parser = argparse.ArgumentParser(description="List visible top-level windows.")
    parser.add_argument(
        "--include-titles",
        action="store_true",
        help="Include window titles (may be sensitive).",
    )
    args = parser.parse_args()

    api = try_create_default_api()
    if api is None:
        print("Window control unavailable (pywin32 missing or import failed).")
        return 1

    wm = WindowManager(api=api, debug_titles=args.include_titles)
    try:
        handles = api.enum_windows()
    except Exception as exc:
        print(f"Window enumeration failed: {exc}")
        return 1

    rows: list[tuple[int, int, str, bool, bool]] = []
    for hwnd in handles:
        try:
            if not api.is_window_visible(hwnd):
                continue
            title = api.get_window_text(hwnd)
            if not title:
                continue
            pid = api.get_pid_for_window(hwnd)
            if pid <= 0:
                continue
            minimized = api.is_iconic(hwnd)
            rows.append((hwnd, pid, title if args.include_titles else "", True, minimized))
        except Exception:
            continue

    # Touch WindowManager so production path is exercised when titles requested
    if args.include_titles and rows:
        pids = sorted({pid for _, pid, *_ in rows})
        _ = wm.find_windows_for_pids(pids)

    if not rows:
        print("No visible titled windows found.")
        return 0

    print(f"Found {len(rows)} window(s):")
    for hwnd, pid, title, visible, minimized in rows:
        proc_name = "unknown"
        try:
            import psutil

            proc_name = psutil.Process(pid).name()
        except Exception:
            pass
        title_part = f"  title={title!r}" if args.include_titles and title else ""
        print(
            f"  hwnd={hwnd}  pid={pid}  process={proc_name}  "
            f"visible={visible}  minimized={minimized}{title_part}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
