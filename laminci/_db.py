import time
from pathlib import Path
from subprocess import run
from typing import Optional

from lamin_utils import logger


def setup_local_test_sqlite_file(src_settings, return_dir: bool = False):
    path = src_settings._sqlite_file_local
    new_stem = path.stem + "_test"
    tgt_sqlite_dir = Path.cwd() / new_stem
    if return_dir:
        return tgt_sqlite_dir
    tgt_sqlite_file = tgt_sqlite_dir / f"{new_stem}{path.suffix}"
    tgt_sqlite_file.parent.mkdir(exist_ok=True)
    if tgt_sqlite_file.exists():
        tgt_sqlite_file.unlink()
    tgt_db = f"sqlite:///{tgt_sqlite_file}"
    return tgt_db


def setup_local_test_postgres(name: str = "pgtest", version: Optional[str] = None):
    if version is not None:
        version = ":{version}"
    else:
        version = ""
    process = run(  # noqa: S602
        f"docker run --name {name} -e POSTGRES_PASSWORD=pwd"
        f" -e POSTGRES_DB={name} -d -p 5432:5432 postgres{version}",
        shell=True,
    )
    if process.returncode == 0:
        logger.info(
            "created Postgres test instance:"
            f" 'postgresql://postgres:pwd@0.0.0.0:5432/{name}' -- it runs in docker"
            f" container '{name}'"
        )
    else:
        raise RuntimeError(
            "Failed to set up postgres test instance. Try running\n"
            f"docker stop {name} && docker rm {name}"
        )
    time.sleep(2)
    return f"postgresql://postgres:pwd@0.0.0.0:5432/{name}"
