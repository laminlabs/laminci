"""Copy the LaminDB guide into the package for the duration of a flit build."""

import shutil
from pathlib import Path

_REQUIRED = ("guide.md", "tutorial.md")


def agent_docs_dir(root: Path | None = None) -> Path:
    return (root or Path.cwd()) / "lamindb" / ".agents" / "docs"


def sync_lamindb_agent_docs(root: Path | None = None) -> Path:
    """Copy ``docs/**/*.md`` into ``lamindb/.agents/docs`` so flit packs them.

    Flit's wheel walk includes gitignored files. The copy is deleted after the
    build, so it is never committed. ``nox -s prepare`` deletes the executable
    pages first; refuse to package a guide that is already gone.
    """
    root = root or Path.cwd()
    source = root / "docs"
    dest = agent_docs_dir(root)
    if not (root / "lamindb" / "__init__.py").is_file():
        raise SystemExit("lamindb package is missing; cannot package the guide.")
    missing = [name for name in _REQUIRED if not (source / name).is_file()]
    if missing:
        joined = ", ".join(f"docs/{name}" for name in missing)
        raise SystemExit(
            f"Refusing to package the guide; missing {joined}. "
            "Release from a clean checkout: nox -s prepare deletes executable pages."
        )
    if dest.exists():
        shutil.rmtree(dest)
    count = 0
    for path in sorted(source.rglob("*.md")):
        target = dest / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        count += 1
    print(f"INFO: Copied {count} guide pages into {dest} for packaging")
    return dest


def remove_lamindb_agent_docs(root: Path | None = None) -> None:
    dest = agent_docs_dir(root)
    if dest.is_dir():
        shutil.rmtree(dest)
