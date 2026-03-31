"""Skill decorator for marking functions as discoverable abilities.

This decorator provides a semantic marker for AST-based skill discovery.
Functions decorated with @skill can be automatically discovered and registered
by the DiscoveryRadar without requiring manual configuration.
"""

from functools import wraps
from typing import Any, Callable, Optional, ParamSpec


P = ParamSpec("P")


def skill(description: str = "", **metadata: Any) -> Callable[..., Any]:
    """
    Mark a function as a discoverable skill for ClawHub.

    The decorator adds metadata that can be extracted by AST-based scanners.
    It does NOT register the function at runtime - registration happens
    via importlib dynamic loading based on config.yaml snapshots.

    Args:
        description: Human-readable description of what this skill does.
        **metadata: Additional metadata (category, version, etc.).

    Example:
        @skill(description="Multiply two numbers")
        def multiply(a: int, b: int) -> int:
            return a * b

        @skill(description="Process CSV data", category="data")
        def process_csv(file_path: str) -> dict:
            ...
    """
    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        # Add metadata as function attributes for runtime access
        func._agentspace_skill = True
        func._skill_description = description
        func._skill_metadata = metadata

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            return func(*args, **kwargs)

        # Copy metadata to wrapper for AST discovery
        wrapper._agentspace_skill = True
        wrapper._skill_description = description
        wrapper._skill_metadata = metadata
        wrapper.__wrapped__ = func  # Keep reference to original

        return wrapper

    return decorator


__all__ = ["skill"]
