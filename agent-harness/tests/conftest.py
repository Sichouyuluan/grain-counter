"""Pytest configuration — ensure project root is on sys.path."""
import sys
import os

# From tests/ -> agent-harness/ -> project/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
