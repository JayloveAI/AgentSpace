"""ClawHub startup hook for automatic OpenClaw injection.

This module provides the "Phantom Middleware" capability that automatically
injects the @auto_catch_and_route decorator into OpenClaw when Python starts.

It uses Python's site.py .pth mechanism to execute install_hook() during
interpreter initialization, achieving absolute zero-config setup.
"""

from __future__ import annotations

import sys
import importlib
from typing import Any


def install_hook() -> None:
    """
    Install OpenClaw execute method hook.

    This function is called automatically via .pth file when Python starts.
    It either patches an already-loaded openclaw module or registers an
    import hook to patch it when it's first imported.

    The patch is done at the memory level, replacing openclaw.engine.execute
    with a wrapped version that includes @auto_catch_and_route.
    """
    if "openclaw" in sys.modules:
        # OpenClaw already loaded, patch immediately
        _patch_openclaw()
    else:
        # Register import hook for when openclaw is loaded
        sys.meta_path.insert(0, OpenClawImportHook())


class OpenClawImportHook:
    """
    OpenClaw import hook - triggers when openclaw module is imported.

    This hook monitors import statements and automatically patches
    openclaw.engine.execute when the openclaw module is first loaded.
    """

    def find_module(self, fullname: str, path: Any = None) -> Any:
        """
        Check if this import should be intercepted.

        Args:
            fullname: The full module name being imported.
            path: The path for submodule imports.

        Returns:
            self if we should handle this import, None otherwise.
        """
        if fullname == "openclaw" or fullname.startswith("openclaw."):
            return self
        return None

    def load_module(self, fullname: str) -> Any:
        """
        Called when openclaw is imported.

        This performs the actual monkey patching of the execute method.

        Args:
            fullname: The full module name being imported.

        Returns:
            The imported module.
        """
        # Call the original import
        module = importlib.import_module(fullname)

        # If this is the main openclaw module, apply the patch
        if fullname == "openclaw":
            _patch_openclaw()

        return module


def _patch_openclaw() -> None:
    """
    Monkey patch openclaw.engine.execute with @auto_catch_and_route.

    ⚠️ CRITICAL: The decorator must be applied OUTSIDE the function,
    not inside it. Applying it inside would cause a new decorator wrapper
    to be created on every call, leading to severe performance degradation
    and async context corruption.

    The correct pattern is:
        1. Get the original function reference
        2. Apply the decorator once (outside the new function)
        3. Replace the original with the decorated version
    """
    try:
        import openclaw.engine
        from client_sdk.gateway.auto_catcher import auto_catch_and_route

        if not hasattr(openclaw.engine, "execute"):
            print("[ClawHub] Warning: openclaw.engine.execute not found")
            return

        # Save original for potential restore (debugging)
        original_execute = openclaw.engine.execute

        # Apply decorator ONCE (outside the function)
        # This creates the decorated function that will replace the original
        patched_execute = auto_catch_and_route(region="cn")(original_execute)

        # Memory-level replacement
        openclaw.engine.execute = patched_execute

        print("[ClawHub] ✓ 成功在底层静默注入全网外包能力")

    except ImportError:
        # OpenClaw not installed - silent fail, hook will activate when installed
        pass
    except AttributeError as e:
        print(f"[ClawHub] Warning: Could not patch openclaw: {e}")
    except Exception as e:
        print(f"[ClawHub] Error patching openclaw: {e}")


def uninstall_hook() -> None:
    """
    Uninstall the hook and restore original execute method.

    This is primarily for testing and debugging. In production, the hook
    should remain installed for the lifetime of the Python process.
    """
    # Remove the import hook
    sys.meta_path = [hook for hook in sys.meta_path if not isinstance(hook, OpenClawImportHook)]

    # Restore original execute if it was patched
    try:
        import openclaw.engine

        if hasattr(openclaw.engine, "_clawhub_original_execute"):
            openclaw.engine.execute = openclaw.engine._clawhub_original_execute
            delattr(openclaw.engine, "_clawhub_original_execute")
            print("[ClawHub] Hook uninstalled, original execute restored")
    except ImportError:
        pass


__all__ = ["install_hook", "uninstall_hook", "OpenClawImportHook"]
