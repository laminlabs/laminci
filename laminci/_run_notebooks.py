from __future__ import annotations

from pathlib import Path


def run_notebooks(file_or_folder: str | Path):
    import nbproject_test

    nbproject_test.execute_notebooks(Path(file_or_folder), write=True)
