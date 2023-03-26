import os
from pathlib import Path
from zipfile import ZipFile

from ._env import get_package_name


def upload_docs_artifact():
    import lamindb as ln

    if os.environ["GITHUB_EVENT_NAME"] != "push":
        return
    package_name = get_package_name()
    filestem = f"{package_name}_docs"
    filename = f"{filestem}.zip"

    with ZipFile(filename, "w") as zf:
        zf.write("README.md")
        for f in Path("./docs").glob("**/*"):
            if ".ipynb_checkpoints" in str(f):
                continue
            if f.suffix in {".md", ".ipynb", ".png", ".jpg", ".svg"}:
                zf.write(f, f.relative_to("./docs"))  # add at root level

    ln.setup.load("testuser1/lamin-site-assets", migrate=True)

    with ln.Session() as ss:
        transform = ln.add(ln.Transform, name=f"CI {package_name}")
        run = ln.Run(transform=transform)

        dobject = ss.select(ln.File, name=filestem).one_or_none()
        if dobject is not None:
            dobject._cloud_filepath = None
            dobject._local_filepath = Path(filename)
            dobject.source = run
        else:
            dobject = ln.File(filename, source=run)
        ss.add(dobject)
