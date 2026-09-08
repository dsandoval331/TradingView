"""PMPD V5 research engine alpha.

This package is intentionally research-only. It models PM/AH/PD level-stack
encounters independently of the frozen V4 signal architecture.
"""

from .alpha import run_symbol_alpha

__all__ = ["run_symbol_alpha"]
