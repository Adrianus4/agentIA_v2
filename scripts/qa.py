"""Lanzador absoluto para ejecutar qa_agent desde cualquier directorio externo sin instalar el repositorio (E02)."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_and_run() -> int:
    script_root = Path(__file__).resolve().parents[1]
    root_str = str(script_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    from qa_agent.cli import main

    return main()


if __name__ == "__main__":
    raise SystemExit(_bootstrap_and_run())
