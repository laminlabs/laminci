import os
from pathlib import Path
from zipfile import ZipFile

from ._env import get_package_name


def upload_docs_dir():
    import lndb

    if os.environ["GITHUB_EVENT_NAME"] != "push":
        return
    package_name = get_package_name()
    filestem = f"{package_name}_docs"
    filename = f"{filestem}.zip"

    with ZipFile(filename, "w") as zf:
        for f in Path("./docs").glob("**/*"):
            if ".ipynb_checkpoints" in str(f):
                continue
            if f.suffix in {".md", ".ipynb"}:
                zf.write(f)

    lndb.load("testuser1/lamin-site-assets", migrate=True)

    import lamindb as ln
    import lamindb.schema as lns

    with ln.Session() as ss:
        pipeline = ln.add(lns.Pipeline, name=f"CI {package_name}")
        run = lns.Run(pipeline=pipeline)

        dobject = ln.DObject(filename, source=run)
        existing_dobject_to_overwrite = ss.select(
            ln.DObject, name=filestem
        ).one_or_none()
        if existing_dobject_to_overwrite is not None:
            dobject.id = existing_dobject_to_overwrite.id
        ss.add(dobject)
