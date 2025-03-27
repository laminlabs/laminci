import os
from pathlib import Path
from subprocess import run
from zipfile import ZipFile


def zip_docs_dir(zip_filename: str, docs_dir: str = "./docs") -> None:
    with ZipFile(zip_filename, "w") as zf:
        zf.write("README.md")
        for f in Path(docs_dir).glob("**/*"):
            if ".ipynb_checkpoints" in str(f):
                continue
            if f.suffix in {".md", ".ipynb", ".png", ".jpg", ".svg", ".py", ".R"}:
                zf.write(f, f.relative_to(docs_dir))  # add at root level


def zip_docs(docs_dir: str = "./docs"):
    repo_name = Path.cwd().name
    assert "." not in repo_name  # doesn't have a weird suffix  # noqa: S101
    assert Path(".git/").exists()  # is git repo  # noqa: S101
    assert repo_name.lower() == repo_name  # is all lower-case  # noqa: S101
    zip_filename = f"{repo_name}.zip"
    zip_docs_dir(zip_filename, docs_dir)
    return repo_name, zip_filename


def upload_docs_artifact(
    aws: bool = False, docs_dir: str = "./docs", in_pr: bool = False
) -> None:
    if not in_pr:
        if os.getenv("GITHUB_EVENT_NAME") not in {"push", "repository_dispatch"}:
            print("Only upload docs artifact for push event.")
            return None
    if aws:
        print("aws arg no longer needed")
    _, zip_filename = zip_docs(docs_dir)
    run(  # noqa: S602
        f"aws s3 cp {zip_filename} s3://lamin-site-assets/docs/{zip_filename}",
        shell=True,
    )
