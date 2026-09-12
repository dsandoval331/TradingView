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
    # Secondary research outputs are legacy named result fields whose values are
    # file paths (for example summary.json or robustness.csv). Plain metadata
    # strings such as fixture identifiers are not artifacts.
    return bool(Path(candidate).suffix)


def declared_output_paths(result: dict[str, Any]) -> list[str]:
    """Return unique declared output files from a runner result.

    Backward compatibility:
    - `artifact` is always the primary output path.
    - legacy named secondary outputs are accepted when their string values look
      like file paths (have a filename suffix).
    - plain string metadata is ignored.
    """
    paths: list[str] = []
    seen: set[str] = set()
    for key, value in result.items():
        if not isinstance(value, str) or not _looks_like_artifact_path(key, value):
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
