from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


def _is_skill_function(node: ast.FunctionDef) -> bool:
    if node.name.startswith("skill_"):
        return True
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "skill":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "skill":
            return True
    return False


def scan_skills(root: Path | str) -> list[dict]:
    """
    Scan Python files under root for skill-like functions.

    Returns a list of dicts with name, docstring, and file path.
    """
    root_path = Path(root)
    if not root_path.exists():
        return []

    results: list[dict] = []
    for path in root_path.rglob("*.py"):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception:
            continue

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and _is_skill_function(node):
                results.append({
                    "name": node.name,
                    "doc": ast.get_docstring(node) or "",
                    "path": str(path)
                })

    return results
