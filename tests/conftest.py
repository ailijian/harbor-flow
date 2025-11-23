import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from langgraph.graph import StateGraph  # noqa: F401
except Exception:
    pytest.skip("langgraph not installed; skipping tests", allow_module_level=True)