from __future__ import annotations

from pathlib import Path


def design_meta_dir(repo_b_path: str | Path) -> Path:
    repo_root = Path(repo_b_path).resolve()
    return repo_root.parent / ".meta" / repo_root.name / "design_consultation"


def design_contract_path(repo_b_path: str | Path) -> Path:
    return Path(repo_b_path).resolve() / "DESIGN.md"


def design_preview_path(repo_b_path: str | Path) -> Path:
    return design_meta_dir(repo_b_path) / "design_preview.html"


def design_report_path(repo_b_path: str | Path) -> Path:
    return design_meta_dir(repo_b_path) / "design_consultation_report.md"


def design_preview_notes_path(repo_b_path: str | Path) -> Path:
    return design_meta_dir(repo_b_path) / "preview_notes.json"


def relpath(repo_b_path: str | Path, target_path: str | Path) -> str:
    repo_root = Path(repo_b_path).resolve()
    target = Path(target_path).resolve()
    try:
        return target.relative_to(repo_root).as_posix()
    except ValueError:
        return target.as_posix()


def read_if_exists(path: str | Path) -> str:
    candidate = Path(path)
    if not candidate.exists():
        return ""
    return candidate.read_text(encoding="utf-8")
