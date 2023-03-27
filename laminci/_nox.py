import os
from pathlib import Path

from nox import Session

from ._db import setup_local_test_postgres
from ._env import get_package_name, get_schema_handle


def login_testuser1(session: Session):
    login_user_1 = "lndb login testuser1@lamin.ai --password cEvcwMJFX4OwbsYVaMt2Os6GxxGgDUlBGILs2RyS"  # noqa
    session.run(*(login_user_1.split(" ")), external=True)


def login_testuser2(session: Session):
    login_user_1 = "lndb login testuser2@lamin.ai --password goeoNJKE61ygbz1vhaCVynGERaRrlviPBVQsjkhz"  # noqa
    session.run(*(login_user_1.split(" ")), external=True)


def setup_test_instances_from_main_branch(session: Session, schema: str = None):
    # spin up a postgres test instance
    pgurl = setup_local_test_postgres()
    # switch to the main branch
    if "GITHUB_BASE_REF" in os.environ and os.environ["GITHUB_BASE_REF"] != "":
        session.run("git", "switch", os.environ["GITHUB_BASE_REF"], external=True)
    session.install(".[test]")  # install current package from main branch
    # init a postgres instance
    init_instance = f"lndb init --storage pgtest --db {pgurl}"
    schema_handle = get_schema_handle()
    if schema is None and schema_handle not in {None, "core"}:
        init_instance += f" --schema {schema_handle}"
    elif schema is not None:
        init_instance += f" --schema {schema}"
    session.run(*init_instance.split(" "), external=True)
    # go back to the PR branch
    if "GITHUB_HEAD_REF" in os.environ and os.environ["GITHUB_HEAD_REF"] != "":
        session.run("git", "switch", os.environ["GITHUB_HEAD_REF"], external=True)


def run_pre_commit(session: Session):
    session.install("pre-commit")
    session.run("pre-commit", "install")
    session.run("pre-commit", "run", "--all-files")


def run_pytest(session: Session, coverage: bool = True):
    package_name = get_package_name()
    coverage_args = (
        f"--cov={package_name} --cov-append --cov-report=term-missing".split()
    )
    session.run(
        "pytest",
        "-s",
        *coverage_args,
    )
    if coverage:
        session.run("coverage", "xml")


def build_docs(session: Session):
    prefix = "." if Path("./lndocs").exists() else ".."
    session.install(f"{prefix}/lndocs")
    session.run("lndocs")
