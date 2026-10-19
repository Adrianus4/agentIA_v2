"""
Pytest configuration for AgentIA v2 Stream C.
"""

from contracts.models import TestBaseline

# Prevent pytest from attempting to collect the contract model TestBaseline as a test class
TestBaseline.__test__ = False  # type: ignore[attr-defined]
