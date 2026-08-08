#!/usr/bin/env python3
"""Generate SOURCE_CODE.md by crawling all project source files."""
import pathlib
import os

ROOT = pathlib.Path(__file__).parent
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache",
    ".mimocode", ".benchmarks", ".ruff_cache", ".mypy_cache", "dist", "build",
    ".next", "egg-info", ".vite", "htmlcov", ".hypothesis", "assets",
    ".DS_Store",
}
SKIP_FILES = {
    "package-lock.json", "bun.lock", "generate_source_code.py",
    "SOURCE_CODE.md",
}
SKIP_EXTS = {".pyc", ".pyo", ".so", ".o", ".min.js", ".map", ".db", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".pdf", ".zip", ".tar", ".gz", ".DS_Store"}

def should_skip(path: pathlib.Path) -> bool:
    parts = path.relative_to(ROOT).parts
    if any(p in SKIP_DIRS for p in parts):
        return True
    if path.name in SKIP_FILES:
        return True
    if path.suffix in SKIP_EXTS:
        return True
    return False

def build_tree(root: pathlib.Path, prefix: str = "", skip_dirs: set = None) -> list:
    """Build a directory tree representation."""
    if skip_dirs is None:
        skip_dirs = SKIP_DIRS
    entries = []
    try:
        items = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except (PermissionError, OSError):
        return entries

    for item in items:
        if item.name in skip_dirs:
            continue
        if item.is_dir():
            entries.append(f"{prefix}{item.name}/")
            entries.extend(build_tree(item, prefix + "│   ", skip_dirs))
        else:
            if item.suffix in SKIP_EXTS:
                continue
            entries.append(f"{prefix}{item.name}")
    return entries

def main():
    files = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and not should_skip(p):
            try:
                if p.stat().st_size > 1_000_000:  # skip files >1MB
                    continue
                content = p.read_text(encoding="utf-8", errors="ignore")
                rel = str(p.relative_to(ROOT))
                files.append((rel, content))
            except Exception:
                pass

    lines = []
    lines.append("# SOURCE_CODE.md — Complete Source Code Dump")
    lines.append("# Auto-generated from repository at HEAD")
    lines.append(f"# Total files: {len(files)}")
    lines.append("#" + "=" * 78)
    lines.append("")

    # Directory hierarchy
    lines.append("## Directory Hierarchy")
    lines.append("")
    lines.append("```")
    tree_lines = build_tree(ROOT)
    lines.extend(tree_lines)
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    for rel, content in files:
        lines.append(f"=== FILE: ./{rel} ===")
        lines.append(content.rstrip())
        lines.append(f"=== END FILE: ./{rel} ===")
        lines.append("")

    out = ROOT / "SOURCE_CODE.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Written {len(files)} files to SOURCE_CODE.md ({out.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
