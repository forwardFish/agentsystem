from __future__ import annotations

from pathlib import Path

import chardet


TARGET_EXTENSIONS = {".md", ".yaml", ".yml", ".py", ".json"}


def fix_file_encoding(file_path: str | Path) -> bool:
    target = Path(file_path).resolve()
    raw = target.read_bytes()
    detected = chardet.detect(raw)
    encoding = detected.get("encoding") or "utf-8"
    if encoding.lower() in {"utf-8", "utf-8-sig"}:
        return False
    text = raw.decode(encoding)
    target.write_text(text, encoding="utf-8-sig")
    return True


def fix_tree_encoding(root: str | Path) -> list[Path]:
    root_path = Path(root).resolve()
    fixed: list[Path] = []
    for path in root_path.rglob("*"):
        if path.is_file() and path.suffix.lower() in TARGET_EXTENSIONS:
            try:
                if fix_file_encoding(path):
                    fixed.append(path)
            except Exception:
                continue
    return fixed
