from __future__ import annotations

from pathlib import Path


def run_notebooks(file_or_folder: str | Path):
    import nbproject_test

    path = Path(file_or_folder)
    assert path.exists()
    nbproject_test.execute_notebooks(path.resolve(), write=True)

    import nbformat

    def strip_bash(nb_path):
        nb = nbformat.read(nb_path, as_version=4)
        modified = False
        for cell in nb.cells:
            if cell.cell_type == "code" and cell.source.startswith("%%bash"):
                import re

                cell.source = re.sub(r"^%%bash\n?", "", cell.source)
                modified = True
        if modified:
            nbformat.write(nb, nb_path)

    if path.is_dir():
        for nb_path in path.glob("**/*.ipynb"):
            strip_bash(nb_path)
    elif path.suffix == ".ipynb":
        strip_bash(path)
