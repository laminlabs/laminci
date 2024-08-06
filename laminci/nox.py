import json
import os
import shlex
from pathlib import Path
from typing import Dict, Iterable, Literal, Optional, Union

import nox
from nox import Session

from . import _nox_logger  # noqa, the import silences the logger
from ._env import get_package_name

SYSTEM = " --system " if os.getenv("CI") else ""


def _login_lamin_user(user_email: str, env: Optional[Dict[str, str]] = None):
    import boto3
    import lamindb_setup as ln_setup

    if env is not None:
        os.environ.update(env)
    session = boto3.session.Session()
    client = session.client(
        service_name="secretsmanager",
        region_name="us-east-1",
    )
    arn = (
        "arn:aws:secretsmanager:us-east-1:586130067823:secret:laminlabs-internal-sZj1MU"
    )
    secrets = json.loads(client.get_secret_value(SecretId=arn)["SecretString"])
    if user_email == "testuser1@lamin.ai":
        ln_setup.login(user_email, key=secrets["LAMIN_TESTUSER1_API_KEY"])
    elif user_email == "testuser2@lamin.ai":
        ln_setup.login(user_email, key=secrets["LAMIN_TESTUSER2_API_KEY"])
    else:
        raise NotImplementedError


def login_testuser1(session: Session, env: Optional[Dict[str, str]] = None):
    _login_lamin_user("testuser1@lamin.ai", env=env)


def login_testuser2(session: Session, env: Optional[Dict[str, str]] = None):
    _login_lamin_user("testuser2@lamin.ai", env=env)


def run(session: Session, s: str, **kwargs):
    assert (args := shlex.split(s))
    return session.run(*args, **kwargs)


def run_pre_commit(session: Session):
    if nox.options.default_venv_backend == "none":
        session.run(*"uv pip install --system pre-commit".split())
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
        session.run(*f"uv pip install --system {prefix}/lndocs".split())
    else:
        session.install(f"{prefix}/lndocs")
    # do not simply add instance creation here
    args = ["lndocs"]
    if strict:
        args.append("--strict")
    if strip_prefix:
        args.append("--strip-prefix")
    session.run(*args)


def install_lamindb(
    session: Session,
    branch: Literal["release", "main"],
    extras: Optional[Union[Iterable[str], str]] = None,
):
    assert branch in {"release", "main"}

    if extras is None:
        extras_str = ""
    elif isinstance(extras, str):
        if extras == "":
            extras_str = ""
        else:
            assert "[" not in extras and "]" not in extras
            extras_str = f"[{extras}]"
    else:
        extras_str = f"[{','.join(extras)}]"

    session.run(
        "git",
        "clone",
        "-b",
        branch,
        "--depth",
        "1",
        "--recursive",
        "--shallow-submodules",
        "https://github.com/laminlabs/lamindb",
    )
    if branch == "main":
        session.run(
            "uv",
            "pip",
            "install",
            "--system",
            "--no-deps",
            "./lamindb/sub/lamindb-setup",
            "./lamindb/sub/lnschema-core",
            "./lamindb/sub/lamin-cli",
            "./lamindb/sub/bionty",
            "./lamindb/sub/wetlab",
        )
    session.run(
        "uv",
        "pip",
        "install",
        "--system",
        f"./lamindb{extras_str}",
    )
