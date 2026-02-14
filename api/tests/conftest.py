from __future__ import annotations

import sys
from pathlib import Path


def _ensure_api_on_sys_path() -> None:
    # Tests import `app.*` where `app/` lives under `api/`.
    # Make `api/` importable regardless of the current working directory.
    api_dir = Path(__file__).resolve().parents[1]
    api_dir_str = str(api_dir)
    if api_dir_str not in sys.path:
        sys.path.insert(0, api_dir_str)


_ensure_api_on_sys_path()

