"""DiscoveryRadar - Automatic skill discovery and config snapshot generation.

This module provides the "Discovery Radar" functionality that automatically
scans Python code for @skill decorated functions and generates config snapshots.
It uses pure AST analysis (ast.parse) for security - no eval/exec.

Security Guarantee:
    - Only uses ast.parse() for code analysis (lexing/parsing only)
    - NEVER uses eval() or exec() - code is never executed
    - Safe to run on untrusted codebases
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

import yaml

from .skill_scanner import scan_skills


class DiscoveryRadar:
    """
    Automatic skill discovery radar for zero-config setup.

    The radar scans Python files for @skill decorated functions and
    generates clawhub_config.yaml snapshots. This enables automatic
    skill registration without manual YAML editing.
    """

    # Default directories to ignore during scanning
    DEFAULT_IGNORE_DIRS = {
        "venv",
        ".venv",
        "env",
        ".env",
        "virtualenv",
        "__pycache__",
        ".git",
        ".tox",
        "build",
        "dist",
        "node_modules",
        ".idea",
        ".vscode",
        "migrations",
    }

    # Default file patterns to ignore
    DEFAULT_IGNORE_PATTERNS = {
        "test_",
        "_test.py",
        "conftest.py",
        "__init__.py",
    }

    def __init__(
        self,
        project_root: Path | str | None = None,
        config_path: Path | str | None = None,
        ignore_dirs: set[str] | None = None,
        ignore_patterns: set[str] | None = None,
    ):
        """
        Initialize the DiscoveryRadar.

        Args:
            project_root: Root directory to scan for skills. Defaults to cwd.
            config_path: Path to write clawhub_config.yaml. Defaults to ~/.clawhub/.
            ignore_dirs: Directories to skip during scanning.
            ignore_patterns: File patterns to skip.
        """
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.config_path = Path(config_path) if config_path else (Path.home() / ".clawhub" / "clawhub_config.yaml")
        self.ignore_dirs = ignore_dirs or self.DEFAULT_IGNORE_DIRS
        self.ignore_patterns = ignore_patterns or self.DEFAULT_IGNORE_PATTERNS

    def scan(self, recursive: bool = True) -> dict[str, Any]:
        """
        Scan the project for @skill decorated functions.

        This uses pure AST analysis (ast.parse) which is safe even for
        untrusted code - it only parses syntax without executing anything.

        Args:
            recursive: Whether to scan subdirectories recursively.

        Returns:
            A dictionary containing discovered skills and metadata.
        """
        if not self.project_root.exists():
            return {
                "local_skills": [],
                "scan_errors": [f"Project root does not exist: {self.project_root}"],
            }

        skills = []
        errors = []

        # Find all Python files to scan
        python_files = self._find_python_files(recursive)

        # Scan each file using AST (safe, no execution)
        for file_path in python_files:
            try:
                file_skills = self._scan_file_ast(file_path)
                skills.extend(file_skills)
            except SyntaxError as e:
                errors.append(f"Syntax error in {file_path}: {e}")
            except Exception as e:
                errors.append(f"Error scanning {file_path}: {e}")

        result = {
            "local_skills": skills,
            "scan_errors": errors,
            "project_root": str(self.project_root),
            "skills_count": len(skills),
        }

        return result

    def scan_and_save(self, recursive: bool = True) -> dict[str, Any]:
        """
        Scan for skills and save the config snapshot.

        Args:
            recursive: Whether to scan subdirectories recursively.

        Returns:
            The scan result dictionary.
        """
        result = self.scan(recursive)
        self._save_config(result)
        return result

    def _find_python_files(self, recursive: bool) -> list[Path]:
        """Find all Python files that should be scanned."""
        files = []

        if recursive:
            # rglob for recursive search
            for path in self.project_root.rglob("*.py"):
                if self._should_scan_file(path):
                    files.append(path)
        else:
            # glob for top-level only
            for path in self.project_root.glob("*.py"):
                if self._should_scan_file(path):
                    files.append(path)

        return files

    def _should_scan_file(self, file_path: Path) -> bool:
        """Check if a file should be scanned."""
        # Check if parent directory should be ignored
        for part in file_path.parts:
            if part in self.ignore_dirs:
                return False

        # Check file name patterns
        file_name = file_path.name
        for pattern in self.ignore_patterns:
            if pattern in file_name:
                return False

        # Skip hidden files
        if file_name.startswith("."):
            return False

        return True

    def _scan_file_ast(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Scan a Python file for @skill decorated functions using pure AST.

        SECURITY: This method ONLY uses ast.parse() which is safe.
        It does NOT use eval() or exec() - code is never executed.

        Args:
            file_path: Path to the Python file.

        Returns:
            List of discovered skill dictionaries.

        Raises:
            SyntaxError: If the file has invalid Python syntax.
        """
        # Read source code
        source = file_path.read_text(encoding="utf-8")

        # Parse using ast (safe - no execution)
        tree = ast.parse(source, filename=str(file_path))

        skills = []

        # Walk the AST looking for function definitions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check if function has @skill decorator
                if self._has_skill_decorator(node):
                    skill_info = self._extract_skill_info(node, file_path)
                    skills.append(skill_info)

        return skills

    def _has_skill_decorator(self, node: ast.FunctionDef) -> bool:
        """Check if a function has @skill decorator."""
        for decorator in node.decorator_list:
            # Check for @skill (plain name)
            if isinstance(decorator, ast.Name) and decorator.id == "skill":
                return True
            # Check for @skill() (call with args)
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name) and decorator.func.id == "skill":
                    return True
                # Check for clawhub.skill or module.skill
                if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "skill":
                    return True
        return False

    def _extract_skill_info(self, node: ast.FunctionDef, file_path: Path) -> dict[str, Any]:
        """Extract skill information from AST node."""
        # Get function name
        name = node.name

        # Get docstring as description
        description = ast.get_docstring(node) or ""

        # Extract @skill decorator arguments if present
        skill_args = self._extract_decorator_args(node)

        # Use decorator description if provided, otherwise use docstring
        final_description = skill_args.get("description", "") or description

        # Extract parameter information
        parameters = self._extract_parameters(node)

        # Make path relative to project root for cleaner config
        try:
            rel_path = file_path.relative_to(self.project_root)
        except ValueError:
            rel_path = file_path

        return {
            "name": name,
            "path": str(file_path),
            "relative_path": str(rel_path),
            "description": final_description,
            "parameters": parameters,
            "metadata": skill_args.get("metadata", {}),
        }

    def _extract_decorator_args(self, node: ast.FunctionDef) -> dict[str, Any]:
        """Extract arguments from @skill decorator."""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name) and decorator.func.id == "skill":
                    return self._parse_call_args(decorator)
                if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "skill":
                    return self._parse_call_args(decorator)
        return {}

    def _parse_call_args(self, node: ast.Call) -> dict[str, Any]:
        """Parse arguments from a decorator call like @skill(description="...")."""
        result = {}

        for keyword in node.keywords:
            if keyword.arg == "description":
                if isinstance(keyword.value, ast.Constant):
                    result["description"] = keyword.value.value
            elif keyword.arg == "metadata":
                # Skip complex metadata parsing for now
                result["metadata"] = {}

        return result

    def _extract_parameters(self, node: ast.FunctionDef) -> list[dict[str, str]]:
        """Extract parameter names and types from function signature."""
        params = []

        for arg in node.args.args:
            param_info = {"name": arg.arg}

            # Get type annotation if present
            if arg.annotation:
                param_info["type"] = ast.unparse(arg.annotation)
            else:
                param_info["type"] = "Any"

            params.append(param_info)

        return params

    def _save_config(self, scan_result: dict[str, Any]) -> None:
        """Save the scan result as clawhub_config.yaml."""
        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Prepare config data
        config_data = {
            "local_skills": scan_result.get("local_skills", []),
            "project_root": scan_result.get("project_root", str(self.project_root)),
            "skills_count": scan_result.get("skills_count", 0),
        }

        # Add scan errors as comments if any
        errors = scan_result.get("scan_errors", [])
        if errors:
            config_data["_scan_errors"] = errors

        # Write YAML file
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    def load_config(self) -> dict[str, Any]:
        """Load the existing clawhub_config.yaml if it exists."""
        if not self.config_path.exists():
            return {}

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}


__all__ = ["DiscoveryRadar"]
