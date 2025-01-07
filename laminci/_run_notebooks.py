from __future__ import annotations

from pathlib import Path


def run_notebooks(file_or_folder: str | Path):
    import nbproject_test

    path = Path(file_or_folder)
    assert path.exists()  # noqa: S101
    nbproject_test.execute_notebooks(path.resolve(), write=True)
