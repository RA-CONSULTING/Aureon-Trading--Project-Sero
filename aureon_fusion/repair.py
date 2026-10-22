"""Plug-and-play entry to Aureon's self-repair.

    python -m aureon_fusion.repair --root /path/to/project

The project needs pytest tests. The repair edits implementation files, reruns
the tests, and commits on a local branch named aureon-self-repair/<timestamp>.
Live trading stays off. Set AUREON_SELF_REPAIR_KILL=1 to stop it.
"""

from __future__ import annotations

import sys
from pathlib import Path

_UPSTREAM = Path(__file__).resolve().parents[1] / "aureon-os-upstream"
if str(_UPSTREAM) not in sys.path:
    sys.path.insert(0, str(_UPSTREAM))

from aureon.autonomous.aureon_sandbox_self_repair import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
