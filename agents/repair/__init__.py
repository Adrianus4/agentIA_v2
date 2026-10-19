"""
DM-3 Scoped Repair module (The Surgeon) and Patch Guards.
"""

from agents.repair.guards import evaluate_guards, extract_touched_files
from agents.repair.prompt import build_repair_prompt
from agents.repair.service import ScopedRepairService

__all__ = [
    "ScopedRepairService",
    "build_repair_prompt",
    "evaluate_guards",
    "extract_touched_files",
]
