"""Zero-Key LLM dependency injection for AgentSpace gateway.

This module provides automatic LLM client extraction from the host context,
with graceful fallback to environment variables. This enables the SDK to
"borrow" the host Agent's LLM instance without requiring additional API keys.
"""

from __future__ import annotations

import os
from typing import Any, Optional


class LLMInjectionError(RuntimeError):
    """Raised when LLM injection fails completely."""

    def __init__(self, reason: str):
        super().__init__(
            f"Failed to obtain LLM client for DemandGenerator: {reason}\n"
            f"Please either:\n"
            f"  1. Pass an LLM client to your Agent's context (e.g., self.llm, agent.llm)\n"
            f"  2. Set OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable\n"
            f"  3. Provide llm_client parameter explicitly"
        )


def extract_llm_from_context(*args: Any, **kwargs: Any) -> Optional[Any]:
    """
    Extract an LLM client from function arguments.

    This function attempts to find an LLM client by inspecting common
    parameter naming patterns used across different Agent frameworks.

    Patterns checked (in order):
    - agent.llm, self.llm (first argument if it's an object with llm attribute)
    - Direct parameters: llm, model, client, llm_client
    - Provider-specific: anthropic, anthropic_client, openai, openai_client

    Args:
        *args: Positional arguments from the decorated function.
        **kwargs: Keyword arguments from the decorated function.

    Returns:
        The extracted LLM client, or None if not found.

    Examples:
        # Case 1: Agent with self.llm
        class MyAgent:
            def __init__(self):
                self.llm = Anthropic(...)

            @auto_catch_and_route
            def run(self):
                ...  # extract_llm_from_context will find self.llm

        # Case 2: Direct llm parameter
        @auto_catch_and_route
        def process(llm=None):
            ...  # extract_llm_from_context will find llm kwarg
    """
    # Check keyword arguments first (most common pattern)
    for key in ["llm", "model", "client", "llm_client", "anthropic_client", "openai_client"]:
        if key in kwargs and kwargs[key] is not None:
            return kwargs[key]

    # Check for provider-specific aliases
    for key in ["anthropic", "openai"]:
        if key in kwargs and kwargs[key] is not None:
            return kwargs[key]

    # Check first argument (usually self or agent)
    if args:
        first_arg = args[0]

        # Check if it's an object with llm attribute
        if hasattr(first_arg, "llm") and first_arg.llm is not None:
            return first_arg.llm

        # Check for common Agent attributes
        for attr in ["client", "model", "llm_client"]:
            if hasattr(first_arg, attr):
                value = getattr(first_arg, attr)
                if value is not None:
                    return value

    return None


def get_llm_with_fallback(*args: Any, **kwargs: Any) -> Any:
    """
    Get an LLM client with automatic fallback strategies.

    This implements the "Zero-Key Injection" pattern:
    1. Try to extract from context (agent.llm, parameters, etc.)
    2. Fall back to environment variables (OPENAI_API_KEY, ANTHROPIC_API_KEY)
    3. Raise helpful error if both fail

    Args:
        *args: Positional arguments from the decorated function.
        **kwargs: Keyword arguments from the decorated function.

    Returns:
        An LLM client instance (provider-specific).

    Raises:
        LLMInjectionError: If no LLM client can be obtained.
    """
    # Strategy 1: Extract from context
    llm = extract_llm_from_context(*args, **kwargs)
    if llm is not None:
        return llm

    # Strategy 2: Create from environment variables
    # Try Anthropic first (primary for AgentSpace)
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import anthropic

            return anthropic.Anthropic(api_key=anthropic_key)
        except ImportError:
            pass  # Fall through to OpenAI

    # Try OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            import openai

            return openai.OpenAI(api_key=openai_key)
        except ImportError:
            pass

    # Strategy 3: Raise helpful error
    raise LLMInjectionError(
        "No LLM client found in context and no API keys in environment"
    )


__all__ = ["extract_llm_from_context", "get_llm_with_fallback", "LLMInjectionError"]
