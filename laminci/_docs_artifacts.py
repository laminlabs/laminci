import os
import warnings
from pathlib import Path
from subprocess import run
from zipfile import ZipFile

from lamin_utils import logger


def zip_docs_dir(zip_filename: str, docs_dir: str = "./docs") -> None:
    with ZipFile(zip_filename, "w") as zf:
        zf.write("README.md")
        for f in Path(docs_dir).glob("**/*"):
            if ".ipynb_checkpoints" in str(f):
                continue
            if f.suffix in {".md", ".ipynb", ".png", ".jpg", ".svg", ".py"}:
                zf.write(f, f.relative_to(docs_dir))  # add at root level


def zip_docs(docs_dir: str = "./docs"):
    repo_name = Path.cwd().name
    assert "." not in repo_name  # doesn't have a weird suffix  # noqa: S101
    assert Path(".git/").exists()  # is git repo  # noqa: S101
    assert repo_name.lower() == repo_name  # is all lower-case  # noqa: S101
    zip_filename = f"{repo_name}.zip"
    zip_docs_dir(zip_filename, docs_dir)
    return repo_name, zip_filename


# Ruff seems to ignore any noqa comments in the following and we therefore disable it briefly
# ruff: noqa
def upload_docs_artifact_aws(docs_dir: str = "./docs") -> None:
    repo_name, zip_filename = zip_docs(docs_dir)
    run(
        f"aws s3 cp {zip_filename} s3://lamin-site-assets/docs/{zip_filename}",
        shell=True,
    )


# ruff: enable


def upload_docs_artifact_lamindb() -> None:
    repo_name, zip_filename = zip_docs()

    import lamindb as ln

    ln.setup.load("testuser1/lamin-site-assets", migrate=True)

    transform = ln.add(ln.Transform, name=f"CI {repo_name}")
    ln.track(transform=transform)

    file = ln.select(ln.File, key=f"docs/{zip_filename}").one_or_none()
    if file is not None:
        file.replace(zip_filename)
    else:
        file = ln.File(zip_filename, key=f"docs/{zip_filename}")
    ln.add(file)


def upload_docs_artifact(aws: bool = False, docs_dir: str = "./docs") -> None:
    if os.getenv("GITHUB_EVENT_NAME") not in {"push", "repository_dispatch"}:
        logger.info("Only upload docs artifact for push event.")
        return None

    if aws:
        upload_docs_artifact_aws(docs_dir)
    else:
        try:
            # this is super ugly but necessary right now
            # we might need to close the current instance as it might be corrupted
            import lamindb_setup

            lamindb_setup.close()

            import lamindb as ln  # noqa

            upload_docs_artifact_lamindb()

        except ImportError:
            warnings.warn("Fall back to AWS", stacklevel=2)
            upload_docs_artifact_aws()
