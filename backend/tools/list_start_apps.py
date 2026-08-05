#!/usr/bin/env python3
"""List discovered Windows Start Apps (fixed PowerShell discovery)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.workspace.start_app_resolver import StartAppResolver


def main() -> int:
    parser = argparse.ArgumentParser(description="List Windows Start Apps.")
    parser.add_argument("--filter", default="", help="Case-insensitive name filter")
    parser.add_argument("--refresh", action="store_true", help="Bypass cache")
    args = parser.parse_args()

    resolver = StartAppResolver()
    apps = resolver.list_apps(force_refresh=args.refresh)
    needle = args.filter.strip().lower()
    if needle:
        apps = [a for a in apps if needle in a.name.lower() or needle in a.app_id.lower()]

    if not apps:
        print("No Start Apps found (or discovery unavailable).")
        return 0

    print(f"Found {len(apps)} Start App(s):")
    for app in apps:
        print(f"  {app.name}  [{app.app_id}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
