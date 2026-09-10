from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

IGNORED_FILES = {
    ".env",
    ".env.local",
    ".env.production",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}

TEXT_SUFFIXES = {
    ".py",
    ".sql",
    ".md",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".txt",
    ".sh",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".scala",
    ".kt",
    ".kts",
    ".dockerfile",
}

SPECIAL_TEXT_NAMES = {
    "Dockerfile",
    "Makefile",
    "Procfile",
    "requirements.txt",
    "requirements-dev.txt",
}

PRIORITY_NAMES = {
    "README.md": 0,
    "pyproject.toml": 1,
    "requirements.txt": 2,
    "package.json": 3,
    "docker-compose.yml": 4,
    "docker-compose.yaml": 4,
    "Dockerfile": 5,
}


@dataclass(frozen=True)
class RepositoryContext:
    root: Path
    text: str
    included_files: tuple[str, ...]
    truncated: bool
    mode: str


def _is_allowed(path: Path) -> bool:
    if path.name in IGNORED_FILES:
        return False
    if any(part in IGNORED_DIRS for part in path.parts):
        return False
    if path.name in SPECIAL_TEXT_NAMES:
        return True
    return path.suffix.lower() in TEXT_SUFFIXES


def _priority(path: Path) -> tuple[int, int, str]:
    return (
        PRIORITY_NAMES.get(path.name, 20),
        len(path.parts),
        path.as_posix().lower(),
    )


def _safe_read(path: Path, max_file_chars: int = 30_000) -> str | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    if "\x00" in raw:
        return None
    if len(raw) > max_file_chars:
        return raw[:max_file_chars] + "\n... [file truncated] ...\n"
    return raw


def build_repository_context(
    repo_path: str | Path,
    *,
    max_chars: int = 120_000,
    max_file_chars: int = 30_000,
) -> RepositoryContext:
    root = Path(repo_path).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {root}")

    candidates = sorted(
        (p for p in root.rglob("*") if p.is_file() and _is_allowed(p.relative_to(root))),
        key=lambda p: _priority(p.relative_to(root)),
    )

    tree_lines = [p.relative_to(root).as_posix() for p in candidates]
    prefix = "# Repository tree\n" + "\n".join(tree_lines) + "\n\n# File contents\n"
    remaining = max_chars - len(prefix)
    chunks: list[str] = [prefix]
    included: list[str] = []
    truncated = False

    for path in candidates:
        relative = path.relative_to(root).as_posix()
        content = _safe_read(path, max_file_chars=max_file_chars)
        if content is None:
            continue
        block = f"\n--- FILE: {relative} ---\n{content}\n--- END FILE ---\n"
        if len(block) > remaining:
            truncated = True
            continue
        chunks.append(block)
        included.append(relative)
        remaining -= len(block)

    return RepositoryContext(
        root=root,
        text="".join(chunks),
        included_files=tuple(included),
        truncated=truncated,
        mode="repository",
    )


def build_diff_context(
    repo_path: str | Path,
    base: str,
    *,
    max_chars: int = 120_000,
) -> RepositoryContext:
    root = Path(repo_path).expanduser().resolve()
    if not (root / ".git").exists():
        raise ValueError(f"--diff-base requires a Git repository: {root}")

    command = ["git", "-C", str(root), "diff", "--no-ext-diff", f"{base}...HEAD"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {result.stderr.strip()}")

    diff = result.stdout
    truncated = len(diff) > max_chars
    if truncated:
        diff = diff[:max_chars] + "\n... [diff truncated] ...\n"

    changed = []
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            changed.append(line[6:])

    text = f"# Git diff\nBase: {base}\nHead: HEAD\n\n{diff}"
    return RepositoryContext(
        root=root,
        text=text,
        included_files=tuple(dict.fromkeys(changed)),
        truncated=truncated,
        mode=f"diff:{base}",
    )
