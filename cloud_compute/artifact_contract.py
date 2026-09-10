from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

PRIMARY_RESULT_KEYS = {"artifact", "output_dir"}


def declared_output_paths(result: dict[str, Any]) -> list[str]:
    """Return unique declared output files from a runner result.

    The runner contract historically used `artifact` for the primary output.
    Research jobs may also return named secondary files. `output_dir` is not an
    artifact; it is only a directory locator.
    """
    paths: list[str] = []
    seen: set[str] = set()
    for key, value in result.items():
        if key == "output_dir" or not isinstance(value, str) or not value.strip():
            continue
        if key == "sha256":
            continue
        rel = value.strip()
        if rel not in seen:
            paths.append(rel)
            seen.add(rel)
    return paths


def validate_declared_outputs(result: dict[str, Any], *, work_root: Path) -> list[Path]:
    root = work_root.resolve()
    validated: list[Path] = []
    for rel in declared_output_paths(result):
        path = (root / rel).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"artifact path escapes work root: {rel}") from exc
        if not path.is_file():
            raise RuntimeError(f"declared artifact does not exist: {rel}")
        validated.append(path)
    return validated


def completeness_summary(result: dict[str, Any], *, work_root: Path) -> dict[str, Any]:
    paths = validate_declared_outputs(result, work_root=work_root)
    primary = result.get("artifact")
    return {
        "declared_file_count": len(paths),
        "declared_files": [str(path.relative_to(work_root.resolve())) for path in paths],
        "primary_declared": bool(primary),
        "primary_in_declared_files": bool(primary and primary in declared_output_paths(result)),
    }
