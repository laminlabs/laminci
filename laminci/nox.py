import json
import os
from pathlib import Path
from typing import Dict, Optional

import nox
from nox import Session

from . import _nox_logger  # noqa, silence logger
from ._env import get_package_name


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
