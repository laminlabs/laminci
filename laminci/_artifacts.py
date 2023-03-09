import os
from pathlib import Path
from zipfile import ZipFile

from ._env import get_package_name


def upload_docs_dir():
    import lamindb as ln
    import lamindb.schema as lns

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
            if f.suffix in {".md", ".ipynb"}:
                zf.write(f, f.relative_to("./docs"))  # add at root level

    ln.setup.load("testuser1/lamin-site-assets", migrate=True)

    with ln.Session() as ss:
        pipeline = ln.add(lns.Pipeline, name=f"CI {package_name}")
        run = lns.Run(pipeline=pipeline)

        dobject = ss.select(ln.DObject, name=filestem).one_or_none()
        if dobject is not None:
            dobject._cloud_filepath = None
            dobject._local_filepath = Path(filename)
            dobject.source = run
        else:
            dobject = ln.DObject(filename, source=run)
        ss.add(dobject)
