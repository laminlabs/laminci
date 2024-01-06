import os
from pathlib import Path
from typing import Dict, Optional

import nox
from nox import Session

from . import _nox_logger  # noqa, silence logger
from ._env import get_package_name


def login_testuser1(session: Session, env: Optional[Dict[str, str]] = None):
    import lamindb_setup as ln_setup

    if env is not None:
        os.environ.update(env)
    ln_setup.login("testuser1@lamin.ai", key="cEvcwMJFX4OwbsYVaMt2Os6GxxGgDUlBGILs2RyS")


def login_testuser2(session: Session, env: Optional[Dict[str, str]] = None):
    import lamindb_setup as ln_setup

    if env is not None:
        os.environ.update(env)
    ln_setup.login("testuser2@lamin.ai", key="goeoNJKE61ygbz1vhaCVynGERaRrlviPBVQsjkhz")


def login_laminapp_admin(session: Session, env: Optional[Dict[str, str]] = None):
    import lamindb_setup as ln_setup

    if env is not None:
        os.environ.update(env)
    ln_setup.login("support@lamin.ai", key="wLNng29pBadv2O9aKpwri2blCHzT1XUb5Ii9jxYL")


def run_pre_commit(session: Session):
    if nox.options.default_venv_backend == "none":
        session.run(*"pip install pre-commit".split())
    else:
        session.install("pre-commit")
    session.run("pre-commit", "install")
    session.run("pre-commit", "run", "--all-files")


def run_pytest(session: Session, coverage: bool = True, env: Optional[Dict] = None):
    package_name = get_package_name()
    coverage_args = (
        f"--cov={package_name} --cov-append --cov-report=term-missing".split()
    )
    session.run(
        "pytest",
        "-s",
        *coverage_args,
        env=env,
    )
    if coverage:
        session.run("coverage", "xml")


def build_docs(session: Session, strict: bool = False, strip_prefix: bool = False):
    prefix = "." if Path("./lndocs").exists() else ".."
    if nox.options.default_venv_backend == "none":
        session.run(*f"pip install {prefix}/lndocs".split())
    else:
        session.install(f"{prefix}/lndocs")
    # do not simply add instance creation here
    args = ["lndocs"]
    if strict:
        args.append("--strict")
    if strip_prefix:
        args.append("--strip-prefix")
    session.run(*args)
