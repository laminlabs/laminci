import os
import shutil

from ._env import get_package_name


def upload_docs_dir():
    import lndb

    if os.environ["GITHUB_EVENT_NAME"] != "push":
        return
    package_name = get_package_name()
    filestem = f"{package_name}_docs"
    filename = shutil.make_archive(filestem, "zip", "./docs")
    lndb.load("testuser1/lamin-site-assets", migrate=True)

    import lamindb as ln
    import lamindb.schema as lns

    with ln.Session() as ss:
        dobject = ss.select(ln.DObject, name=filestem).one_or_none()
        pipeline = ln.add(lns.Pipeline, name=f"CI {package_name}")
        run = lns.Run(pipeline=pipeline)
        if dobject is None:
            dobject = ln.DObject(filename, source=run)
        else:
            dobject.source = run
        ss.add(dobject)
