import os
import warnings
from pathlib import Path
from subprocess import run
from zipfile import ZipFile

from lamin_utils import logger

from ._env import get_package_name


def zip_docs_dir(zip_filename: str) -> None:
    with ZipFile(zip_filename, "w") as zf:
        zf.write("README.md")
        for f in Path("./docs").glob("**/*"):
            if ".ipynb_checkpoints" in str(f):
                continue
            if f.suffix in {".md", ".ipynb", ".png", ".jpg", ".svg"}:
                zf.write(f, f.relative_to("./docs"))  # add at root level


def zip_docs():
    package_name = get_package_name()
    zip_filename = f"{package_name}_docs.zip"
    zip_docs_dir(zip_filename)
    return package_name, zip_filename


def upload_docs_artifact_aws() -> None:
    package_name, zip_filename = zip_docs()
    run(
        f"aws s3 cp {zip_filename} s3://lamin-site-assets/docs/{zip_filename}",
        shell=True,
    )


def upload_docs_artifact_lamindb() -> None:
    package_name, zip_filename = zip_docs()

    import lamindb as ln

    ln.setup.load("testuser1/lamin-site-assets", migrate=True)

    transform = ln.add(ln.Transform, name=f"CI {package_name}")
    ln.track(transform=transform)

    file = ln.select(ln.File, key=f"docs/{zip_filename}").one_or_none()
    if file is not None:
        file.replace(zip_filename)
    else:
        file = ln.File(zip_filename, key=f"docs/{zip_filename}")
    ln.add(file)


def upload_docs_artifact(aws: bool = False) -> None:
    if os.getenv("GITHUB_EVENT_NAME") not in {"push", "repository_dispatch"}:
        logger.info("Only upload docs artifact for push event.")
        return None

    if aws:
        upload_docs_artifact_aws()
    else:
        try:
            # this is super ugly but necessary right now
            # we might need to close the current instance as it might be corrupted
            import lamindb_setup

            lamindb_setup.close()

            import lamindb as ln  # noqa

            upload_docs_artifact_lamindb()

        except ImportError:
            warnings.warn("Fall back to AWS")
            upload_docs_artifact_aws()
