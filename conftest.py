"""pytest configuration — adds the repo root to sys.path so `from engine import ...` works.

Place at the repo root (same level as `app.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo root = directory containing this file
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
