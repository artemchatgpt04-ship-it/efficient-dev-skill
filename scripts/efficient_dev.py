#!/usr/bin/env python3
"""Run the shared Efficient Development core without installing a package."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.efficient_dev.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
