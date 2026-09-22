from __future__ import annotations

from pathlib import Path
from typing import Any


def _looks_like_artifact_path(key: str, value: str) -> bool:
    if key == "artifact":
        return True
    if key in {"output_dir", "sha256"}:
        return False
    candidate = value.strip()
    if not candidate:
        return False
    return bool(Path(candidate).suffix)


def _append_unique(paths: list[str], seen: set[str], value: str) -> None:
    rel = value.strip()
    if rel and rel not in seen:
        paths.append(rel)
        seen.add(rel)


def declared_output_paths(result: dict[str, Any]) -> list[str]:
    """Return unique declared output files from a runner result.

    Supported contracts:
    - `artifact`: legacy primary output path.
    - `output_paths`: explicit list of output paths; first item is the default
      primary when `artifact` is absent.
    - legacy named secondary string fields whose values look like file paths.
    Plain string metadata is ignored.
    """
    paths: list[str] = []
    seen: set[str] = set()

    primary = result.get("artifact")
    if isinstance(primary, str) and primary.strip():
        _append_unique(paths, seen, primary)

    output_paths = result.get("output_paths")
    if isinstance(output_paths, list):
        for value in output_paths:
            if isinstance(value, str) and value.strip():
                _append_unique(paths, seen, value)

    for key, value in result.items():
        if key in {"artifact", "output_paths"}:
            continue
        if not isinstance(value, str) or not _looks_like_artifact_path(key, value):
            continue
        _append_unique(paths, seen, value)
    return paths


def primary_output_path(result: dict[str, Any]) -> str | None:
    primary = result.get("artifact")
    if isinstance(primary, str) and primary.strip():
        return primary.strip()
    output_paths = result.get("output_paths")
    if isinstance(output_paths, list):
        for value in output_paths:
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


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
    primary = primary_output_path(result)
    declared = declared_output_paths(result)
    return {
        "declared_file_count": len(paths),
        "declared_files": [str(path.relative_to(work_root.resolve())) for path in paths],
        "primary_declared": bool(primary),
        "primary_in_declared_files": bool(primary and primary in declared),
    }
